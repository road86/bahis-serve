from datetime import date, datetime
import os
import pytz
import re
import tempfile
import traceback
from xml.dom import Node
from xml.parsers.expat import ExpatError

from dict2xml import dict2xml
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.storage import get_storage_class
from django.core.mail import mail_admins
from django.core.servers.basehttp import FileWrapper
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.signals import pre_delete
from django.http import HttpResponse, HttpResponseNotFound, \
    StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import DjangoUnicodeDecodeError
from django.utils.translation import ugettext as _
from django.utils import timezone
from modilabs.utils.subprocess_timeout import ProcessTimedOut
from pyxform.errors import PyXFormError
from pyxform.xform2json import create_survey_element_from_xml
import sys

from onadata.apps.main.models import UserProfile
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models.attachment import (
    generate_attachment_filename,
    hash_attachment_contents,
)
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.instance import (
    FormInactiveError,
    InstanceHistory,
    get_id_string_from_xml_str)
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.xform import XLSFormError
from onadata.apps.logger.xform_instance_parser import (
    InstanceEmptyError,
    InstanceInvalidUserError,
    InstanceMultipleNodeError,
    DuplicateInstance,
    clean_and_parse_xml,
    get_uuid_from_xml,
    get_deprecated_uuid_from_xml,
    get_submission_date_from_xml)
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import _remove_from_mongo,\
    xform_instances, ParsedInstance
from onadata.libs.utils import common_tags
from onadata.libs.utils.model_tools import queryset_iterator, set_uuid
from django.db import connection
import operator
#form parsing related
from onadata.apps.main.database_utility import __db_commit_query, __db_fetch_single_value
import pandas as pd
import operator
import json
# from onadata.apps.main.views import generate_insert_query
from onadata.apps.formmodule.form_tools import generate_insert_query
column_dict = {}





OPEN_ROSA_VERSION_HEADER = 'X-OpenRosa-Version'
HTTP_OPEN_ROSA_VERSION_HEADER = 'HTTP_X_OPENROSA_VERSION'
OPEN_ROSA_VERSION = '1.0'
DEFAULT_CONTENT_TYPE = 'text/xml; charset=utf-8'
DEFAULT_CONTENT_LENGTH = settings.DEFAULT_CONTENT_LENGTH

uuid_regex = re.compile(r'<formhub>\s*<uuid>\s*([^<]+)\s*</uuid>\s*</formhub>',
                        re.DOTALL)

mongo_instances = settings.MONGO_DB.instances


def _get_instance(xml, new_uuid, submitted_by, status, xform):
    # check if its an edit submission
    old_uuid = get_deprecated_uuid_from_xml(xml)
    instances = Instance.objects.filter(uuid=old_uuid)

    if instances:
        # edits
        check_edit_submission_permissions(submitted_by, xform)
        instance = instances[0]
        InstanceHistory.objects.create(
            xml=instance.xml, xform_instance=instance, uuid=old_uuid)
        instance.xml = xml
        instance._populate_xml_hash()
        instance.uuid = new_uuid
        instance.save()
    else:
        # new submission
        instance = Instance.objects.create(
            xml=xml, user=submitted_by, status=status, xform=xform)

    return instance


def dict2xform(jsform, form_id):
    dd = {'form_id': form_id}
    xml_head = u"<?xml version='1.0' ?>\n<%(form_id)s id='%(form_id)s'>\n" % dd
    xml_tail = u"\n</%(form_id)s>" % dd

    return xml_head + dict2xml(jsform) + xml_tail


def get_uuid_from_submission(xml):
    # parse UUID from uploaded XML
    split_xml = uuid_regex.split(xml)

    # check that xml has UUID
    return len(split_xml) > 1 and split_xml[1] or None


