import re
import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django.utils.decorators import method_decorator
from django.db import transaction

from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.authentication import (
    BasicAuthentication,
    TokenAuthentication,
    SessionAuthentication,)
from rest_framework.response import Response
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.mixins.openrosa_headers_mixin import OpenRosaHeadersMixin
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.data_serializer import SubmissionSerializer
from onadata.libs.utils.logger_tools import dict2xform, safe_create_instance


#FormBuilder related import
import pandas
from collections import OrderedDict
from django.db import connection
from django.http import (
    HttpResponseRedirect, HttpResponse , Http404)
import os
import zipfile
import StringIO
import json

# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)
xml_error_re = re.compile('>(.*)<')


def is_json(request):
    return 'application/json' in request.content_type.lower()


def dict_lists2strings(d):
    """Convert lists in a dict to joined strings.

    :param d: The dict to convert.
    :returns: The converted dict."""
    for k, v in d.items():
        if isinstance(v, list) and all([isinstance(e, basestring) for e in v]):
            d[k] = ' '.join(v)
        elif isinstance(v, dict):
            d[k] = dict_lists2strings(v)

    return d


def create_instance_from_xml(username, request):
    xml_file_list = request.FILES.pop('xml_submission_file', [])
    xml_file = xml_file_list[0] if len(xml_file_list) else None
    media_files = request.FILES.values()

    return safe_create_instance(username, xml_file, media_files, None, request)


def create_instance_from_json(username, request):
    request.accepted_renderer = JSONRenderer()
    request.accepted_media_type = JSONRenderer.media_type
    dict_form = request.data
    submission = dict_form.get('submission')

    if submission is None:
        # return an error
        return [_(u"No submission key provided."), None]

    # convert lists in submission dict to joined strings
    submission_joined = dict_lists2strings(submission)
    xml_string = dict2xform(submission_joined, dict_form.get('id'))

    xml_file = StringIO.StringIO(xml_string)

    return safe_create_instance(username, xml_file, [], None, request)


