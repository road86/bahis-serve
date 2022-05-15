import json
import os
import re
import logging

from datetime import datetime
from tempfile import NamedTemporaryFile
from time import strftime, strptime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import get_storage_class
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseForbidden, HttpResponseRedirect, HttpResponseNotFound,
    HttpResponseBadRequest, HttpResponse)
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

from onadata.apps.main.models import UserProfile, MetaData, TokenStorageModel
from onadata.apps.logger.models import XForm, Attachment
from onadata.apps.logger.views import download_jsonform
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.export import Export
from onadata.apps.viewer.tasks import create_async_export,new_create_async_export
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.common_tags import SUBMISSION_TIME
from onadata.libs.utils.export_tools import (
    generate_export,
    should_create_new_export,
    kml_export_data,
    newset_export_for)
from onadata.libs.utils.image_tools import image_url
from onadata.libs.utils.google import google_export_xls, redirect_uri
from onadata.libs.utils.log import audit_log, Actions
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name,\
    disposition_ext_and_date
from onadata.libs.utils.viewer_tools import create_attachments_zipfile,\
    export_def_from_filename
from onadata.libs.utils.user_auth import has_permission, get_xform_and_perms,\
    helper_auth_helper, has_edit_permission
from xls_writer import XlsWriter
from onadata.libs.utils.chart_tools import build_chart_data
from django.db import connection
from django.views.decorators.http import require_POST, require_http_methods
from onadata.libs.utils.logger_tools import check_form_permissions,get_form_permissions
from collections import OrderedDict
import pandas
from onadata.apps.bh_module.utility_functions import datasource_query_generate

media_file_logger = logging.getLogger('media_files')


def _set_submission_time_to_query(query, request):
    query[SUBMISSION_TIME] = {}
    try:
        if request.GET.get('start'):
            query[SUBMISSION_TIME]['$gte'] = format_date_for_mongo(
                request.GET['start'])
        if request.GET.get('end'):
            query[SUBMISSION_TIME]['$lte'] = format_date_for_mongo(
                request.GET['end'])
    except ValueError:
        return HttpResponseBadRequest(
            _("Dates must be in the format YY_MM_DD_hh_mm_ss"))

    return query


def encode(time_str):
    time = strptime(time_str, "%Y_%m_%d_%H_%M_%S")
    return strftime("%Y-%m-%d %H:%M:%S", time)


def format_date_for_mongo(x):
    return datetime.strptime(x, '%y_%m_%d_%H_%M_%S')\
        .strftime('%Y-%m-%dT%H:%M:%S')


def instances_for_export(dd, start=None, end=None):
    if start and not end:
        return dd.instances.filter(date_created__gte=start)
    elif end and not start:
        return dd.instances.filter(date_created__lte=end)
    elif start and end:
        return dd.instances.filter(date_created__gte=start,
                                   date_created__lte=end)


def dd_for_params(id_string, owner, request):
    start = end = None
    dd = DataDictionary.objects.get(id_string__exact=id_string,
                                    user=owner)
    if request.GET.get('start'):
        try:
            start = encode(request.GET['start'])
        except ValueError:
            # bad format
            return [False,
                    HttpResponseBadRequest(
                        _(u'Start time format must be YY_MM_DD_hh_mm_ss'))
                    ]
    if request.GET.get('end'):
        try:
            end = encode(request.GET['end'])
        except ValueError:
            # bad format
            return [False,
                    HttpResponseBadRequest(
                        _(u'End time format must be YY_MM_DD_hh_mm_ss'))
                    ]
    if start or end:
        dd.instances_for_export = instances_for_export(dd, start, end)

    return [True, dd]


def parse_label_for_display(pi, xpath):
    label = pi.data_dictionary.get_label(xpath)
    if not type(label) == dict:
        label = {'Unknown': label}
    return label.items()


def average(values):
    if len(values):
        return sum(values, 0.0) / len(values)
    return None