def get_xform_from_submission(xml, username, uuid=None):
        # check alternative form submission ids
        uuid = uuid or get_uuid_from_submission(xml)

        if not username and not uuid:
            raise InstanceInvalidUserError()

        if uuid:
            # try find the form by its uuid which is the ideal condition
            if XForm.objects.filter(uuid=uuid).count() > 0:
                xform = XForm.objects.get(uuid=uuid)

                return xform

        id_string = get_id_string_from_xml_str(xml)

        return get_object_or_404(XForm, id_string__exact=id_string,
                                 user__username=username)


def _has_edit_xform_permission(xform, user):
    if isinstance(xform, XForm) and isinstance(user, User):
        return user.has_perm('logger.change_xform', xform)

    return False


def check_edit_submission_permissions(request_user, xform):
    if xform and request_user and request_user.is_authenticated():
        requires_auth = UserProfile.objects.get_or_create(user=xform.user
            )[0].require_auth
        has_edit_perms = _has_edit_xform_permission(xform, request_user)

        if requires_auth and not has_edit_perms:
            raise PermissionDenied(
                _(u"%(request_user)s is not allowed to make edit submissions "
                  u"to %(form_user)s's %(form_title)s form." % {
                      'request_user': request_user,
                      'form_user': xform.user,
                      'form_title': xform.title}))


def check_submission_permissions(request, xform):
    """Check that permission is required and the request user has permission.

    The user does no have permissions iff:
        * the user is authed,
        * either the profile or the form require auth,
        * the xform user is not submitting.

    Since we have a username, the Instance creation logic will
    handle checking for the forms existence by its id_string.

    :returns: None.
    :raises: PermissionDenied based on the above criteria.
    """
    profile = UserProfile.objects.get_or_create(user=xform.user)[0]
    if request and (profile.require_auth or xform.require_auth
                    or request.path == '/submission')\
            and xform.user != request.user\
            and not request.user.has_perm('report_xform', xform):
        raise PermissionDenied(
            _(u"%(request_user)s is not allowed to make submissions "
              u"to %(form_user)s's %(form_title)s form." % {
                  'request_user': request.user,
                  'form_user': xform.user,
                  'form_title': xform.title}))


def save_attachments(instance, media_files):
    '''
    Returns `True` if any new attachment was saved, `False` if all attachments
    were duplicates or none were provided
    '''
    any_new_attachment = False
    for f in media_files:
        attachment_filename = generate_attachment_filename(instance, f.name)
        existing_attachment = Attachment.objects.filter(
            instance=instance,
            media_file=attachment_filename,
            mimetype=f.content_type,
        ).first()
        if existing_attachment and (existing_attachment.file_hash ==
                                    hash_attachment_contents(f.read())):
            # We already have this attachment!
            continue
        f.seek(0)
        # This is a new attachment; save it!
        Attachment.objects.create(
            instance=instance,
            media_file=f, mimetype=f.content_type)
        any_new_attachment = True
    return any_new_attachment


def save_submission(xform, xml, media_files, new_uuid, submitted_by, status,
                    date_created_override):
    if not date_created_override:
        date_created_override = get_submission_date_from_xml(xml)

    instance = _get_instance(xml, new_uuid, submitted_by, status, xform)

    save_attachments(instance, media_files)

    # override date created if required
    if date_created_override:
        if not timezone.is_aware(date_created_override):
            # default to utc?
            date_created_override = timezone.make_aware(
                date_created_override, timezone.utc)
        instance.date_created = date_created_override
        instance.save()

    if instance.xform is not None:
        pi, created = ParsedInstance.objects.get_or_create(
            instance=instance)

    if not created:
        pi.save(async=False)

    return instance


def update_schedule_status(scheduleid,instanceid):
    print("scheduleid*******************************************")
    print(scheduleid)
    qry="update schedule set status='DONE',updated_date=now(),submitted_instance_id=" + str(instanceid) + " where id="+str(scheduleid)+";"
    print qry
    cursor = connection.cursor()
    cursor.execute(qry)