class XFormSubmissionApi(OpenRosaHeadersMixin,
                         mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
Implements OpenRosa Api [FormSubmissionAPI](\
    https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI)

## Submit an XML XForm submission

<pre class="prettyprint">
<b>POST</b> /api/v1/submissions</pre>
> Example
>
>       curl -X POST -F xml_submission_file=@/path/to/submission.xml \
https://example.com/api/v1/submissions

## Submit an JSON XForm submission

<pre class="prettyprint">
<b>POST</b> /api/v1/submissions</pre>
> Example
>
>       curl -X POST -d '{"id": "[form ID]", "submission": [the JSON]} \
http://localhost:8000/api/v1/submissions -u user:pass -H "Content-Type: \
application/json"

Here is some example JSON, it would replace `[the JSON]` above:
>       {
>           "transport": {
>               "available_transportation_types_to_referral_facility": \
["ambulance", "bicycle"],
>               "loop_over_transport_types_frequency": {
>                   "ambulance": {
>                       "frequency_to_referral_facility": "daily"
>                   },
>                   "bicycle": {
>                       "frequency_to_referral_facility": "weekly"
>                   },
>                   "boat_canoe": null,
>                   "bus": null,
>                   "donkey_mule_cart": null,
>                   "keke_pepe": null,
>                   "lorry": null,
>                   "motorbike": null,
>                   "taxi": null,
>                   "other": null
>               }
>           }
>           "meta": {
>               "instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
>           }
>       }
"""
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = Instance
    permission_classes = (permissions.AllowAny,)
    renderer_classes = (TemplateXMLRenderer,
                        JSONRenderer,
                        BrowsableAPIRenderer)
    serializer_class = SubmissionSerializer
    template_name = 'submission.xml'

    def __init__(self, *args, **kwargs):
        super(XFormSubmissionApi, self).__init__(*args, **kwargs)
        # Respect DEFAULT_AUTHENTICATION_CLASSES, but also ensure that the
        # previously hard-coded authentication classes are included first.
        # We include BasicAuthentication here to allow submissions using basic
        # authentication over unencrypted HTTP. REST framework stops after the
        # first class that successfully authenticates, so
        # HttpsOnlyBasicAuthentication will be ignored even if included by
        # DEFAULT_AUTHENTICATION_CLASSES.
        authentication_classes = [
            DigestAuthentication,
            BasicAuthentication,
            TokenAuthentication
        ]
        # Do not use `SessionAuthentication`, which implicitly requires CSRF prevention
        # (which in turn requires that the CSRF token be submitted as a cookie and in the
        # body of any "unsafe" requests).
        self.authentication_classes = authentication_classes + [
            auth_class for auth_class in self.authentication_classes
                if not auth_class in authentication_classes and \
                    not issubclass(auth_class, SessionAuthentication)
        ]

    def create(self, request, *args, **kwargs):
        username = self.kwargs.get('username')
        

        if self.request.user.is_anonymous():
            if username is None:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)
            else:
                user = get_object_or_404(User, username=username.lower())

                profile, created = UserProfile.objects.get_or_create(user=user)

                if profile.require_auth:
                    # raises a permission denied exception,
                    # forces authentication
                    self.permission_denied(self.request)
        elif not username:
            # get the username from the user if not set
            username = (request.user and request.user.username)

        if request.method.upper() == 'HEAD':
            return Response(status=status.HTTP_204_NO_CONTENT,
                            headers=self.get_openrosa_headers(request),
                            template_name=self.template_name)

        is_json_request = is_json(request)

        error, instance = (create_instance_from_json if is_json_request else
                           create_instance_from_xml)(username, request)

        if error or not instance:
            return self.error_response(error, is_json_request, request)

        context = self.get_serializer_context()
        serializer = SubmissionSerializer(instance, context=context)

        return Response({
            'formid': instance.xform.id_string,
            'encrypted': instance.xform.encrypted,
            'instanceID': u'uuid:%s' % instance.uuid,
            'submissionDate': instance.date_created.isoformat(),
            'markedAsCompleteDate': instance.date_modified.isoformat()},
                        headers=self.get_openrosa_headers(request),
                        status=status.HTTP_201_CREATED,
                        template_name=self.template_name)

    def error_response(self, error, is_json_request, request):
        if not error:
            error_msg = _(u"Unable to create submission.")
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(error, basestring):
            error_msg = error
            status_code = status.HTTP_400_BAD_REQUEST
        elif not is_json_request:
            return error
        else:
            error_msg = xml_error_re.search(error.content).groups()[0]
            status_code = error.status_code

        return Response({'error': error_msg},
                        headers=self.get_openrosa_headers(request),
                        status=status_code)


    # ---------- FormBuilder Related code

    def get_form_attribute(self, request, *args, **kwargs):
        """
        This function is to render form related necessary Data
        """
        print("inside get_form_attribute *********")
        data = request.data
        print(data)
        form_id = data['id']
        url = data['url']
        username = data['username']
        preset_data = data

        if 'username' in data:
            preset_data['username'] = data['username']
        # get returnee id
        if 'instance_id' in data:
            instance_id = data['instance_id']
        else:
            instance_id = "-1"

        print instance_id
        # ------------Do not delete -------------#
        # csv_path = '/get_all_csv'
        # if form_id == '716':
        #     csv_path = '/get_group_event_form_csv'
        # csv_url = "http://" + url + "/" + username + csv_path
        # ------------Do not delete -------------#

        submission_url = "http://" + url + "/" + username + "/submission"
        csv_url = "http://" + url + "/bhmodule/get-datasource-csv/"+str(form_id)+"/"
        csv_exists = self.__db_fetch_single_value("select json_array_elements(csv_config::json) from core.xform_config_data xcd where xform_id = "+str(form_id))
        try:
            qry = "select json::json,uuid,id_string from logger_xform where id =" + str(form_id)
            data = self.__db_fetch_values_dict(qry)[0]
            data['submission_url'] = submission_url
            if csv_exists:
                data['csv'] = csv_url
            if str(instance_id) != "-1":
                qry_data = "select id,json from logger_instance where id =" + str(instance_id)
                print
                "##################################################################"
                print
                qry_data
                data_ins = self.__db_fetch_values_dict(qry_data)
                if len(data_ins) > 0:
                    data_json = data_ins[0]['json']
                    print(data_json)
                    data['data_json'] = self.kobo_to_formBuilder_json(data_json, {}, "")
            else:
                # get_preloaded_json(form_id,returnee_id)
                # data['data_json']={"beneficiary_id": "JhaRaj001","medical_support": {"disease": "1"}}


                data['data_json'] = self.get_preloaded_json(form_id, preset_data)
                for key in request.data.iterkeys():
                    print(key)
                    if key not in ['username','id','url','']:
                        data['data_json'][key] = request.data[key]
            response = HttpResponse(json.dumps(data))
            response["Access-Control-Allow-Origin"] = "*"
            return response

        except Exception as e:
            print(e)
            return HttpResponse(status=404)

    # ---------- FormBuilder Related code

    def get_preloaded_json(self, form_id, preset_data):
        """
            This function injects preloaded Data in the json
        """
        json = {}
        print("in preset")
        if 'institution_id' in preset_data:
            print(preset_data['institution_id'])
            json['info'] = {'institution_id': str(preset_data['institution_id'])}
        json['username'] = str(preset_data['username'])
        return json


    def get_all_csv(self, request, *args, **kwargs):
        """
        This Function is to render Form Related Data in CSV Format
        """
        print("inside get_all_csv *********")
        username = self.kwargs.get('username')
        # user_path_filename = os.path.join(settings.MEDIA_ROOT, username)
        user_path_filename = os.path.join(settings.MEDIA_ROOT, 'formid-media')
        if not os.path.isdir(user_path_filename):
            os.makedirs(user_path_filename)
        query = "select div_code as division_code, div_name as division_name, " \
            "dist_code as district_code, dist_name as district_name, " \
            "upazila_code, upazila_name , union_code, union_name from vwgeo_data"
        geo_df = pandas.read_sql(query, connection)
        final_path_event = user_path_filename + '/geo.csv'
        geo_df.to_csv(final_path_event, encoding='utf-8', index=False)


        try:
            list_of_files = os.listdir(user_path_filename)

        except Exception as e:
            print(e)
            return HttpResponse(status=404)

        print(list_of_files)
        print(user_path_filename)
        zip_subdir = "itemsetfiles"
        zip_filename = "%s.zip" % zip_subdir
        s = StringIO.StringIO()
        # The zip compressor
        zf = zipfile.ZipFile(s, "w")
        for fpath in list_of_files:
            # Calculate path for file in zip
            fpath = user_path_filename + '/' + fpath
            print(fpath)
            if os.path.exists(fpath):
                fdir, fname = os.path.split(fpath)
                zip_path = os.path.join(zip_subdir, fname)
                print(zip_path)
                # Add file, at correct path
                zf.write(fpath, fname)
        # Must close zip for all contents to be written
        zf.close()
        # Grab ZIP file from in-memory, make response with correct MIME-type
        resp = HttpResponse(s.getvalue(), content_type="application/x-zip-compressed")
        # ..and correct content-disposition
        resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
        resp["Access-Control-Allow-Origin"] = "*"
        return resp


    def send_option(self, request, *args, **kwargs):
        print("inside options *******************************")
        # if request.method.upper() == 'HEAD':
        access_control_headers = request.META['HTTP_ACCESS_CONTROL_REQUEST_HEADERS']
        response = HttpResponse(200)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST"
        response["Access-Control-Allow-Headers"] = access_control_headers
        response["Access-Control-Allow-Credentials"] = False
        return response


    def dictfetchall(self, cursor):
        desc = cursor.description
        return [
            OrderedDict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()]


    def __db_fetch_values_dict(self, query):
        cursor = connection.cursor()
        cursor.execute(query)
        fetchVal = self.dictfetchall(cursor)
        cursor.close()
        return fetchVal

    def __db_fetch_single_value(self, query):
        cursor = connection.cursor()
        cursor.execute(query)
        fetchVal = cursor.fetchone()
        cursor.close()
        if fetchVal:
            return fetchVal[0]
        else:
            return None


    def convert_array_json(self, array_json, upto_name=""):
        tmp = []
        for obj in array_json:
            tmp.append(self.kobo_to_formBuilder_json(obj, {}, upto_name))
        return tmp


    def kobo_to_formBuilder_json(self, kobo_json, form_builder_json={}, upto_name=""):
        for key in sorted(kobo_json.keys()):
            # print(key)
            key = str(key)
            if upto_name == "":
                current_hierchical_name = key
            else:
                current_hierchical_name = key[len(upto_name) + 1:]
            split_hierchical_name = current_hierchical_name.split('/')
            if (len(split_hierchical_name) == 1):
                if type(kobo_json[key]) != list:
                    form_builder_json[split_hierchical_name[-1]] = kobo_json[key]
                else:
                    form_builder_json[split_hierchical_name[-1]] = self.convert_array_json(kobo_json[key], key)
            elif (len(split_hierchical_name) > 1):
                tmp = form_builder_json
                for x in split_hierchical_name:
                    if x not in tmp:
                        tmp[x] = {}
                    if x == split_hierchical_name[-1]:
                        if type(kobo_json[key]) != list:
                            tmp[x] = kobo_json[key]
                        else:
                            tmp[x] = self.convert_array_json(kobo_json[key], key)
                    else:
                        tmp = tmp[x]
                        # print(form_builder_json)
        return form_builder_json