def map_view(request, username, id_string, template='map.html'):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))
    data = {'content_user': owner, 'xform': xform}
    data['profile'], created = UserProfile.objects.get_or_create(user=owner)
    # Follow the example of onadata.apps.main.views.show
    data['can_edit'] = has_edit_permission(xform, owner, request)

    data['form_view'] = True
    data['jsonform_url'] = reverse(download_jsonform,
                                   kwargs={"username": username,
                                           "id_string": id_string})
    data['enketo_edit_url'] = reverse('edit_data',
                                      kwargs={"username": username,
                                              "id_string": id_string,
                                              "data_id": 0})
    data['enketo_add_url'] = reverse('enter_data',
                                     kwargs={"username": username,
                                             "id_string": id_string})

    data['enketo_add_with_url'] = reverse('add_submission_with',
                                          kwargs={"username": username,
                                                  "id_string": id_string})
    data['mongo_api_url'] = reverse('mongo_view_api',
                                    kwargs={"username": username,
                                            "id_string": id_string})
    data['delete_data_url'] = reverse('delete_data',
                                      kwargs={"username": username,
                                              "id_string": id_string})
    data['mapbox_layer'] = MetaData.mapbox_layer_upload(xform)
    audit = {
        "xform": xform.id_string
    }
    audit_log(Actions.FORM_MAP_VIEWED, request.user, owner,
              _("Requested map on '%(id_string)s'.")
              % {'id_string': xform.id_string}, audit, request)
    return render(request, template, data)


def map_embed_view(request, username, id_string):
    return map_view(request, username, id_string, template='map_embed.html')


def add_submission_with(request, username, id_string):

    import uuid
    import requests

    from django.template import loader, Context
    from dpath import util as dpath_util
    from dict2xml import dict2xml

    def geopoint_xpaths(username, id_string):
        d = DataDictionary.objects.get(
            user__username__iexact=username, id_string__exact=id_string)
        return [e.get_abbreviated_xpath()
                for e in d.get_survey_elements()
                if e.bind.get(u'type') == u'geopoint']

    value = request.GET.get('coordinates')
    xpaths = geopoint_xpaths(username, id_string)
    xml_dict = {}
    for path in xpaths:
        dpath_util.new(xml_dict, path, value)

    context = {'username': username,
               'id_string': id_string,
               'xml_content': dict2xml(xml_dict)}
    instance_xml = loader.get_template("instance_add.xml")\
        .render(Context(context))

    url = settings.ENKETO_API_INSTANCE_IFRAME_URL
    return_url = reverse('thank_you_submission',
                         kwargs={"username": username, "id_string": id_string})
    if settings.DEBUG:
        openrosa_url = "https://dev.formhub.org/{}".format(username)
    else:
        openrosa_url = request.build_absolute_uri("/{}".format(username))
    payload = {'return_url': return_url,
               'form_id': id_string,
               'server_url': openrosa_url,
               'instance': instance_xml,
               'instance_id': uuid.uuid4().hex}

    r = requests.post(url, data=payload,
                      auth=(settings.ENKETO_API_TOKEN, ''), verify=False)

    return HttpResponse(r.text, content_type='application/json')


def thank_you_submission(request, username, id_string):
    return HttpResponse("Thank You")


def data_export(request, username, id_string, export_type):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))
    query = request.GET.get("query")
    extension = export_type

    # check if we should force xlsx
    force_xlsx = request.GET.get('xls') != 'true'
    if export_type == Export.XLS_EXPORT and force_xlsx:
        extension = 'xlsx'
    elif export_type in [Export.CSV_ZIP_EXPORT, Export.SAV_ZIP_EXPORT]:
        extension = 'zip'

    audit = {
        "xform": xform.id_string,
        "export_type": export_type
    }
    # check if we need to re-generate,
    # we always re-generate if a filter is specified
    if should_create_new_export(xform, export_type) or query or\
            'start' in request.GET or 'end' in request.GET:
        # check for start and end params
        if 'start' in request.GET or 'end' in request.GET:
            if not query:
                query = '{}'
            query = json.dumps(
                _set_submission_time_to_query(json.loads(query), request))
        try:
            export = generate_export(
                export_type, extension, username, id_string, None, query)
            audit_log(
                Actions.EXPORT_CREATED, request.user, owner,
                _("Created %(export_type)s export on '%(id_string)s'.") %
                {
                    'id_string': xform.id_string,
                    'export_type': export_type.upper()
                }, audit, request)
        except NoRecordsFoundError:
            return HttpResponseNotFound(_("No records found to export"))
    else:
        export = newset_export_for(xform, export_type)

    # log download as well
    audit_log(
        Actions.EXPORT_DOWNLOADED, request.user, owner,
        _("Downloaded %(export_type)s export on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
            'export_type': export_type.upper()
        }, audit, request)

    if not export.filename:
        # tends to happen when using newset_export_for.
        return HttpResponseNotFound("File does not exist!")

    # get extension from file_path, exporter could modify to
    # xlsx if it exceeds limits
    path, ext = os.path.splitext(export.filename)
    ext = ext[1:]
    if request.GET.get('raw'):
        id_string = None

    response = response_with_mimetype_and_name(
        Export.EXPORT_MIMES[ext], id_string, extension=ext,
        file_path=export.filepath)

    return response