@transaction.atomic # paranoia; redundant since `ATOMIC_REQUESTS` set to `True`
def create_instance(username, xml_file, media_files,
                    status=u'submitted_via_web', uuid=None,
                    date_created_override=None, request=None):
    """
    Submission cases:
        If there is a username and no uuid, submitting an old ODK form.
        If there is a username and a uuid, submitting a new ODK form.
    """
    instance = None
    user = get_object_or_404(User, username=username.lower())
    submitted_by = request.user \
        if request and request.user.is_authenticated() else user

    if username:
        username = username.lower()

    xml = xml_file.read()
    xml_hash = Instance.get_hash(xml)
    xform = get_xform_from_submission(xml, username, uuid)
    check_submission_permissions(request, xform)
    # get new and deprecated uuid's
    new_uuid = get_uuid_from_xml(xml)
    

    # Dorey's rule from 2012 (commit 890a67aa):
    #   Ignore submission as a duplicate IFF
    #    * a submission's XForm collects start time
    #    * the submitted XML is an exact match with one that
    #      has already been submitted for that user.
    if xform.has_start_time:
        # XML matches are identified by identical content hash OR, when a
        # content hash is not present, by string comparison of the full
        # content, which is slow! Use the management command
        # `populate_xml_hashes_for_instances` to hash existing submissions
        existing_instance = Instance.objects.filter(
             uuid=new_uuid,
            xform__user=xform.user,
        ).first()
    else:
        existing_instance = existing_instance = Instance.objects.filter(
             uuid=new_uuid,
            xform__user=xform.user,
        ).first()


    if existing_instance:
        # ensure we have saved the extra attachments
        any_new_attachment = save_attachments(existing_instance, media_files)
        if not any_new_attachment:
            raise DuplicateInstance()
        else:
            # Update Mongo via the related ParsedInstance
            existing_instance.parsed_instance.save(async=False)
            return existing_instance
    else:
        instance = save_submission(xform, xml, media_files, new_uuid,
                                   submitted_by, status,
                                   date_created_override)
        instanceid = instance.id
        generate_insert_query(xform.id, instanceid)
        return instance


def safe_create_instance(username, xml_file, media_files, uuid, request):
    """Create an instance and catch exceptions.

    :returns: A list [error, instance] where error is None if there was no
        error.
    """
    error = instance = None

    try:
        instance = create_instance(
            username, xml_file, media_files, uuid=uuid, request=request)
    except InstanceInvalidUserError:
        error = OpenRosaResponseBadRequest(_(u"Username or ID required."))
    except InstanceEmptyError:
        error = OpenRosaResponseBadRequest(
            _(u"Received empty submission. No instance was created")
        )
    except FormInactiveError:
        error = OpenRosaResponseNotAllowed(_(u"Form is not active"))
    except XForm.DoesNotExist:
        error = OpenRosaResponseNotFound(
            _(u"Form does not exist on this account")
        )
    except ExpatError as e:
        error = OpenRosaResponseBadRequest(_(u"Improperly formatted XML."))
    except DuplicateInstance:
        response = OpenRosaResponse(_(u"Duplicate submission"))
        response.status_code = 202
        response['Location'] = request.build_absolute_uri(request.path)
        error = response
    except PermissionDenied as e:
        error = OpenRosaResponseForbidden(e)
    except InstanceMultipleNodeError as e:
        error = OpenRosaResponseBadRequest(e)
    except DjangoUnicodeDecodeError:
        error = OpenRosaResponseBadRequest(_(u"File likely corrupted during "
                                             u"transmission, please try later."
                                             ))

    return [error, instance]


def report_exception(subject, info, exc_info=None):
    if exc_info:
        cls, err = exc_info[:2]
        message = _(u"Exception in request:"
                    u" %(class)s: %(error)s")\
            % {'class': cls.__name__, 'error': err}
        message += u"".join(traceback.format_exception(*exc_info))
    else:
        message = u"%s" % info

    if settings.DEBUG or settings.TESTING_MODE:
        sys.stdout.write("Subject: %s\n" % subject)
        sys.stdout.write("Message: %s\n" % message)
    else:
        mail_admins(subject=subject, message=message)


