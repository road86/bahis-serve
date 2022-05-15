from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Count,Q
from django.http import (
    HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext,loader
from django.contrib.auth.models import User
from datetime import date, timedelta, datetime
# from django.utils import simplejson
import json
import logging
import sys
from django.core.urlresolvers import reverse
import pandas
from collections import OrderedDict

from django.db import (IntegrityError,transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect
import StringIO
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
# Menu imports
from onadata.apps.usermodule.forms import MenuForm
from onadata.apps.usermodule.models import MenuItem
# Unicef Imports
from onadata.apps.logger.models import Instance,XForm
# Organization Roles Import
from onadata.apps.usermodule.models import OrganizationRole,MenuRoleMap,UserRoleMap
from onadata.apps.usermodule.forms import OrganizationRoleForm,RoleMenuMapForm,UserRoleMapForm,UserRoleMapfForm
from django.forms.models import inlineformset_factory,modelformset_factory
from django.forms.formsets import formset_factory

from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.shortcuts import render
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os
import pandas as pd
import requests
import csv
#from onadata.apps.bh_module.views import datasource_query_generate
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin,UserBranch
import xml.etree.ElementTree as ET
from onadata.apps.main.database_utility  import __db_fetch_values_dict,__db_fetch_values,__db_fetch_single_value,__db_commit_query,__db_insert_query
# file zip related import
import zipfile
import StringIO
from onadata.apps.bh_module.utility_functions import datasource_query_generate
from onadata.apps.bh_module import utility_functions

datasource_type = [['2', 'Datasource'], ['1', 'Table']]
#----------------------------- Form Related ---------------------


@login_required
def form_settings(request, username, id_string):
    """This function renders form settings

    Args:
        request ([GET]): [description]
        username ([string]): [requested user's username]
        id_string ([string]): [Form Id String]

    Returns:
        [html]: [html with context data]
    """
    xform = XForm.objects.get(id_string__exact=id_string)
    selective_columns = __db_fetch_values("select distinct(field_name) from xform_extracted where xform_id = "+str(xform.id)+" and field_type = any (array['select all that apply','select one'])")
    datasource_list = __db_fetch_values("select id||'@'||title, title from datasource_definition")
    datasource = __db_fetch_values_dict("select id, title from datasource_definition")
    table_list = __db_fetch_values_dict("SELECT table_name,table_name as \"name\" FROM "
                                        "information_schema.tables WHERE table_type='BASE TABLE' AND table_schema='core' ")
    # form_column_list =
    info_dict={'datasource_choices':json.dumps(datasource),'table_choices':json.dumps(table_list),'datasource_type_choices': datasource_type,'selective_columns':selective_columns,'csvsource_choices': datasource_list,'xform_id':xform.id}

    template = loader.get_template('forms/form_settings.html')
    context = RequestContext(request, info_dict)

    return HttpResponse(template.render(context))


@csrf_exempt
def update_form_csv(request, xform_id):
    """This function manages form Related csv configuration

    Args:
        request ([POST/GET]):
        xform_id ([type]): [requested forms id]

    Returns:
        [response]: [operation status with code]
    """
    csv_config = __db_fetch_single_value("select csv_config from xform_config_data where xform_id=" + xform_id)
    post_dict = request.POST
    edited = post_dict['flag']
    csv_name = post_dict['csv_name']
    # attribute_name = post_dict['attribute_name']
    datasource = post_dict['datasource_name'].split('@')
    new_config = []

    if edited == 'add':
        if csv_config is not None:
            new_config = json.loads(csv_config)
        new_config.append({'csv_name': csv_name,  'datasource_id': datasource[0],
                           'datasource_title': datasource[1]})

    else:
        config = json.loads(csv_config)
        for c in config:
            if c['csv_name'] != csv_name and c['datasource_id'] != datasource[0] and c['datasource_title'] != datasource[1]:
                new_config.append(
                    {'csv_name': c['csv_name'],  'datasource_id': c['datasource_id'],
                     'datasource_title': c['datasource_title']})
    print new_config
    update_query = "update xform_config_data set updated_at=now(), updated_by ='" + request.user.username + "' ,csv_config = '" + json.dumps(
        new_config) + "' where xform_id =" + xform_id
    __db_commit_query(update_query)
    return HttpResponse('success', status=200)


@csrf_exempt
def add_form_data_embed(request, xform_id):
    # csv_config = __db_fetch_single_value("select csv_config from xform_config_data where xform_id="+xform_id)
    post_dict = request.POST
    print
    post_dict
    # edited= post_dict['flag']
    # csv_name = post_dict['csv_name']
    # attribute_name = post_dict['attribute_name']
    # datasource = post_dict['datasource_name'].split('@')
    # new_config = []

    # if edited=='add':
    #     if csv_config is not None:
    #         new_config = json.loads(csv_config)
    #     new_config.append({'csv_name':csv_name,'attribute_name': attribute_name, 'datasource_id': datasource[0], 'datasource_title': datasource[1]})

    # else:
    #     config = json.loads(csv_config)
    #     for c in config:
    #         if c['csv_name']!=csv_name and c['attribute_name']!=attribute_name and c['datasource_id']!=datasource[0] and c['datasource_title']!= datasource[1]:
    #             new_config.append({'csv_name':csv_name,'attribute_name': attribute_name, 'datasource_id': datasource[0], 'datasource_title': datasource[1]})

    # update_query = "update xform_config_data set updated_at=now(), updated_by ='" + request.user.username + "' ,csv_config = '" + json.dumps(
    #         new_config) + "' where xform_id =" + xform_id
    # __db_commit_query(update_query)
    # return HttpResponse('success', status=200)


@csrf_exempt
def form_csv_config_list(request, xform_id):
    """this function gets csv config list of a form

    Args:
        request ([GET]): [description]
        xform_id ([int]): [Form id]

    Returns:
        [json]: [csv config json of a form]
    """
    csv_config = __db_fetch_single_value("select csv_config from xform_config_data where xform_id=" + xform_id)
    return HttpResponse(csv_config , content_type='application/json')


#--------------------------- Form Related ------------------------

#--------------------------- API Related -------------------------


# @api_view(['GET'])
# @permission_classes((IsAuthenticated,))
def get_form_api(request, username,last_sync_time):
    """
    this function will return script for system table
    :param Request:
    :return:
    """
    # form_query = "select lx.id,id_string from logger_xform lx, xform_config_data xc where lx.id = xc.xform_id and status=1"
    # form_df = pandas.read_sql(form_query, connection)
    # form_id_list = form_df['id'].tolist()
    # form_id_string = '0'
    # if len(form_id_list) > 0:

    #     form_id_string = ','.join(str(x) for x in form_id_list)

    form_config_query = """select lower(sql_script) as sql_script, xform_id as id, (extract(epoch from created_at::timestamp) * 1000)::bigint as updated_at from database_static_script where (extract(epoch from created_at::timestamp) * 1000)::bigint > %s""" % (str(last_sync_time))
    #print form_config_query
    form_config_df = pandas.read_sql(form_config_query, connection)
    # if not form_config_df.empty:
    #     print form_df
    #     print form_config_df
    #     form_config_df = form_config_df.merge(form_df, on='id', how='left')
    json_data = form_config_df.to_json(orient='records')
    response = HttpResponse(json_data)
    response["Access-Control-Allow-Origin"] = "*"
    return response




# @api_view(['GET'])
# @permission_classes((IsAuthenticated,))
def get_module_api(request, username):
    """This function will render Published Module Data

    Args:
        request ([GET]): []
        username ([string]): [Requested user's username]

    Returns:
        [json]: [Module configuration json tree]
    """
    if request.GET.get('last_modified') is not None:
        last_sync_time = request.GET.get('last_modified')
    else:
        last_sync_time = 0
    role_id = None
    branch_id = None
    user = User.objects.get(username = username)
    role_id = utility_functions.get_user_role(user.id)
    branch_id = utility_functions.get_user_branch(user.id)
    branch_catchment_df = utility_functions.get_branch_catchment(branch_id)
    #print len(branch_catchment_df)
    media_url = 'http://' + str(request.META['SERVER_NAME']) + ':' + str(
        request.META['SERVER_PORT']) + '/media/shared_file/'
    module_query = """select id,'module_'||id::text as "name", m_name::json as label, 
    (case when module_type='1' then 'form' when module_type='2' then 'list' 
    when module_type='3' then 'container' end ) as "type", icon as img_id, 
    node_parent, xform_id::int, list_def_id as list_id, "order" from core.module_definition where publish_status=1 and archive = 0
    and id = any (SELECT  module_id FROM core.modulerolemap where role_id = %d and deleted_at is null)"""%(role_id)
    #print(module_query)
    
    module_df = pandas.read_sql(module_query, connection)
    module_df = module_df.fillna('')
    root = module_df['node_parent'] == ''
    root_df = module_df[root]
    root_dict = root_df.drop(['node_parent'], axis=1).to_dict('records')

    final_dict = get_children_dict(root_dict, module_df, media_url, branch_catchment_df)
    # print("------------final_dict------------")
    # print(final_dict)
    if len(final_dict)>0:
        response = HttpResponse(json.dumps(final_dict[0]))
    else: response = HttpResponse(json.dumps({}))
    response["Access-Control-Allow-Origin"] = "*"
    return response



def get_children_dict(module_dict, module_df, media_url, parent_catchment_df):
    """
    :param module_dict: module definition dictionary
    :param module_df: module dataframe
    :parent_catchment_df: catchment dataframe
    :return: json data containing module definition
    """
    final_dict = []
    for module in module_dict:
        child_df = module_df[module_df['node_parent'] == module['id']]
        child_dict = child_df.drop(['node_parent'], axis=1).to_dict('records')
        module_catchment_df = utility_functions.get_module_catchment(module['id'])
        
        
        if not module_catchment_df.empty:
            catchment_df = pandas.merge(module_catchment_df, parent_catchment_df, how ='inner') 
            #if len(catchment_df)<=0:
            #    return []
        else: catchment_df = parent_catchment_df
        #print len(catchment_df), len(parent_catchment_df)
        # module['label'] = json.loads(module['label'])
        module['catchment_area'] = catchment_df.to_dict('records') 
        if module['xform_id'] != '':
            module['xform_id'] = int(module['xform_id'])
        if module['img_id'] != '':
            module['img_id'] = ''+module['img_id']
        
        if len(catchment_df) > 0:
            module['children'] = get_children_dict(child_dict, module_df, media_url, catchment_df)
            final_dict.append(module)
    return final_dict


# @api_view(['GET'])
# @permission_classes((IsAuthenticated,))
def get_form_list_api(request, username):
    """
    this function will return form json
    :param Request:
    :return:
    """
    if request.GET.get('last_modified') is not None:
        last_sync_time = request.GET.get('last_modified')
    else:
        last_sync_time = 0
    user = User.objects.get(username = username)
    role_id = utility_functions.get_user_role(user.id)
    form_query = """select
	lx.id,
	lx.id_string as name,
	lx.json::json as form_definition,
	lx.uuid as form_uuid
from
	instance.logger_xform lx
where
	lx.id in (with tf as(with tmax as(with t1 as(
	select
		md.xform_id,(extract(epoch
	from
		coalesce(md.updated_at, md.created_at)::timestamp) * 1000)::bigint as updated_at
	from
		core.module_definition md
	left join core.modulerolemap mrm on
		mrm.module_id = md.id
	where
		md.module_type = '1'
		and mrm.role_id = %d), t2 as(
	select
		lw.xform_id::int,(extract(epoch
	from
		coalesce(ld.updated_at, ld.created_at)::timestamp) * 1000)::bigint as updated_at
	from
		core.list_workflow lw
	left join core.module_definition md on
		md.list_def_id = lw.list_id
	left join core.list_definition ld on
		ld.id = lw.list_id
	left join core.modulerolemap mrm on
		mrm.module_id = md.id
	where
		lw.workflow_type = 'entry'
		and md.publish_status = 1
		and md.module_type = '2'
		and mrm.role_id = %d)
	select
		*
	from
		t1
union all
	select
		*
	from
		t2)
	select
		xform_id, max(updated_at) as updated_at
	from
		tmax
	group by
		xform_id)
	select
		xform_id
	from
		tf
	where
		updated_at > %d)"""%(int(role_id),int(role_id),int(last_sync_time))
    # print(form_query)
    form_df = pandas.read_sql(form_query, connection)
    form_id_list = form_df['id'].tolist()
    form_id_string = ','.join(str(x) for x in form_id_list)
    if form_id_string == '':
        form_id_string = '0'
    form_config_query = "select xform_id as id,(case when table_mapping is null then '[]' else table_mapping end)::json table_mapping,csv_config::json as choice_list from xform_config_data where xform_id = any(array[" + form_id_string + "])"
    form_config_df = pandas.read_sql(form_config_query, connection)
    form_df = form_df.merge(form_config_df, on='id', how='inner')
    form_dict = form_df.to_dict('records')
    
    for form in form_dict:
        choice_list = form['choice_list'] 
        choice_temp = {}
        if choice_list is not None and len(choice_list)>0:
            for choice in choice_list:
                temp = {}
                datasource_id = choice['datasource_id']
                query = utility_functions.datasource_query_generate(datasource_id)
                temp['query'] = query
                temp['config_json'] = choice
                choice_temp[choice['csv_name']] = temp
        form['choice_list'] = choice_temp   
                

    response = HttpResponse(json.dumps(form_dict))
    response["Access-Control-Allow-Origin"] = "*"
    return response


# @api_view(['GET'])
# @permission_classes((IsAuthenticated,))
def get_form_choices_api(request, username):
    """
    this function will return form json
    :param Request:
    :return:
    """
    if request.GET.get('last_modified') is not None:
        last_sync_time = request.GET.get('last_modified')
    else:
        last_sync_time = 0
    user = User.objects.get(username=username)
    role_id = utility_functions.get_user_role(user.id)
    form_query = """with t as(select xform_id,field_name,value_label,value_text,field_type from "instance".xform_extracted xe where field_type in ('select one',
'select all that apply') and xform_id in (select xform_id::int from core.module_definition 
    where module_type = '1' and id = any 
    (SELECT  module_id FROM core.modulerolemap where role_id = %d 
    and deleted_at is null) union 
select xform_id::int from core.list_workflow where workflow_type='entry' and list_id = any(select list_def_id from core.module_definition where publish_status=1 and module_type = '2' and id = any(SELECT  module_id FROM core.modulerolemap where role_id = %d and deleted_at is null)))
    )
    select * from t where xform_id in (with tf as(with tmax as(with t1 as(
	select
		md.xform_id,(extract(epoch
	from
		coalesce(md.updated_at, md.created_at)::timestamp) * 1000)::bigint as updated_at
	from
		core.module_definition md
	left join core.modulerolemap mrm on
		mrm.module_id = md.id
	where
		md.module_type = '1'
		and mrm.role_id = %d), t2 as(
	select
		lw.xform_id::int,(extract(epoch
	from
		coalesce(ld.updated_at, ld.created_at)::timestamp) * 1000)::bigint as updated_at
	from
		core.list_workflow lw
	left join core.module_definition md on
		md.list_def_id = lw.list_id
	left join core.list_definition ld on
		ld.id = lw.list_id
	left join core.modulerolemap mrm on
		mrm.module_id = md.id
	where
		lw.workflow_type = 'entry'
		and md.publish_status = 1
		and md.module_type = '2'
		and mrm.role_id = %d)
	select
		*
	from
		t1
union all
	select
		*
	from
		t2)
	select
		xform_id, max(updated_at) as updated_at
	from
		tmax
	group by
		xform_id)
	select
		xform_id
	from
		tf
	where
		updated_at > %d)""" % (
    int(role_id), int(role_id), int(role_id),int(role_id), int(last_sync_time))
    # print(form_query)
    form_df = pandas.read_sql(form_query, connection)
    # form_id_list = form_df['id'].tolist()
    # form_id_string = ','.join(str(x) for x in form_id_list)
    # if form_id_string == '':
    #     form_id_string = '0'
    # form_config_query = "select xform_id as id,(case when table_mapping is null then '[]' else table_mapping end)::json table_mapping,csv_config::json as choice_list from xform_config_data where xform_id = any(array[" + form_id_string + "])"
    # form_config_df = pandas.read_sql(form_config_query, connection)
    # form_df = form_df.merge(form_config_df, on='id', how='inner')
    form_dict = form_df.to_dict('records')

    # for form in form_dict:
    #     choice_list = form['choice_list']
    #     choice_temp = {}
    #     if choice_list is not None and len(choice_list) > 0:
    #         for choice in choice_list:
    #             temp = {}
    #             datasource_id = choice['datasource_id']
    #             query = utility_functions.datasource_query_generate(datasource_id)
    #             temp['query'] = query
    #             temp['config_json'] = choice
    #             choice_temp[choice['csv_name']] = temp
    #     form['choice_list'] = choice_temp

    response = HttpResponse(json.dumps(form_dict))
    response["Access-Control-Allow-Origin"] = "*"
    return response


# @api_view(['GET'])
# @permission_classes((IsAuthenticated,))
def get_list_def_api(request, username):
    """ This function renders List Def json as API

    Args:
        request ([GET]):
        username ([string]): [Requested user's username]

    Returns:
        [json]: [List Def Json]
    """
    if request.GET.get('last_modified') is not None:
        last_sync_time = request.GET.get('last_modified')
    else:
        last_sync_time = 0
    query = """
    select
        id,
        'list_' || id::text as list_name,
        list_name::json as list_header,
        column_definition,
        filter_definition,
        datasource_type,
        datasource
    from
        core.list_definition
    where
        publish_status = 1
        and (extract(epoch from coalesce(updated_at,created_at)::timestamp) * 1000)::bigint > %d
    """ % int(last_sync_time)
    list_df = pandas.read_sql(query, connection)

    id_list = list_df['id'].tolist()
    list_id_string = ','.join( str(id) for id in id_list)
    if list_id_string == '':
        list_id_string = '0'
    # print list_id_string
    workflow_query = "select title::json,list_id,workflow_definition,workflow_type,xform_id,id, details_pk from list_workflow where list_id=any(array[%s])" % (
        list_id_string)
    # print
    # workflow_query
    workflow_df = pandas.read_sql(workflow_query, connection)
    # print workflow_df
    list_df = list_df.fillna('')
    list_dict = list_df.to_dict('records')
    final_dict = []
    for list_def in list_dict:
        try:
            #sorting column according to order
            col_df = pandas.DataFrame(list_def['column_definition']).sort_values(by=['order'], ascending=True)
            col_df = col_df.where(pandas.notnull(col_df), None)
            list_def['column_definition'] = col_df.to_dict('r')
            # print list_def['column_definition']


        except Exception as ex:
            print ex
        try:
              #sorting Filter accroding to order
            filter_df = pandas.DataFrame(list_def['filter_definition']).sort_values(by=['order'], ascending=True)
            filter_df = filter_df.where(pandas.notnull(filter_df), None)
            list_def['filter_definition'] = filter_df.to_dict('r')
            #sorting Filter according to order

        except Exception as ex:
            print ex
        if list_def['datasource_type'] == 1:
            query = "select * from " + list_def['datasource']
        else:
            query = datasource_query_generate(list_def['datasource'])
        list_def['datasource'] = {'type': list_def['datasource_type'], 'query': query, 'config_json': ""}
        del list_def['datasource_type']
        action_df = workflow_df[workflow_df['list_id'] == list_def['id']]
        list_def = get_action_dict(action_df, list_def)
        final_dict.append(list_def)


    response = HttpResponse(json.dumps(final_dict))
    response["Access-Control-Allow-Origin"] = "*"
    return response


def get_action_dict(action_df, list_def):
    """This function Manages action flow of a list

    Args:
        action_df ([dataframe]): [all the action def of a list]
        list_def ([dict]): [Definition of a particular list]

    Returns:
        [dict]: [Manipulated column_defintion after adding action flow as column]
    """
    action_df = action_df.fillna(0)
    action_dict = action_df.to_dict('records')
    col_def = list_def['column_definition']

    action_definition = []
    for action in action_dict:
        form_title = ''
        if action['xform_id']:
            form_title = __db_fetch_single_value("""select title from logger_xform 
                                              where id = %d"""%(int(action['xform_id'])))
        action_temp = {
                'action_type': action['workflow_type'],
                'xform_id': action['xform_id'],
                'form_title': form_title,
                'data_mapping': action['workflow_definition'],
                'label': action['title'],
                'details_pk': action['details_pk']
            }
        action_definition.append(action_temp)
    if len(action_definition)>0:
        action_dict = {
                "data_type": "action",
                "label": {"Bangla": "Action", "English": "Action"},
                "action_definition": action_definition

        }
        col_def.append(action_dict)

    list_def['column_definition'] = col_def
    return list_def


@csrf_exempt
def submission_request(request, username):
    """This function handles form submission

    Args:
        request ([POST]): []
        username ([string]): [Requested users name]

    Returns:
        [json]: [Submitted instance meta data]
    """
    body = request.body
    xml_string = json.loads(body.encode('utf-8'))['xml_submission_file']
    xml = ET.fromstring(xml_string)
    xml_file = StringIO.StringIO(xml_string)
    sub_url = 'http://' + str(request.META['SERVER_NAME']) + ':' + str(
        request.META['SERVER_PORT']) + '/' + username + '/submission'
    print sub_url
    files = {'xml_submission_file': xml_file}
    r = requests.post(sub_url, files=files)
    message = {'status': r.status_code, 'message': r.text}
    root = ET.fromstring(r.text)
    instance_data = None
    if r.status_code == 201:
        for child in root:
            instance_string = child.attrib
            instance_data = instance_string.get('instanceID')

        instance_data = instance_data.replace('uuid:', '')
        instance = Instance.objects.filter(uuid=instance_data).first()
        message['id'] = instance.id
        message['date_created'] = instance.date_created.strftime("%Y-%m-%d %H:%M:%S")

    response = HttpResponse(json.dumps(message))
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_exempt
def system_tabl_sync(request, username):
    """This functon handles data sync between app and web

    Args:
        request ([GET]): []
        username ([string]): [requested user's username]

    Returns:
        [json]: [All instance data submitted after the sync time]
    """
    last_modified = 'null'
    where_string = ' '

    if request.GET.get('last_modified') is not None:
        last_modified = request.GET.get('last_modified')
        print last_modified
        where_string = " where (extract(epoch from date_modified::timestamp) * 1000)::bigint>" + str(last_modified) + ""
    else:
        last_modified = '0'
        
    qry="select id,script_file,id_string from core.database_static_script where xform_id is null and script_file is not null"
    list_df = pandas.read_sql(qry, connection)
    
    datas=[]
    
    for i,row in list_df.iterrows():
        d={}
        id=row["id"]
        script_file=row["script_file"].replace('@@lt',last_modified) 
        id_string=row["id_string"]
        data = __db_fetch_single_value(script_file)  
        d["data"]=data
        d["table_name"]=id_string
        qry="select jsonb_agg(vw_primary_keys.key_column)  from vw_primary_keys where table_name = '" + id_string + "'"
        d["primary_key"]=__db_fetch_single_value(qry)  
        datas.append(d)
    print datas
        
                     
    response = HttpResponse(json.dumps(datas))
    response["Access-Control-Allow-Origin"] = "*"
    return response    


@csrf_exempt
def data_sync(request, username):
    """This functon handles data sync between app and web

    Args:
        request ([GET]): []
        username ([string]): [requested user's username]

    Returns:
        [json]: [All instance data submitted after the sync time]
    """
    last_modified = 'null'
    where_string = ' '

    if request.GET.get('last_modified') is not None:
        last_modified = request.GET.get('last_modified')
        print
        last_modified
        where_string = " where (extract(epoch from date_modified::timestamp) * 1000)::bigint>" + str(last_modified) + ""

    logger_query = """select id,xform_id, json, user_id, 
    (extract(epoch from date_modified::timestamp) * 1000)::bigint as updated_at from logger_instance""" + where_string
    logger_df = pandas.read_sql(logger_query, connection)
    logger_df = logger_df.fillna('')
    logger_json = logger_df.to_json(orient='records')

    response = HttpResponse(logger_json)
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_exempt
def data_sync_paginated(request, username):
    """This functon handles data sync between app and web

    Args:
        request ([GET]): []
        username ([string]): [requested user's username]

    Returns:
        [json]: [All instance data submitted after the sync time]
    """
    geo_mapping = {
        1: 'basic_info/division',
        2: 'basic_info/district',
        3: 'basic_info/upazila',
        4: 'basic_info/union',
        5: 'basic_info/mouza'
    }
    last_modified = 'null'
    where_string = ' '

    # user = User.objects.get(username=username)
    # branch_id = utility_functions.get_user_branch(user.id)
    # branch_catchment_df = utility_functions.get_branch_catchment(branch_id)
    branch_catchment_df = pandas.read_sql("""
    select geoid as value,gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::bigint = bca.geoid 
    where bca.branch_id in (	
	select branch_id from core.usermodule_userbranchmap where user_id = (select id from "instance".auth_user au where username = '%s'))
	and deleted_at is null
    """ % (username), connection)
    if not branch_catchment_df.empty:
        geo_filter_query = ' and ('
        for idx, row in branch_catchment_df.iterrows():
            if idx > 0:
                geo_filter_query += " or " + "coalesce(json->>'" + geo_mapping[
                    row['loc_type']] + "','-fuzx-') in ('" + str(
                    row['value']) + "','-fuzx-')"
            else:
                geo_filter_query += "coalesce(json->>'" + geo_mapping[row['loc_type']] + "','-fuzx-') in ('" + str(
                    row['value']) + "','-fuzx-')"
        geo_filter_query += ') '
    else:
        geo_filter_query = ''

    if request.GET.get('last_modified') is not None:
        last_modified = request.GET.get('last_modified')
        print last_modified
        where_string = " where (extract(epoch from date_modified::timestamp) * 1000)::bigint>" + str(last_modified) + ""

    if request.GET.get('page_length') is not None:
        page_length = int(request.GET.get('page_length'))
    else:
        page_length = 100

    if request.GET.get('page_no') is not None:
        page_no = int(request.GET.get('page_no'))
    else:
        page_no = 1

    order_limit_str = " order by id asc limit %s offset %s * (%s - 1)" % (page_length, page_length, page_no)

    logger_query = """select id,xform_id, json, user_id, 
    (extract(epoch from date_modified::timestamp) * 1000)::bigint as updated_at from logger_instance""" + where_string + geo_filter_query + order_limit_str
    print logger_query
    logger_df = pandas.read_sql(logger_query, connection)
    logger_df = logger_df.fillna('')
    logger_json = logger_df.to_json(orient='records')

    response = HttpResponse(logger_json)
    response["Access-Control-Allow-Origin"] = "*"
    return response


@csrf_exempt
def data_sync_count(request, username):
    """This functon handles data sync count between app and web

    Args:
        request ([GET]): []
        username ([string]): [requested user's username]

    Returns:
        [json]: [All instance data submitted after the sync time]
    """
    geo_mapping = {
        1:'basic_info/division',
        2:'basic_info/district',
        3:'basic_info/upazila',
        4:'basic_info/union',
        5:'basic_info/mouza'
    }
    last_modified = 'null'
    where_string = ' '

    # user = User.objects.get(username=username)
    # branch_id = utility_functions.get_user_branch(user.id)
    # branch_catchment_df = utility_functions.get_branch_catchment(branch_id)
    branch_catchment_df = pandas.read_sql("""
        select geoid as value,gd.field_type_id as loc_type from core.branch_catchment_area bca 
        left join core.geo_data gd on
        gd.geocode::bigint = bca.geoid 
        where bca.branch_id in (	
    	select branch_id from core.usermodule_userbranchmap where user_id = (select id from "instance".auth_user au where username = '%s'))
    	and deleted_at is null
        """ % (username), connection)
    if not branch_catchment_df.empty:
        geo_filter_query = ' and ('
        for idx,row in branch_catchment_df.iterrows():
            if idx > 0:
                geo_filter_query += " or " + "coalesce(json->>'" + geo_mapping[row['loc_type']] + "','-fuzx-') in ('" + str(
                    row['value']) + "','-fuzx-')"
            else:
                geo_filter_query += "coalesce(json->>'" + geo_mapping[row['loc_type']] + "','-fuzx-') in ('" + str(
                    row['value']) + "','-fuzx-')"
        geo_filter_query += ')'
    else:
        geo_filter_query = ''

    if request.GET.get('last_modified') is not None:
        last_modified = request.GET.get('last_modified')
        print(last_modified)
        where_string = " where (extract(epoch from date_modified::timestamp) * 1000)::bigint>" + str(last_modified) + ""

    logger_query = """select count(*) from logger_instance""" + where_string + geo_filter_query
    logger_df = pandas.read_sql(logger_query, connection)
    logger_df = logger_df.fillna('')
    logger_json = logger_df.to_json(orient='records')

    response = HttpResponse(logger_json)
    response["Access-Control-Allow-Origin"] = "*"
    return response


def checking_user_upazila(user_branch, working_upazila_id):
    """
    :param user_branch: user branch model
    :param working_upazila_id: upazila code
    :return: boolean flag according to existence of machine_id in database
    """
    return True
    query = "select count(*) from branch_catchment_area where branch_id = "+str(user_branch.branch_id)+" and geoid="+working_upazila_id+" and deleted_at is null;"
    result_count = __db_fetch_single_value(query)
    if result_count==0:
        return False
    else:
        return True


@csrf_exempt
def app_user_verify(request):
    """
    Final Executable Query Generator
    :param request: catchment info and user credential info in request body
    :return: user information with unique machine id
    """
    try :
        body = request.body
        data_json = json.loads(body)
        division, district, upazila, mac_address, username, password = '', '', '', '', '', ''

        if 'upazila' in data_json:
            upazila = data_json['upazila']
        if 'mac_address' in data_json:
            mac_address = data_json['mac_address']
        if 'username' in data_json:
            username = data_json['username']
        if 'password' in data_json:
            password = data_json['password']
        user_information = {}
        

        working_upazila_id = str(upazila)

        # first authenticate user
        if username != '' and password != '':
            user = authenticate(username=username, password=password)


            if user:
                user_branch = UserBranch.objects.filter(user_id=user.id).first()

                # checking user branch catchment area matches with request area
                #if checking_user_upazila(user_branch, working_upazila_id):
                # number of login attempts allowed
                max_allowed_attempts = 5
                # count of invalid logins in db
                counter_login_attempts = UserFailedLogin.objects.filter(user_id=user.id).count()
                # check for number of allowed logins if it crosses limit do not login.
                if counter_login_attempts < max_allowed_attempts:
                    # return HttpResponse("Your account is locked for multiple invalid logins, contact admin to unlock")
                    status = 200

                # Is the account active? It could have been disabled.
                if user.is_active:
                    if hasattr(user, 'usermoduleprofile'):
                        # user profile
                        user_profile = user.usermoduleprofile
                        user_branch = UserBranch.objects.filter(user_id=user.id).first()
                        user_role = UserRoleMap.objects.filter(user_id=user.id).first()
                        user_information['user_name'] = username
                        user_information['name'] = user.first_name + " " + user.last_name
                        user_information['email'] = user.email
                        user_information['role'] = user_role.role.role
                        user_information['organization'] = user_profile.organisation_name_id
                        user_information['branch'] = user_branch.branch_id
                        user_information['branch_catchment'] = utility_functions.get_branch_catchment(user_information['branch']).to_dict('records')

                    login(request, user)
                    UserFailedLogin.objects.filter(user_id=user.id).delete()
                    status = 200
            else:
                return HttpResponse('Invalid login credentials!!', status= 409)

        if mac_address != '' and working_upazila_id != '':
            query = "select id from core.registered_device where working_upazila_id=" + working_upazila_id + " and mac_address = '" + mac_address + "'"
            df = pandas.read_sql(query, connection)

            if len(df.id.tolist()):
                meta_id = df.id.tolist()[0]
            else:
                insert_query = "INSERT INTO core.registered_device (working_upazila_id, mac_address, created_at, updated_at) VALUES(" + working_upazila_id + ", '" + mac_address + "', now(), now()) returning id;"
                meta_id = __db_insert_query(insert_query)
            user_information['meta_id'] = working_upazila_id + "{:02d}".format(meta_id)

        return HttpResponse(json.dumps(user_information), status=200)
    except Exception as ex:
        print(ex)
        return HttpResponse('failed', status= 409)



def catchment_area_api(request):
    """
        For generating catchment csv
        :param request: request from app
        :return: zip content with one csv file containing geo-location-mapping
    """
    query = "select div_code as division, div_name as division_label, dist_code as district, dist_name as dist_label, upazila_code as upazila, upazila_name as upazila_label  from vwgeo_cluster"
    catchment_df = pandas.read_sql(query,connection)

    user_path_filename = os.path.join(settings.MEDIA_ROOT, request.user.username)
    user_path_filename = os.path.join(user_path_filename, 'formid-media')
    if not os.path.exists(user_path_filename):
        os.makedirs(user_path_filename)

    file_name = os.path.join(user_path_filename, 'catchment-area.csv')
    catchment_df.to_csv(file_name, encoding='utf-8', index=False)
    filenames = [file_name]
    zip_subdir = "itemsetfiles"
    zip_filename = "%s.zip" % zip_subdir
    # Open StringIO to grab in-memory ZIP contents
    s = StringIO.StringIO()
    # The zip compressor
    zf = zipfile.ZipFile(s, "w")

    for fpath in filenames:
        # Calculate path for file in zip
        if os.path.exists(fpath):
            fdir, fname = os.path.split(fpath)
            zf.write(fpath, fname)

    # Must close zip for all contents to be written
    zf.close()
    # Grab ZIP file from in-memory, make response with correct type
    resp = HttpResponse(s.getvalue(),  content_type='application/zip')
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
    resp["Access-Control-Allow-Origin"] = "*"
    return resp


# def master_data_sync(request, user_id):
#     data = []
#     query = """SELECT product_id, product_label, generic1, generic1_label, generic2,
#     generic2_label, generic3, generic3_label, generic4, generic4_label FROM core.medicine; """
#
#     medicine_df = pandas.read_sql(query, connection)
#     total_query = ''
#     for index, row in medicine_df.iterrows():
#         total_query += """INSERT INTO core.medicine(product_id, product_label, generic1, generic1_label,
#         generic2, generic2_label, generic3, generic3_label, generic4, generic4_label)
#         VALUES(%d,%s', '%s' , '%s', '%s' , '%s', '%s', '%s', '%s', '%s');""" % (row['product_id'], row['product_label'],
#                                                                                 row['generic1'], row['generic1_label'],
#                                                                                 row['generic2'], row['generic2_label'],
#                                                                                 row['generic3'],
#                                                                                 row['generic3_label'], row['generic4'],
#                                                                                 row['generic4_label'])
#     data.append({'script': total_query})
#
#     # field staff
#     query = """SELECT id, fullname, designation, mobile_number, node_id, trained, created_At::date FROM core.field_staffs;"""
#     staff_df = pandas.read_sql(query, connection)
#     total_query = ''
#     for index, row in staff_df.iterrows():
#         total_query += """INSERT INTO core.field_staffs(id, fullname, designation, mobile_number, node_id, trained, created_at) VALUES(%d, '%s', '%s', '%s', '%s', %d, '%s');""" % (
#         row['id'], row['fullname'],
#         row['designation'], row['mobile_number'], row['node_id'], row['trained'], row['created_at'])
#     data.append({'script': total_query})
#
#     print(data)
#     response = HttpResponse([data])
#     response["Access-Control-Allow-Origin"] = "*"
#     return response

#------------------------ API Related -----------------------------


def reduce_geo_loc(branch_id,data_df):
    branch_catchment_df = pandas.read_sql("""
    with t as ( WITH RECURSIVE starting (id, value, name, parent, loc_type) 
        AS ( select id, value, name, parent, loc_type from core.geo_cluster where 
        value = any(select geoid from core.branch_catchment_area where 
        branch_id = %s and deleted_at is null) ), descendants (id, value, name, parent, loc_type) 
        AS ( SELECT id, value, name, parent, loc_type FROM starting AS s 
        UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type 
        FROM core.geo_cluster AS t JOIN descendants AS d ON t.parent = d.value ), 
        ancestors (id, value, name, parent, loc_type) AS ( SELECT t.id, t.value ,t.name, 
        t.parent, t.loc_type FROM core.geo_cluster AS t WHERE t.value IN (SELECT parent FROM starting) 
        UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type FROM core.geo_cluster AS t JOIN 
        ancestors AS a ON t.value = a.parent ) TABLE ancestors UNION ALL TABLE descendants) 
        select t.*, c.node_name as loc_name  from t 
        join core.geo_definition c on t.loc_type = c.id order by value asc
    """ % branch_id,connection)


    div_df = branch_catchment_df[branch_catchment_df['loc_type'] == 1].drop_duplicates()
    dis_df = branch_catchment_df[branch_catchment_df['loc_type'] == 2].drop_duplicates()
    upz_df = branch_catchment_df[branch_catchment_df['loc_type'] == 3].drop_duplicates()
    uni_df = branch_catchment_df[branch_catchment_df['loc_type'] == 4].drop_duplicates()
    mau_df = branch_catchment_df[branch_catchment_df['loc_type'] == 5].drop_duplicates()


    data_df = pandas.merge(data_df.astype(str), div_df.astype(str).add_suffix('_y'), how='inner', left_on='division_code',right_on='value_y')

    data_df = pandas.merge(data_df.astype(str), dis_df.astype(str).add_suffix('_y'), how='inner', left_on='district_code',right_on='value_y')

    data_df = pandas.merge(data_df.astype(str), upz_df.astype(str).add_suffix('_y'), how='inner', left_on='upazila_code',right_on='value_y')

    data_df = pandas.merge(data_df.astype(str), uni_df.astype(str).add_suffix('_y'), how='inner', left_on='union_code',right_on='value_y')

    data_df = pandas.merge(data_df.astype(str), mau_df.astype(str).add_suffix('_y'), how='inner', left_on='mouza_code',right_on='value_y')

    data_df = data_df[['division_code','division_name','district_code','district_name','upazila_code','upazila_name','union_code','union_name','mouza_code','mouza_name']]

    return data_df


def get_datasource_csv(request, form_id):
    """
        For generating catchment csv
        :param request: request from app
        :return: zip content with one csv file containing geo-location-mapping
    """
    branch_id = utility_functions.get_user_branch(request.user.id)
    datasources = __db_fetch_values("""
    with t as(
    select
        xform_id, json_array_elements(csv_config::json) as csv_config
    from
        core.xform_config_data xcd
    where
        xform_id = %s)
    select
        cast(csv_config->>'datasource_id' as integer) as datasource_id,
        csv_config->>'csv_name' as csv_name
    from
        t
    """ % form_id)
    filenames = []
    for ds in datasources:
        datasource_id = ds[0]
        csv_name = ds[1]
        datasource_query = datasource_query_generate(datasource_id)
        data_df = pandas.read_sql(datasource_query, connection)
        if csv_name == 'geo':
            data_df = reduce_geo_loc(branch_id,data_df)
        user_path_filename = os.path.join(settings.MEDIA_ROOT, request.user.username)
        user_path_filename = os.path.join(user_path_filename, 'formid-media')
        if not os.path.exists(user_path_filename):
            os.makedirs(user_path_filename)
        file_name = os.path.join(user_path_filename, str(csv_name) + '.csv')
        data_df.to_csv(file_name, encoding='utf-8', index=False)
        filenames.append(file_name)
    zip_subdir = "itemsetfiles"
    zip_filename = "%s.zip" % zip_subdir
    s = StringIO.StringIO()
    # The zip compressor
    zf = zipfile.ZipFile(s, "w")
    for fpath in filenames:
        # Calculate path for file in zip
        if os.path.exists(fpath):
            fdir, fname = os.path.split(fpath)
            zf.write(fpath, fname)
    # Must close zip for all contents to be written
    zf.close()
    # Grab ZIP file from in-memory, make response with correct type
    resp = HttpResponse(s.getvalue(), content_type='application/zip')
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
    resp["Access-Control-Allow-Origin"] = "*"
    return resp
    
@csrf_exempt
def get_qry_result(request):
    """This functon handles data sync between app and web

    Args:
        request ([GET]): []
        username ([string]): [requested user's username]

    Returns:
        [json]: [All instance data submitted after the sync time]
    """
    post_qry = request.POST
    print post_qry
    response={}

    if "query" in post_qry:
        query = post_qry['query']
        print  query    
        logger_df = pandas.read_sql(query, connection)
        logger_df = logger_df.fillna('')
        logger_json = logger_df.to_json(orient='records')
        response = HttpResponse(logger_json)
        response["Access-Control-Allow-Origin"] = "*"
        
    return response