@login_required
@require_POST
def create_export(request, username, id_string, export_type):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    if export_type == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform=xform):
            return HttpResponseForbidden(_(u'No XLS Template set.'))

    query = request.POST.get("query")
    print ("query++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    print query
    force_xlsx = request.POST.get('xls') != 'true'

    # export options

    export_data_type = request.POST.get('rprt_data_type','xml')
    if export_data_type == 'xml':
        edt = 0
    else:
        edt = 1
    default_xls_fields = request.POST.get('default_xls_fields')
    export_label_lang = None
    if export_data_type == 'lbl':
        export_label_lang = request.POST.get('label_name')
    group_delimiter = request.POST.get("options[group_delimiter]", '/')
    if group_delimiter not in ['.', '/']:
        return HttpResponseBadRequest(
            _("%s is not a valid delimiter" % group_delimiter))

    # default is True, so when dont_.. is yes
    # split_select_multiples becomes False
    split_select_multiples = request.POST.get(
        "options[dont_split_select_multiples]", "no") == "no"

    binary_select_multiples = getattr(settings, 'BINARY_SELECT_MULTIPLES',
                                      False)
    # external export option
    meta = request.POST.get("meta")
    options = {
        'group_delimiter': group_delimiter,
        'split_select_multiples': split_select_multiples,
        'binary_select_multiples': binary_select_multiples,
        'meta': meta.replace(",", "") if meta else None,
        'exp_data_typ':export_data_type,
        'export_label_lang':export_label_lang,
        'default_xls_fields':default_xls_fields
    }

    try:
        #create_async_export(xform, export_type, query, force_xlsx, options)
        new_create_async_export(export_label_lang, xform, query, edt, id_string, export_type)
    except Export.ExportTypeError:
        return HttpResponseBadRequest(
            _("%s is not a valid export type" % export_type))
    else:
        audit = {
            "xform": xform.id_string,
            "export_type": export_type
        }
        audit_log(
            Actions.EXPORT_CREATED, request.user, owner,
            _("Created %(export_type)s export on '%(id_string)s'.") %
            {
                'export_type': export_type.upper(),
                'id_string': xform.id_string,
            }, audit, request)
        # mpower start: added for redirection to custom view
        custom = request.POST.get("custom", "default")
        if custom != 'default':
            return HttpResponseRedirect('/usermodule/'+owner.username+'/projects-views/'+xform.id_string+'/?tab_selection='+custom)
        # mpower end: added for redirection to custom view

        return HttpResponseRedirect(reverse(
            export_list,
            kwargs={
                "username": username,
                "id_string": id_string,
                "export_type": export_type
            })
        )


def _get_google_token(request, redirect_to_url):
    token = None
    if request.user.is_authenticated():
        try:
            ts = TokenStorageModel.objects.get(id=request.user)
        except TokenStorageModel.DoesNotExist:
            pass
        else:
            token = ts.token
    elif request.session.get('access_token'):
        token = request.session.get('access_token')
    if token is None:
        request.session["google_redirect_url"] = redirect_to_url
        return HttpResponseRedirect(redirect_uri)
    return token


def export_list(request, username, id_string, export_type):
    if export_type == Export.GDOC_EXPORT:
        redirect_url = reverse(
            export_list,
            kwargs={
                'username': username, 'id_string': id_string,
                'export_type': export_type})
        token = _get_google_token(request, redirect_url)
        if isinstance(token, HttpResponse):
            return token
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    if export_type == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform=xform):
            return HttpResponseForbidden(_(u'No XLS Template set.'))
    # Get meta and token
    export_token = request.GET.get('token')
    export_meta = request.GET.get('meta')
    options = {
        'meta': export_meta,
        'token': export_token,
    }

    if should_create_new_export(xform, export_type):
        try:
            create_async_export(
                xform, export_type, query=None, force_xlsx=True,
                options=options)
        except Export.ExportTypeError:
            return HttpResponseBadRequest(
                _("%s is not a valid export type" % export_type))

    metadata = MetaData.objects.filter(xform=xform,
                                       data_type="external_export")\
        .values('id', 'data_value')

    for m in metadata:
        m['data_value'] = m.get('data_value').split('|')[0]

    data = {
        'username': owner.username,
        'xform': xform,
        'export_type': export_type,
        'export_type_name': Export.EXPORT_TYPE_DICT[export_type],
        'exports': Export.objects.filter(
            xform=xform, export_type=export_type).order_by('-created_on'),
        'metas': metadata
    }

    return render(request, 'export_list.html', data)