def response_with_mimetype_and_name(
        mimetype, name, extension=None, show_date=True, file_path=None,
        use_local_filesystem=False, full_mime=False):
    if extension is None:
        extension = mimetype
    if not full_mime:
        mimetype = "application/%s" % mimetype
    if file_path:
        try:
            if not use_local_filesystem:
                default_storage = get_storage_class()()
                wrapper = FileWrapper(default_storage.open(file_path))
                response = StreamingHttpResponse(wrapper,
                                                 content_type=mimetype)
                response['Content-Length'] = default_storage.size(file_path)
            else:
                wrapper = FileWrapper(open(file_path))
                response = StreamingHttpResponse(wrapper,
                                                 content_type=mimetype)
                response['Content-Length'] = os.path.getsize(file_path)
        except IOError:
            response = HttpResponseNotFound(
                _(u"The requested file could not be found."))
    else:
        response = HttpResponse(content_type=mimetype)
    response['Content-Disposition'] = disposition_ext_and_date(
        name, extension, show_date)
    return response


def disposition_ext_and_date(name, extension, show_date=True):
    if name is None:
        return 'attachment;'
    if show_date:
        name = "%s_%s" % (name, date.today().strftime("%Y_%m_%d"))
    return 'attachment; filename=%s.%s' % (name, extension)


def store_temp_file(data):
    tmp = tempfile.TemporaryFile()
    ret = None
    try:
        tmp.write(data)
        tmp.seek(0)
        ret = tmp
    finally:
        tmp.close()
    return ret


def publish_form(callback):
    try:
        return callback()
    except (PyXFormError, XLSFormError) as e:
        return {
            'type': 'alert-error',
            'text': unicode(e)
        }
    except IntegrityError as e:
        return {
            'type': 'alert-error',
            'text': _(u'Form with this id or SMS-keyword already exists.'),
        }
    except ValidationError as e:
        # on clone invalid URL
        return {
            'type': 'alert-error',
            'text': _(u'Invalid URL format.'),
        }
    except AttributeError as e:
        # form.publish returned None, not sure why...
        return {
            'type': 'alert-error',
            'text': unicode(e)
        }
    except ProcessTimedOut as e:
        # catch timeout errors
        return {
            'type': 'alert-error',
            'text': _(u'Form validation timeout, please try again.'),
        }
    except Exception as e:
        # TODO: Something less horrible. This masks storage backend
        # `ImportError`s and who knows what else

        # ODK validation errors are vanilla errors and it masks a lot of regular
        # errors if we try to catch it so let's catch it, BUT reraise it
        # if we don't see typical ODK validation error messages in it.
        if u"ODK Validate Errors" not in e.message:
            raise

        # error in the XLS file; show an error to the user
        return {
            'type': 'alert-error',
            'text': unicode(e)
        }


def publish_xls_form(xls_file, user, id_string=None):
    """ Creates or updates a DataDictionary with supplied xls_file,
        user and optional id_string - if updating
    """
    # get or create DataDictionary based on user and id string
    if id_string:
        dd = DataDictionary.objects.get(
            user=user, id_string=id_string)
        dd.xls = xls_file
        dd.save()
        return dd
    else:
        return DataDictionary.objects.create(
            user=user,
            xls=xls_file
        )


def publish_xml_form(xml_file, user, id_string=None):
    xml = xml_file.read()
    survey = create_survey_element_from_xml(xml)
    form_json = survey.to_json()
    if id_string:
        dd = DataDictionary.objects.get(user=user, id_string=id_string)
        dd.xml = xml
        dd.json = form_json
        dd._mark_start_time_boolean()
        set_uuid(dd)
        dd._set_uuid_in_xml()
        dd.save()
        return dd
    else:
        dd = DataDictionary(user=user, xml=xml, json=form_json)
        dd._mark_start_time_boolean()
        set_uuid(dd)
        dd._set_uuid_in_xml(file_name=xml_file.name)
        dd.save()
        return dd


