# coding: utf-8

from __future__ import (unicode_literals, print_function, absolute_import,
                        division)

from collections import OrderedDict
from django.db import connection
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json
import decimal
from onadata.apps.main.database_utility import __db_fetch_single_value, \
    __db_commit_query, __db_fetch_values
from django.views.decorators.csrf import csrf_exempt




@login_required
def index(request):
    """
        Test Function for module

        Args:
            request (str): Default Django request Object

        Returns:
            Render Html
    """
    return render(request, 'formmodule/index.html')



@login_required
def get_form(request, form_id):
    """
        Function for rendering odk forms from form parser through iFrame

        Args:
            request (str): Default Django request Object
            id_string (str): form id_string
        Returns:
            Render iFrame within Html
    """
    username = request.user
    # if in local environment, you should use your ip instead of localhost
    # server_address = request.META.get('ip')+':'+request.META.get('HTTP_HOST').split(':', 1)[1]
    # when in developement/live/client server
    server_address = request.META.get('HTTP_HOST')
    # parse request param
    request_param = request.GET.dict()
    # server_address = '192.168.22.133:8001'
    print(server_address)
    # form_builder_server = __db_fetch_single_value("select form_builder_server from form_builder_configuration")
    # form_id = __db_fetch_single_value("select id from logger_xform where id_string='" + id_string + "'")
    form_builder_server = 'http://192.168.19.16:9991'
    return render(request, 'formmodule/form.html',
                  {'username': username, 'server_address': server_address, 'form_id': int(form_id),
                   'form_builder_server': form_builder_server, 'request_param': json.dumps(request_param)})



def edit_data(request, username, id_string, data_id):
    # username = request.user
    # if in local environment, you should use your ip instead of localhost
    # server_address = request.META.get('ip')+':'+request.META.get('HTTP_HOST').split(':', 1)[1]
    # when in developement/live/client server
    server_address = request.META.get('HTTP_HOST')
    print(server_address)
    form_id = __db_fetch_single_value("select id from logger_xform where id_string='"+id_string+"'")
    form_builder_server = __db_fetch_single_value("select form_builder_server from form_builder_configuration")
    print(form_builder_server)
    instance_id = data_id
    redirected_url = '/'+username+'/forms/'+id_string+'/instance/?s_id='+instance_id+'#/'+instance_id
    form_builder_server = 'http://192.168.19.16:9991'
    print (instance_id)
    return render(request, 'formmodule/edit_form.html',{'username':username,'server_address':server_address,
                                                   'form_id':form_id,'form_builder_server':form_builder_server,
                                                   'instance_id':instance_id,'redirected_url':redirected_url})