def export_progress(request, username, id_string, export_type):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    # find the export entry in the db
    export_ids = request.GET.getlist('export_ids')
    exports = Export.objects.filter(xform=xform, id__in=export_ids)
    statuses = []
    for export in exports:
        status = {
            'complete': False,
            'url': None,
            'filename': None,
            'export_id': export.id
        }

        if export.status == Export.SUCCESSFUL:
            status['url'] = reverse(export_download, kwargs={
                'username': owner.username,
                'id_string': xform.id_string,
                'export_type': export.export_type,
                'filename': export.filename
            })
            status['filename'] = export.filename
            if export.export_type == Export.GDOC_EXPORT and \
                    export.export_url is None:
                redirect_url = reverse(
                    export_progress,
                    kwargs={
                        'username': username, 'id_string': id_string,
                        'export_type': export_type})
                token = _get_google_token(request, redirect_url)
                if isinstance(token, HttpResponse):
                    return token
                status['url'] = None
                try:
                    url = google_export_xls(
                        export.full_filepath, xform.title, token, blob=True)
                except Exception, e:
                    status['error'] = True
                    status['message'] = e.message
                else:
                    export.export_url = url
                    export.save()
                    status['url'] = url
            if export.export_type == Export.EXTERNAL_EXPORT \
                    and export.export_url is None:
                status['url'] = url
        # mark as complete if it either failed or succeeded but NOT pending
        if export.status == Export.SUCCESSFUL \
                or export.status == Export.FAILED:
            status['complete'] = True
        statuses.append(status)

    return HttpResponse(
        json.dumps(statuses), content_type='application/json')


def export_download(request, username, id_string, export_type, filename):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    # find the export entry in the db
    export = get_object_or_404(Export, xform=xform, filename=filename)

    if (export_type == Export.GDOC_EXPORT or export_type == Export.EXTERNAL_EXPORT) \
            and export.export_url is not None:
        return HttpResponseRedirect(export.export_url)

    ext, mime_type = export_def_from_filename(export.filename)

    audit = {
        "xform": xform.id_string,
        "export_type": export.export_type
    }
    audit_log(
        Actions.EXPORT_DOWNLOADED, request.user, owner,
        _("Downloaded %(export_type)s export '%(filename)s' "
          "on '%(id_string)s'.") %
        {
            'export_type': export.export_type.upper(),
            'filename': export.filename,
            'id_string': xform.id_string,
        }, audit, request)
    if request.GET.get('raw'):
        id_string = None

    default_storage = get_storage_class()()
    if not isinstance(default_storage, FileSystemStorage):
        return HttpResponseRedirect(default_storage.url(export.filepath))
    basename = os.path.splitext(export.filename)[0]
    response = response_with_mimetype_and_name(
        mime_type, name=basename, extension=ext,
        file_path=export.filepath, show_date=False)
    return response


@login_required
@require_POST
def delete_export(request, username, id_string, export_type):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    export_id = request.POST.get('export_id')

    # find the export entry in the db
    export = get_object_or_404(Export, id=export_id)

    export.delete()
    audit = {
        "xform": xform.id_string,
        "export_type": export.export_type
    }
    audit_log(
        Actions.EXPORT_DOWNLOADED, request.user, owner,
        _("Deleted %(export_type)s export '%(filename)s'"
          " on '%(id_string)s'.") %
        {
            'export_type': export.export_type.upper(),
            'filename': export.filename,
            'id_string': xform.id_string,
        }, audit, request)

    # mpower start: added for redirection to custom view
    custom = request.POST.get("custom", "default")
    if custom != 'default':
            return HttpResponseRedirect('/usermodule/'+owner.username+'/projects-views/'+xform.id_string+'/?tab_selection='+custom)
    # mpower end: added for redirection to custom view
    return HttpResponseRedirect(reverse(
        export_list,
        kwargs={
            "username": username,
            "id_string": id_string,
            "export_type": export_type
        }))