class BaseOpenRosaResponse(HttpResponse):
    status_code = 201

    def __init__(self, *args, **kwargs):
        super(BaseOpenRosaResponse, self).__init__(*args, **kwargs)

        self[OPEN_ROSA_VERSION_HEADER] = OPEN_ROSA_VERSION
        tz = pytz.timezone(settings.TIME_ZONE)
        dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')
        self['Date'] = dt
        self['X-OpenRosa-Accept-Content-Length'] = DEFAULT_CONTENT_LENGTH
        self['Content-Type'] = DEFAULT_CONTENT_TYPE


class OpenRosaResponse(BaseOpenRosaResponse):
    status_code = 201

    def __init__(self, *args, **kwargs):
        super(OpenRosaResponse, self).__init__(*args, **kwargs)
        # wrap content around xml
        self.content = '''<?xml version='1.0' encoding='UTF-8' ?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="">%s</message>
</OpenRosaResponse>''' % self.content


class OpenRosaResponseNotFound(OpenRosaResponse):
    status_code = 404


class OpenRosaResponseBadRequest(OpenRosaResponse):
    status_code = 400


class OpenRosaResponseNotAllowed(OpenRosaResponse):
    status_code = 405


class OpenRosaResponseForbidden(OpenRosaResponse):
    status_code = 403


def inject_instanceid(xml_str, uuid):
    if get_uuid_from_xml(xml_str) is None:
        xml = clean_and_parse_xml(xml_str)
        children = xml.childNodes
        if children.length == 0:
            raise ValueError(_("XML string must have a survey element."))

        # check if we have a meta tag
        survey_node = children.item(0)
        meta_tags = [
            n for n in survey_node.childNodes
            if n.nodeType == Node.ELEMENT_NODE
            and n.tagName.lower() == "meta"]
        if len(meta_tags) == 0:
            meta_tag = xml.createElement("meta")
            xml.documentElement.appendChild(meta_tag)
        else:
            meta_tag = meta_tags[0]

        # check if we have an instanceID tag
        uuid_tags = [
            n for n in meta_tag.childNodes
            if n.nodeType == Node.ELEMENT_NODE
            and n.tagName == "instanceID"]
        if len(uuid_tags) == 0:
            uuid_tag = xml.createElement("instanceID")
            meta_tag.appendChild(uuid_tag)
        else:
            uuid_tag = uuid_tags[0]
        # insert meta and instanceID
        text_node = xml.createTextNode(u"uuid:%s" % uuid)
        uuid_tag.appendChild(text_node)
        return xml.toxml()
    return xml_str


def update_mongo_for_xform(xform, only_update_missing=True):
    instance_ids = set(
        [i.id for i in Instance.objects.only('id').filter(xform=xform)])
    sys.stdout.write("Total no of instances: %d\n" % len(instance_ids))
    mongo_ids = set()
    user = xform.user
    userform_id = "%s_%s" % (user.username, xform.id_string)
    if only_update_missing:
        sys.stdout.write("Only updating missing mongo instances\n")
        mongo_ids = set(
            [rec[common_tags.ID] for rec in mongo_instances.find(
                {common_tags.USERFORM_ID: userform_id},
                {common_tags.ID: 1})])
        sys.stdout.write("Total no of mongo instances: %d\n" % len(mongo_ids))
        # get the difference
        instance_ids = instance_ids.difference(mongo_ids)
    else:
        # clear mongo records
        mongo_instances.remove({common_tags.USERFORM_ID: userform_id})
    # get instances
    sys.stdout.write(
        "Total no of instances to update: %d\n" % len(instance_ids))
    instances = Instance.objects.only('id').in_bulk(
        [id for id in instance_ids])
    total = len(instances)
    done = 0
    for id, instance in instances.items():
        (pi, created) = ParsedInstance.objects.get_or_create(instance=instance)
        if not pi.save(async=False):
            print("\033[91m[ERROR] - Instance #{}/uuid:{} - Could not save the parsed instance\033[0m".format(
                id, instance.uuid))
        else:
            done += 1

        # if 1000 records are done, flush mongo
        if (done > 0 and done % 1000) == 0:
            sys.stdout.write(
                'Updated %d records, flushing MongoDB...\n' % done)
            settings.MONGO_CONNECTION.admin.command({'fsync': 1})

        progress = "\r%.2f %% done..." % ((float(done) / float(total)) * 100)
        sys.stdout.write(progress)
        sys.stdout.flush()
    # flush mongo again when done
    settings.MONGO_CONNECTION.admin.command({'fsync': 1})
    sys.stdout.write(
        "\nUpdated %s\n------------------------------------------\n"
        % xform.id_string)


def mongo_sync_status(remongo=False, update_all=False, user=None, xform=None):
    """Check the status of records in the mysql db versus mongodb. At a
    minimum, return a report (string) of the results.

    Optionally, take action to correct the differences, based on these
    parameters, if present and defined:

    remongo    -> if True, update the records missing in mongodb
                  (default: False)
    update_all -> if True, update all the relevant records (default: False)
    user       -> if specified, apply only to the forms for the given user
                  (default: None)
    xform      -> if specified, apply only to the given form (default: None)

    """

    qs = XForm.objects.only('id_string', 'user').select_related('user')
    if user and not xform:
        qs = qs.filter(user=user)
    elif user and xform:
        qs = qs.filter(user=user, id_string=xform.id_string)
    else:
        qs = qs.all()

    total = qs.count()
    found = 0
    done = 0
    total_to_remongo = 0
    report_string = ""
    for xform in queryset_iterator(qs, 100):
        # get the count
        user = xform.user
        instance_count = Instance.objects.filter(xform=xform).count()
        userform_id = "%s_%s" % (user.username, xform.id_string)
        mongo_count = mongo_instances.find(
            {common_tags.USERFORM_ID: userform_id}).count()

        if instance_count != mongo_count or update_all:
            line = "user: %s, id_string: %s\nInstance count: %d\t"\
                   "Mongo count: %d\n---------------------------------"\
                   "-----\n" % (
                       user.username, xform.id_string, instance_count,
                       mongo_count)
            report_string += line
            found += 1
            total_to_remongo += (instance_count - mongo_count)

            # should we remongo
            if remongo or (remongo and update_all):
                if update_all:
                    sys.stdout.write(
                        "Updating all records for %s\n--------------------"
                        "---------------------------\n" % xform.id_string)
                else:
                    sys.stdout.write(
                        "Updating missing records for %s\n----------------"
                        "-------------------------------\n"
                        % xform.id_string)
                update_mongo_for_xform(
                    xform, only_update_missing=not update_all)
        done += 1
        sys.stdout.write(
            "%.2f %% done ...\r" % ((float(done) / float(total)) * 100))
    # only show stats if we are not updating mongo, the update function
    # will show progress
    if not remongo:
        line = "Total # of forms out of sync: %d\n" \
            "Total # of records to remongo: %d\n" % (found, total_to_remongo)
        report_string += line
    return report_string


def remove_xform(xform):
    # disconnect parsed instance pre delete signal
    pre_delete.disconnect(_remove_from_mongo, sender=ParsedInstance)

    # delete instances from mongo db
    query = {
        ParsedInstance.USERFORM_ID:
        "%s_%s" % (xform.user.username, xform.id_string)}
    xform_instances.remove(query, j=True)
    # delete from study_form and form_version
    '''
    del_study_q = "delete from study_form where form_id = "+str(xform.id)
    cursor = connection.cursor()
    cursor.execute(del_study_q)
    # connection.commit()
    cursor.close()
    del_version_q = "delete from form_version where form_id = " + str(xform.id)
    cursor = connection.cursor()
    cursor.execute(del_version_q)
    # connection.commit()
    cursor.close()
    '''
    # delete xform, and all related models
    xform.delete()

    # reconnect parsed instance pre delete signal?
    pre_delete.connect(_remove_from_mongo, sender=ParsedInstance)