def zip_export(request, username, id_string):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))
    if request.GET.get('raw'):
        id_string = None

    attachments = Attachment.objects.filter(instance__xform=xform)
    zip_file = None

    try:
        zip_file = create_attachments_zipfile(attachments)
        audit = {
            "xform": xform.id_string,
            "export_type": Export.ZIP_EXPORT
        }
        audit_log(
            Actions.EXPORT_CREATED, request.user, owner,
            _("Created ZIP export on '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        # log download as well
        audit_log(
            Actions.EXPORT_DOWNLOADED, request.user, owner,
            _("Downloaded ZIP export on '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        if request.GET.get('raw'):
            id_string = None

        response = response_with_mimetype_and_name('zip', id_string)
        response.write(FileWrapper(zip_file))
        response['Content-Length'] = zip_file.tell()
        zip_file.seek(0)
    finally:
        zip_file and zip_file.close()

    return response


def kml_export(request, username, id_string):
    # read the locations from the database
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    helper_auth_helper(request)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))
    data = {'data': kml_export_data(id_string, user=owner)}
    response = \
        render(request, "survey.kml", data,
               content_type="application/vnd.google-earth.kml+xml")
    response['Content-Disposition'] = \
        disposition_ext_and_date(id_string, 'kml')
    audit = {
        "xform": xform.id_string,
        "export_type": Export.KML_EXPORT
    }
    audit_log(
        Actions.EXPORT_CREATED, request.user, owner,
        _("Created KML export on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)
    # log download as well
    audit_log(
        Actions.EXPORT_DOWNLOADED, request.user, owner,
        _("Downloaded KML export on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)

    return response


def google_xls_export(request, username, id_string):
    token = None
    if request.user.is_authenticated():
        try:
            ts = TokenStorageModel.objects.get(id=request.user)
        except TokenStorageModel.DoesNotExist:
            pass
        else:
            token = ts.token
    elif request.session.get('access_token'):
        token = request.session.get('access_token')

    if token is None:
        request.session["google_redirect_url"] = reverse(
            google_xls_export,
            kwargs={'username': username, 'id_string': id_string})
        return HttpResponseRedirect(redirect_uri)

    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    valid, dd = dd_for_params(id_string, owner, request)
    if not valid:
        return dd

    ddw = XlsWriter()
    tmp = NamedTemporaryFile(delete=False)
    ddw.set_file(tmp)
    ddw.set_data_dictionary(dd)
    temp_file = ddw.save_workbook_to_file()
    temp_file.close()
    url = google_export_xls(tmp.name, xform.title, token, blob=True)
    os.unlink(tmp.name)
    audit = {
        "xform": xform.id_string,
        "export_type": "google"
    }
    audit_log(
        Actions.EXPORT_CREATED, request.user, owner,
        _("Created Google Docs export on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)

    return HttpResponseRedirect(url)


def data_view(request, username, id_string):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    data = {
        'owner': owner,
        'xform': xform
    }
    audit = {
        "xform": xform.id_string,
    }
    audit_log(
        Actions.FORM_DATA_VIEWED, request.user, owner,
        _("Requested data view for '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)

    return render(request, "data_view.html", data)


def attachment_url(request, size='medium'):
    media_file = request.GET.get('media_file')
    # TODO: how to make sure we have the right media file,
    # this assumes duplicates are the same file
    if media_file:
        mtch = re.search('^([^\/]+)/attachments(/[^\/]+)$', media_file)
        if mtch:
            # in cases where the media_file url created by instance.html's
            # _attachment_url function is in the wrong format, this will
            # match attachments with the correct owner and the same file name
            (username, filename) = mtch.groups()
            result = Attachment.objects.filter(**{
                  'instance__xform__user__username': username,
                }).filter(**{
                  'media_file__endswith': filename,
                })[0:1]
        else:
            # search for media_file with exact matching name
            result = Attachment.objects.filter(media_file=media_file)[0:1]

        if len(result) == 0:
            media_file_logger.info('attachment not found')
            return HttpResponseNotFound(_(u'Attachment not found'))

        attachment = result[0]

        if not attachment.mimetype.startswith('image'):
            return redirect(attachment.media_file.url)

        try:
            media_url = image_url(attachment, size)
        except:
            media_file_logger.error('could not get thumbnail for image', exc_info=True)
        else:
            if media_url:
                return redirect(media_url)

    return HttpResponseNotFound(_(u'Error: Attachment not found'))


def instance(request, username, id_string):
    instance_id = instance_id = request.GET.get('s_id', '')
    # print "____________________________________________________________"
    # print instance_id
    # instance_id = instance_id = data_id
    # print "controller hit" + id_string
    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    '''
    # approve related code
    qry = "select ns_label,ns_value from vwapprovaldef where document_name='logger_instance' and document_id='" + str(
        xform.id) + "' and current_state=(SELECT  status	FROM approval_instanceapproval where instance_id=" + str(
        instance_id) + " limit 1) and role_id in(select role_id::text from vwusermodule_userrolemap where auth_user_id=" + str(
        request.user.id) + ")"

    print  "+++++++++++++++++++++++++++++++++++++++++++"
    print qry
    cursor = connection.cursor()
    cursor.execute(qry)
    tmp_db_value = cursor.fetchall();
    cursor.close()
    json_data_response = []
    approvedef =[]

    if tmp_db_value is not None:
        for every in tmp_db_value:
            instance_data_json = {}
            # event_type = switch_event_type_label(str(every[1])) ,
            instance_data_json['ns_label'] = str(every[0])
            instance_data_json['ns_value'] = str(every[1])
            json_data_response.append(instance_data_json)
        approvedef = json.dumps(json_data_response)


    print "approvedef___________________________________________________"
    print approvedef
    '''
    # no access
    if not (xform.shared_data or can_view or
                    request.session.get('public_link') == xform.uuid):
        return HttpResponseForbidden(_(u'Not shared.'))

    audit = {
        "xform": xform.id_string,
    }
    audit_log(
        Actions.FORM_DATA_VIEWED, request.user, xform.user,
        _("Requested instance view for '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)

    # if can_edit:
    #     can_edit = check_additional_edit_perms(id_string)
    ################## data view code #######################
    prev_next_query = "SELECT * FROM( (SELECT id FROM logger_instance WHERE xform_id = (SELECT id FROM logger_xform where id_string = '" + id_string + "' LIMIT 1) AND user_id = " + str(
        request.user.id) + " AND id < " + instance_id + " ORDER BY id DESC LIMIT 1) UNION (SELECT id FROM logger_instance WHERE xform_id = (SELECT id FROM logger_xform where id_string = '" + id_string + "' LIMIT 1) AND user_id = " + str(
        request.user.id) + " AND id > " + instance_id + " ORDER BY id ASC LIMIT 1)) maybe_three_records ORDER BY id"
    # print " prev_next_query+++++++++++++++++++++++++++++"
    # print prev_next_query
    prev_next_data = json.dumps(__db_fetch_values(prev_next_query))

    form_title_query = "SELECT title FROM logger_xform where id_string = '" + id_string + "' LIMIT 1"
    form_title = __db_fetch_single_value(form_title_query)
    form_data_query = "SELECT * from get_instance_extracted_temp(" + instance_id + ")"
    # print "#######################"
    # print form_data_query
    #form_data_matrix = json.dumps(__db_fetch_values_dict(form_data_query))

    form_data_matrix = json.dumps(generate_form_data_matrix(instance_id))

    form_owner_query = "select (select username from auth_user where id = user_id) as owner from logger_xform where id_string = '" + str(
        id_string) + "'"
    form_owner = __db_fetch_single_value(form_owner_query)

    #   Get form and instance uuid

    instance_uuid = 0

    form_uuid = 0

    q = "select uuid instance_uuid,json->>'formhub/uuid' form_uuid from logger_instance where id  = "+str(instance_id)

    data = __db_fetch_values_dict(q)

    for temp in data:
        instance_uuid = temp['instance_uuid']
        form_uuid = temp['form_uuid']


    return render(request, 'instance.html', {
        'form_owner': form_owner,
        'prev_next_data': prev_next_data,
        'form_title': form_title,
        'form_data_matrix': form_data_matrix,
        'username': username,
        'id_string': id_string,
        'xform': xform,
        'can_edit': can_edit,
        'instance_id': instance_id,
        'instance_uuid' : instance_uuid,
        'form_uuid' : form_uuid
        #'approvedef': approvedef
    })



def generate_form_data_matrix(instance_id):
    form_data_query = """SELECT * from get_instance_extracted_temp(%s)""" % instance_id

    xform_id = __db_fetch_single_value("""select xform_id from instance.logger_instance where id = %s""" % instance_id)

    form_data_df = pandas.read_sql(form_data_query, connection)
    # csv_df = form_data_df[
    #     form_data_df['_a_title'].isnull() & form_data_df['_field_type'].isin(['select one', 'select all that apply'])]
    # non_csv_df = form_data_df[
    #     ~form_data_df['_a_title'].isnull() & form_data_df['_field_type'].isin(['select one', 'select all that apply'])]

    for csvidx, csvrow in form_data_df.iterrows():
        if csvrow['_a_title'] is None and csvrow['_field_type'] in ['select one', 'select all that apply']:
            try:
                datasource_id = __db_fetch_single_value("""
                with t1 as(with t as(
            select
                xform_id, json_array_elements(csv_config::json) as csv_config
            from
                core.xform_config_data xcd
            where
                xform_id = """+str(xform_id)+""")
            select
                csv_config->>'csv_name' as csv_name, csv_config->>'datasource_id' as datasource_id
            from
                t),
            t2 as(
            select
                field_name, substring(split_part(cntrl->>'appearance', ' ', 2) from '\''(.+)\''') as csv_name
            from
                instance.xform_extracted xe
            where
                xform_id = """+str(xform_id)+"""
                and field_type in ('select one', 'select all that apply')
                and split_part(cntrl->>'appearance', ' ', 2) like 'search%')
            select
                datasource_id
            from
                t2
            left join t1 on
                t1.csv_name = t2.csv_name
            where
                t2.field_name = '"""+str(csvrow['_field_name'])+"""'
                """)
                datasource_query = datasource_query_generate(datasource_id)
                datasource_df = pandas.read_sql(datasource_query, connection)
                lookup_vals = __db_fetch_values_dict(
                    """select value_text ,value_label::json->>'English' as value_label from "instance".xform_extracted xe where xform_id = """+str(xform_id)+""" and field_name = '"""+str(csvrow['_field_name'])+"""' limit 1""")
                datasource_df = datasource_df[[lookup_vals[0]['value_text'], lookup_vals[0]['value_label']]].drop_duplicates()
                # print csvrow['_field_value']
                # print type(csvrow['_field_value'])
                # print datasource_df
                # print type(datasource_df[lookup_vals[0]['value_text']].iloc[0])
                try:
                    _a_title_new = datasource_df[datasource_df[lookup_vals[0]['value_text']] == float(csvrow['_field_value'])][
                        lookup_vals[0]['value_label']].drop_duplicates().iloc[0]
                except Exception as ex:
                    try:
                        _a_title_new = datasource_df[datasource_df[lookup_vals[0]['value_text']] == int(csvrow['_field_value'])][
                            lookup_vals[0]['value_label']].drop_duplicates().iloc[0]
                    except Exception as ex1:
                        _a_title_new = datasource_df[datasource_df[lookup_vals[0]['value_text']] == csvrow['_field_value']][
                            lookup_vals[0]['value_label']].drop_duplicates().iloc[0]
                form_data_df.at[csvidx, '_a_title'] = json.dumps({
                    "Bangla": _a_title_new,
                    "English": _a_title_new
                })
            except Exception as ex3:
                pass

    return form_data_df.to_dict('r')



def charts(request, username, id_string):
    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)

    # no access
    if not (xform.shared_data or can_view or
            request.session.get('public_link') == xform.uuid):
        return HttpResponseForbidden(_(u'Not shared.'))

    try:
        lang_index = int(request.GET.get('lang', 0))
    except ValueError:
        lang_index = 0

    try:
        page = int(request.GET.get('page', 0))
    except ValueError:
        page = 0
    else:
        page = max(page - 1, 0)

    summaries = build_chart_data(xform, lang_index, page)

    if request.is_ajax():
        template = 'charts_snippet.html'
    else:
        template = 'charts.html'

    return render(request, template, {
        'xform': xform,
        'summaries': summaries,
        'page': page + 1
    })


def stats_tables(request, username, id_string):
    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared_data or can_view or
            request.session.get('public_link') == xform.uuid):
        return HttpResponseForbidden(_(u'Not shared.'))

    return render(request, 'stats_tables.html', {'xform': xform})


@require_http_methods(["GET"])
@login_required
def custom_data_view(request, username, id_string):
    ACTIVATE_CUSTOM_VIEW_QUERY = False
    # Query parameter must need to declare Column name using as clause.
    # In Query Make sure that instance id is fetched and it should be fetched in first parameter as select id, other column name from table.
    column_query = ''
    state_list = ''

    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)

    # if not has_permission(xform, owner, request):
    if not check_form_permissions(xform, str(request.user), 'can_view'):
        return HttpResponseForbidden(_(u'Not shared.'))

    cursor = connection.cursor()

    if str(request.user.id) == str(owner.id):
        state_list = "*"
    else:
        sqry = "select distinct current_state from vwrolestatuswiseformpermission where role_id in(select role_id::text from vwusermodule_userrolemap where auth_user_id=" + str(
            request.user.id) + ")"

        cursor.execute(sqry)
        fetchVal = cursor.fetchall();
        for eachval in fetchVal:
            if state_list == "":
                state_list = "'" + str(eachval[0]) + "'"
            else:
                state_list = state_list + "," + "'" + str(eachval[0]) + "'"

    if state_list != "" and state_list != "*":
        state_list = "(" + state_list + ")"

    submission_start = '%'
    submission_end = '%'
    submitted_by = '%'
    status = '%'
    submitter_id = 0

    if 'filter' in request.GET:
        filter_required = int(request.GET.get('filter'))
        # print ('incoming filter data:: ', filter_required)
    if 'start_date' in request.GET:
        submission_start = str(request.GET.get('start_date'))
    if 'end_date' in request.GET:
        submission_end = str(request.GET.get('end_date'))
    if 'submitted_by' in request.GET:
        submitted_by = str(request.GET.get('submitted_by'))
    if 'status' in request.GET:
        status = str(request.GET.get('status'))
        if submitted_by != 'custom':
            submitter_obj = get_object_or_404(User, username__iexact=submitted_by)
            submitter_id = submitter_obj.id
            # print ('submitter_id:: ', submitter_id)
    sub_query_user = ""
    sub_query_date_range = ""
    sub_query_status = ""

    if submitter_id != 0:
        sub_query_user += " AND vwlogger_instance.user_id = " + str(submitter_id)
    if submission_start and submission_end is not '%':
        sub_query_date_range += " AND vwlogger_instance.date_created BETWEEN '" + str(
            submission_start) + "' AND '" + str(submission_end) + "'"
    if status is not '%' and status != 'custom':
        sub_query_status += " AND app_inst.status = '" + str(status) + "'"

    if xform.id == 333:
        db_test_column_query = "logger_instance.id ID, logger_instance.user_id ,  to_char(logger_instance.date_created,'DD Mon YYYY') Received, logger_instance.json->>'hh_serial_number' Household"
        column_query = db_test_column_query
        ACTIVATE_CUSTOM_VIEW_QUERY = True
    elif xform.id == 400:
        db_test_column_query = "vwlogger_instance.id ID, vwlogger_instance.user_id ,vwlogger_instance.json->>'hh_id' household_id,  to_char(vwlogger_instance.date_created,'DD Mon YYYY') Received, app_inst.status ApprovalStatus"
        column_query = db_test_column_query
        ACTIVATE_CUSTOM_VIEW_QUERY = True
    elif xform.id == 402:
        db_test_column_query = "vwlogger_instance.id ID, vwlogger_instance.user_id,vwlogger_instance.json->>'school_name' school_name,to_char(vwlogger_instance.date_created,'DD Mon YYYY') Received, app_inst.status ApprovalStatus"
        column_query = db_test_column_query
        ACTIVATE_CUSTOM_VIEW_QUERY = True

    else:
        db_test_column_query = "vwlogger_instance.id ID, vwlogger_instance.user_id ,  to_char(vwlogger_instance.date_created,'DD Mon YYYY') Received, app_inst.status ApprovalStatus"
        column_query = db_test_column_query
        ACTIVATE_CUSTOM_VIEW_QUERY = True

    submission_instance_query = "SELECT " + column_query + " FROM vwlogger_instance LEFT JOIN approval_instanceapproval app_inst ON app_inst.instance_id = vwlogger_instance.id WHERE xform_id = " + str(
        xform.id) + str(sub_query_user) + str(sub_query_date_range) + str(sub_query_status)

    if state_list == "":
        submission_instance_query = submission_instance_query + " and app_inst.status =''"
    elif state_list != "*":
        submission_instance_query = submission_instance_query + " and app_inst.status in" + state_list

    print submission_instance_query
    data_list = []
    col_names = []

    try:
        if ACTIVATE_CUSTOM_VIEW_QUERY:

            cursor.execute(submission_instance_query)
            fetchVal = cursor.fetchall();
            col_names = [i[0] for i in cursor.description]
            col_names.append('details')

            for eachval in fetchVal:
                details_link = '/' + username + '/' + 'forms' + '/' + id_string + '/' + 'instance' + '/' + '?s_id=' + str(
                    eachval[0]) + '#/' + str(eachval[0])
                # details_link = '/' + username + '/' + 'forms' + '/' + id_string + '/' + 'instance/#/'+ str(eachval[0] )
                details_button = '<a class="btn red" href="' + details_link + '" role="button">Details</a>'
                eachval = eachval + (details_button,)
                data_list.append(list(eachval))
                # print ('Col Names:: ', col_names)
                # print ('Col Data', data_list)

    except Exception, e:
        if connection is not None:
            connection.rollback()
            print ('DB query error:: ', str(e))
            ACTIVATE_CUSTOM_VIEW_QUERY = False
    finally:
        if cursor is not None:
            cursor.close()
            ACTIVATE_CUSTOM_VIEW_QUERY = False
    return HttpResponse(json.dumps(
        {'col_name': col_names, 'data': data_list}), content_type='application/json')





def __db_fetch_values(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchall()
    cursor.close()
    return fetchVal


def __db_fetch_single_value(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    return fetchVal[0]


def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal

def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]