def get_xform_list(username):
    frm_qry="select xform_id from vwrolewiseformpermission where username='"+str(username)+"'"

    cursor = connection.cursor()
    cursor.execute(frm_qry)
    tmp_db_value = cursor.fetchall()
    frm_list=[]

    if tmp_db_value is not None:
        for every in tmp_db_value:
            frm_list.append(every[0])

    if len(frm_list) == 0:
        xforms=[]
    else:
        xforms = XForm.objects.filter(reduce(operator.or_, [Q(id=c) for c in frm_list]))
    cursor.close()
    #print "###333333xform permission#######3333"
    #print frm_qry
    #print frm_list
    #print xforms
    return xforms

def check_form_permissions(xform,username,permission_type):
    frm_qry="select "+ permission_type +" from vwrolewiseformpermission where xform_id="+str(xform.id)+" and username='"+str(username)+"'"
    cursor = connection.cursor()
    cursor.execute(frm_qry)
    tmp_db_value = cursor.fetchall()
    frm_list=[]
    cursor.close()
    if tmp_db_value is not None:
        for every in tmp_db_value:
            if str(every[0])=="1":
                return True
            else:
                return False
    else:
        return False


def get_form_permissions(xform_id_string,username,logged_user):
    can_view=False
    can_submit=False
    can_edit=False
    can_delete=False
    can_setting=False

    frm_qry="SELECT can_view,can_submit,can_edit,can_delete,can_setting FROM vwrolewiseformpermission where id_string='"+str(xform_id_string)+"' and username='"+str(logged_user)+"'"

    cursor = connection.cursor()
    cursor.execute(frm_qry)
    tmp_db_value = cursor.fetchall()
    frm_list=[]
    cursor.close()
    if tmp_db_value is not None:
        for every in tmp_db_value:
            if str(every[0])=="1":
                can_view=True
            if str(every[1])=="1":
                can_submit=True
            if str(every[2])=="1":
                can_edit=True
            if str(every[3])=="1":
                can_delete=True
            if str(every[4])=="1":
                can_setting=True


    #xform = XForm.objects.get(id_string__exact=xform_id_string)
    xform = get_object_or_404(XForm, user__username__iexact=username, id_string__exact=xform_id_string)


    return xform,can_setting,can_edit,can_view,can_submit,can_delete


# #----------------- Data parse ----------------


# def generate_insert_query( xform_id,instance_id):
#     global column_dict

#     get_form_data(xform_id,instance_id)
#     print "Here Final Dict all"
#     print column_dict
#     col_list = []
#     val_list = []
#     for key in column_dict.keys():
#         value = column_dict[key]
#         table_name = key
#         if 'columns' in value:
#             value_dict = value['columns']
#             for col in value_dict:
#                 col_list.append(col)
#                 val_list.append(value_dict[col])

#             col_list.append('instanceid')
#             val_list.append(str(instance_id))
#             col_string = ','.join(col_list)
#             val_string = ','.join("'" + x + "'" for x in val_list)
#             query_string = "insert into " + table_name + " (" + col_string + ") values(" + val_string + ")"
#             print query_string
#             __db_commit_query(query_string)


#             if 'children' in value:
#                 data_id = __db_fetch_single_value(
#                     "select id from " + table_name + " where instanceid ='%s' " % (str(instance_id)))
#                 child_list = value['children']
#                 for child in child_list:

#                     for k in child.keys():
#                         child_table_name = k
#                         child_col_list = []
#                         child_val_list = []
#                         child_data = child[k]
#                         for col_name in child_data:
#                             if col_name == 'parent':
#                                 child_col_list.append(child_data[col_name])
#                                 child_val_list.append(str(data_id))
#                             else:
#                                 child_col_list.append(col_name)
#                                 child_val_list.append(child_data[col_name])

#                         col_string = ','.join(child_col_list)
#                         val_string = ','.join("'" + x + "'" for x in child_val_list)
#                         query_string = "insert into " + child_table_name + " (" + col_string + ") values(" + val_string + ")"
#                         print query_string
#                         __db_commit_query(query_string)


# def get_form_data(xform_id,instance_id):
#     global column_dict
#     column_dict = {}
#     form_data = pd.read_sql("select id_string,json from logger_xform where id = " + str(xform_id), connection)
#     form_def = json.loads(form_data.iloc[0]['json'])
#     form_id_string = form_data.iloc[0]['id_string']
#     form_elements = form_def['children']
#     data = pd.read_sql("select json from logger_instance where id = " + str(instance_id), connection)
#     data_json = data.iloc[0]['json']
#     create_query_script(form_elements,data_json,form_id_string)


# def update_column_dict(table_cols,form_id_string, parent):
#     global column_dict
#     print table_cols, form_id_string, parent
#     parent_table_name = 'bahis_' + str(form_id_string) + '_table'

#     if parent!='':
#         child_table_name = 'bahis_' + str(form_id_string) + '_' + parent + '_table'
#         table_cols['parent'] = form_id_string+'_id'
#         child_dict = {child_table_name: table_cols}
#         if parent_table_name in column_dict:
#             if 'children' in column_dict[parent_table_name]:
#                 column_dict[parent_table_name]['children'].append(child_dict)
#             else:
#                 column_dict[parent_table_name]['children'] = []
#                 column_dict[parent_table_name]['children'].append(child_dict)
#         else:
#             column_dict[parent_table_name] = {}
#             column_dict[parent_table_name]['children'] = []
#             column_dict[parent_table_name]['children'].append(child_dict)
#     else:
#         if parent_table_name in column_dict:
#             column_dict[parent_table_name]['columns']=table_cols
#         else:
#             column_dict[parent_table_name] = {}
#             column_dict[parent_table_name]['columns'] = table_cols


# def create_query_script(form_elements, data_json, form_id_string, **kwargs):
#     """
#         Recursive function for parsing form data

#         Parameters
#         ----------
#         form_elements : `list`
#             List of form elements
#         data_json : `json`
#             Form Data json
#         form_id_string : `str`,
#             Form id string

#         **kwargs Parameters
#         ----------------
#         parent : `str`, optional
#             parent table name for establishing the link
#         group_name : `str`, optional
#             parent group name for parsing data
#     """
#     table_cols = {}
#     parent = ''
#     group_name = ''
#     table_string = ''
#     if kwargs.has_key('parent'):
#         parent = kwargs['parent']
#     if kwargs.has_key('group_name'):
#         group_name = kwargs['group_name']

#     key_name = parent + '/' if parent != '' else ''
#     key_name = group_name + '/'+key_name if group_name !='' else ''+key_name

#     for form_element in form_elements:
#         if form_element['type'] != 'repeat' and form_element['type'] != 'group':
#             if form_element['name'] != 'end' and form_element['name'] != 'start':
#                 if key_name + form_element['name'] in data_json:
#                     table_cols[form_element['name']] = data_json[key_name + form_element['name']]
#         else:
#             if form_element['type'] == 'repeat':
#                 print form_element['name']
#                 if key_name + form_element['name'] in data_json:
#                     data_list = data_json[form_element['name']]
#                     for data in data_list:
#                         create_query_script(form_element['children'], data, form_id_string,
#                                         parent=form_element['name'])
#             elif form_element['type'] == 'group':
#                 group_parent = form_element['name']
#                 for fc in form_element['children']:
#                     field_name = key_name + group_parent + '/' + fc['name']
#                     if fc['type'] != 'repeat':
#                         if field_name in data_json:
#                             table_cols[form_element['name']+'_'+fc['name']] = data_json[field_name]
#                     else:
#                         if field_name in data_json:
#                             data_list = data_json[field_name]
#                             for data in data_list:
#                                 create_query_script(fc['children'], data, form_id_string,
#                                                 parent=fc['name'],group_name=form_element['name'])

#     update_column_dict(table_cols, form_id_string, parent)

    update_column_dict(table_cols, form_id_string, parent)

# #----------------- Data parse ----------------

