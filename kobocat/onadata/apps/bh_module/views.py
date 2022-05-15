from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Count, Q
from django.http import (
    HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, loader
from django.contrib.auth.models import User
from datetime import date, timedelta, datetime
# from django.utils import simplejson
import json
import logging
import sys
from django.core.urlresolvers import reverse
import pandas
from collections import OrderedDict

from django.db import (IntegrityError, transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect

from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
# Menu imports
from onadata.apps.usermodule.forms import MenuForm
from onadata.apps.usermodule.models import MenuItem
# Unicef Imports
from onadata.apps.logger.models import Instance, XForm
# Organization Roles Import
from onadata.apps.usermodule.models import OrganizationRole, MenuRoleMap, UserRoleMap, UserModuleProfile
from onadata.apps.usermodule.forms import OrganizationRoleForm, RoleMenuMapForm, UserRoleMapForm, UserRoleMapfForm
from onadata.apps.usermodule.views import get_recursive_organization_children
from django.forms.models import inlineformset_factory, modelformset_factory
from django.forms.formsets import formset_factory

from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.shortcuts import render
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os
import time
import csv

from onadata.apps.bh_module.utility_functions import *
from onadata.apps.main.database_utility import __db_fetch_values_dict, __db_fetch_values, __db_fetch_single_value, \
    __db_commit_query, __db_insert_query, db_fetch_dataframe

from onadata.apps.bh_module import utility_functions, Constants

datasource_type = [['2', 'Datasource'], ['1', 'Table']]
data_type = [['int', 'Integer'], ['number', 'Number'], ['text', 'Text'], ['date', 'Date']]
merge_dicts = lambda old, new: old.update(new) or old
from onadata.apps.formmodule.form_tools import generate_insert_query


# -------------------------Datasource Related ---------------------


@login_required
def datasource_list(request):
    """
        View of Datasource List
    """
    datasource_query = "SELECT id, ds_name, title, p_source, p_source_type, s_source, " \
                       "s_source_type, (created_at::date)::text FROM core.datasource_definition order by id desc"
    datasource_df = pandas.read_sql(datasource_query, connection)
    datasource_df = datasource_df.fillna('')
    datasource_data = datasource_df.to_dict('records')

    template = loader.get_template('datasource_list.html')
    context = RequestContext(request, {
        'datasource_list': json.dumps(datasource_data)
    })

    return HttpResponse(template.render(context))


def edit_datasource(request, datasource_id):
    """This function is for editing datasource which will recieve POST request
    @param request:
    @param datasource_id: `str`
    @return: response
    """
    info_dict = datasource_form_info()
    query = "SELECT id, ds_name, title as datasource_title, p_source, p_source_type::text," \
            " s_source, s_source_type::text, column_mapping FROM core.datasource_definition where id =" + datasource_id
    datasource_df = __db_fetch_values(query)[0]
    column_data = datasource_df[7]

    datasource_dict = {
        'datasource_title': datasource_df[2],
        'p_source': datasource_df[3],
        's_source': datasource_df[5],
        'p_source_type': datasource_df[4],
        's_source_type': datasource_df[6],
        'column_mapping': json.dumps(column_data)
    }
    if 'operation' in column_data:
        if 'on' in column_data['operation']:
            datasource_dict['p_source_key'] = column_data['operation']['on'][0]['p_key']
            datasource_dict['s_source_key'] = column_data['operation']['on'][0]['s_key']
    merge_dicts = lambda old, new: old.update(new) or old

    template = loader.get_template('edit_datasource.html')
    context = RequestContext(request, merge_dicts(datasource_dict, info_dict))
    return HttpResponse(template.render(context))


@csrf_exempt
def datasource_preview(request, datasource_id):
    """ This View is for Datasource Preview Table
    @param request:
    @param datasource_id: `str`
    @return: json
    """
    datasource_query = datasource_query_generate(datasource_id)
    print datasource_query
    df = pandas.read_sql(datasource_query, connection)
    table_classes = "dataframe_datasource display table table-bordered table-striped table-condensed table-responsive nowrap"
    table_html = df.to_html(classes=table_classes, index=False)
    data = {'table': table_html}

    template = loader.get_template('datasource_view.html')

    return HttpResponse(json.dumps(data))


def datasource_view(request, datasource_id):
    """
    @param request:
    @param datasource_id: `str`
    @return:
    """
    datasource_query = datasource_query_generate(datasource_id)
    print(datasource_query)
    df = pandas.read_sql(datasource_query, connection)
    table_classes = "dataframe_datasource display table table-bordered table-striped table-condensed table-responsive nowrap"
    table_html = df.to_html(classes=table_classes, index=False)

    template = loader.get_template('datasource_view.html')
    context = RequestContext(request, {
        'table': table_html
    })

    return HttpResponse(template.render(context))


@login_required
def create_datasource(request):
    template = loader.get_template('create_datasource.html')
    info_dict = datasource_form_info()
    context = RequestContext(request, info_dict)

    return HttpResponse(template.render(context))


def datasource_form_info():
    join_types = [['Inner Join', 'Inner Join'], ['Left Join', 'Left Join'], ['Full Join', 'Full Join'],
                  ['Right join', 'Right join']]
    join_types = [['Inner Join', 'Inner Join'], ['Left Join', 'Left Join']]
    datasource_list = __db_fetch_values("select id, title from core.datasource_definition")
    table_list = __db_fetch_values("SELECT table_name,table_name as \"name\" FROM "
                                   "information_schema.tables WHERE table_type='BASE TABLE' "
                                   "AND table_schema in ('core','custom')")

    data_info = {
        'datasource_choices': datasource_list,
        'table_choices': table_list,
        'datasource_type_choices': datasource_type,
        'join_type_choices': join_types,
        'data_type_choices': data_type
    }
    return data_info


def parse_aggregate_def(data):
    print (data)
    # data = {u'aggregation@column_rename': [u'', u''], u'aggregation@type': [u'count', u'sum'], u'aggregation@source_type': [u'1', u'1'], u'aggregation@column_type': [u'number', u'text'], u'aggregation@column': [u'id', u'script_file']}
    aggregation_type = data['aggregation@type[]']
    primary_source = []
    secondary_source = []
    for i in range(len(aggregation_type)):
        # if primary source
        temp_def = {'agg_function': data['aggregation@type[]'][i]}
        temp_def['name'] = data['aggregation@column[]'][i]
        temp_def['agg_columntype'] = data['aggregation@column_type[]'][i]

        if data['aggregation@column_rename[]'][i] != '':
            temp_def['rename'] = data['aggregation@column_rename[]'][i]

        if data['aggregation@source_type[]'][i] == '1':
            primary_source.append(temp_def)
        else:
            secondary_source.append(temp_def)
    return primary_source, secondary_source


@csrf_exempt
def add_datasource(request):
    if request.POST:
        column_mapping = {}
        s_source_name = ''
        s_source_type = 'null'
        p_source_key = []
        s_source_key = []
        primary_agg = []
        secondary_agg = []
        post_dict = dict(request.POST.iterlists())
        print (post_dict)
        print("********************************")
        main_data = json.loads(post_dict['main_data'][0])
        primary_source = json.loads(post_dict['primary_source'][0])
        if 'aggregation_data' in post_dict:
            aggregation_data = json.loads(post_dict['aggregation_data'][0])
            primary_agg, secondary_agg = parse_aggregate_def(aggregation_data)
            print aggregation_data

        print("##########################################")

        print main_data, primary_source
        print("##########################################")

        datasource_name = main_data['datasource_name']
        p_source_type = main_data['p_source_type']
        operation_type = main_data['join_type']

        p_source_name = main_data['p_source'][0] if main_data['p_source'] != '' else main_data['p_source'][1]
        p_source_name = primary_source['p_source']

        print p_source_name
        if p_source_name != '':
            p_source_info = parsing_source_info(primary_source, 'p_source')
            print p_source_info + primary_agg

            column_mapping['p_source'] = {'column_names': p_source_info + primary_agg}

        if operation_type != '':
            s_source_name = primary_source['s_source']
            if s_source_name != '':
                s_source_key = primary_source['s_source_key']
                p_source_key = primary_source['p_source_key']
                s_source_type = main_data['s_source_type']
                s_source_info = parsing_source_info(primary_source, 's_source')
                print s_source_info
                column_mapping['s_source'] = {'column_names': s_source_info + secondary_agg}

            join_key_list = []

            if isinstance(p_source_key, list):
                if len(p_source_key) == len(s_source_key):
                    for i in range(len(p_source_key)):
                        temp = {}
                        temp['p_key'] = p_source_key[i]
                        temp['s_key'] = s_source_key[i]

                        join_key_list.append(temp)
            else:
                join_key_list.append({'p_key': p_source_key, 's_key': s_source_key})

            column_mapping['operation'] = {"on": join_key_list, "type": operation_type}

        condition_list = parse_condition(main_data)
        column_mapping['condition'] = condition_list

        print column_mapping
        query = "INSERT INTO core.datasource_definition (title, p_source, p_source_type, " \
                "s_source, s_source_type, column_mapping, created_at, created_by) " \
                "VALUES( '%s', '%s',%s , '%s', %s, '%s', now(), %d )" % \
                (datasource_name, p_source_name, p_source_type, s_source_name, s_source_type,
                 json.dumps(column_mapping), request.user.id)
        __db_commit_query(query)

        # if ds_id is not None:
        update_query = "update core.datasource_definition set ds_name='datasource_'||id::text " \
                       "where ds_name is null "
        __db_commit_query(update_query)
        messages.success(request, '<i class="fa fa-check-circle"></i> Datasource Added successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/bhmodule/datasource-list/', status=200)


def parse_condition(data_dict):
    print "---------------------------------------"
    print (data_dict)
    condition_source_type = ''
    condition_column = ''
    condition_column_type = ''
    condition_type = ''
    condition_input1 = ''
    condition_input2 = ''
    condition_list = []
    # condition_temp = {}

    if 'condition@source_type[]' in data_dict:
        condition_source_type = data_dict['condition@source_type[]']
        if len(condition_source_type) > 0 and condition_source_type[0] != '':
            condition_source_list = condition_source_type

            if 'condition@column[]' in data_dict:
                condition_column = data_dict['condition@column[]']

            if 'condition@column_type[]' in data_dict:
                condition_column_type = data_dict['condition@column_type[]']

            if 'condition@type[]' in data_dict:
                condition_type = data_dict['condition@type[]']

            if 'condition@input1[]' in data_dict:
                condition_input1 = data_dict['condition@input1[]']

            if 'condition@input2[]' in data_dict:
                condition_input2 = data_dict['condition@input2[]']

            for i in range(len(condition_source_list)):
                condition_temp = {}
                condition_temp['source_type'] = condition_source_list[i]
                if condition_column[i] != '':
                    condition_temp['column'] = condition_column[i]
                if condition_column_type[i] != '':
                    condition_temp['column_type'] = condition_column_type[i]
                if condition_type[i] != '':
                    condition_temp['condition_type'] = condition_type[i]
                if condition_input1[i] != '':
                    condition_temp['input1'] = condition_input1[i]
                if condition_input2[i] != '':
                    condition_temp['input2'] = condition_input2[i]

                condition_list.append(condition_temp)

    return condition_list

    # if len(condition_source_type) >1:


def parsing_source_info(data_dict, source_type):
    """
    This function is to parse column information in details
    @param data_dict:
    @param source_type: `str` this string means the type (eg: primary or secondary)
    @return: `dict` total dictionary of details
    """
    keys = data_dict.keys()
    field_list = set()
    total_def = []

    for key in keys:
        if '@' + source_type in key:
            field_list.add(key.split('@' + source_type)[0])

    for field in field_list:
        temp_dict = {}
        temp_dict['name'] = field
        rename = field + '@' + source_type + '_rename'
        groupby = field + '@' + source_type + '_groupby'
        aggregte_column_type = field + '@' + source_type + '_aggcolumntype'
        condition_type = field + '@' + source_type + '_conditiontype'
        condition_input1 = field + '@' + source_type + '_conditioninput1'
        condition_input2 = field + '@' + source_type + '_conditioninput2'
        column_type = field + '@' + source_type + '_columntype'
        if rename in data_dict and data_dict[rename] != '':
            temp_dict['rename'] = data_dict[rename]

        if groupby in data_dict and data_dict[groupby] != '':
            if data_dict[groupby] == 'on':
                temp_dict['groupby'] = 'groupby'
            # else:
            #     temp_dict['agg_function'] = data_dict[groupby]
            #     if 'agg_colmntype' in temp_dict:
            #         temp_dict['agg_columntype'] = data_dict[aggregte_column_type]

        if column_type in data_dict and data_dict[column_type] != '':
            condition_dict = {}
            temp_dict['column_type'] = data_dict[column_type]
            condition_dict['column_type'] = data_dict[column_type]
            if condition_type in data_dict:
                condition_dict['condition_type'] = data_dict[condition_type]
                condition_dict['input1'] = data_dict[condition_input1]
                condition_dict['input2'] = data_dict[condition_input2]
                temp_dict['condition'] = condition_dict

        total_def.append(temp_dict)

    return total_def


def get_datasource_query(request, datasource_id):
    datasource_query = datasource_query_generate(datasource_id)
    print datasource_query


# -------------------------Datasource Related ---------------------#

def project_profile(request, project_id):
    """
    this function will render to project profile
    :param request: request param
    :param project_id: `str` Project Id
    :return: template
    """
    redirect_url = request.GET.get('next')
    print redirect_url
    module_query = "select id, (m_name::json)->>'English' as \"module_name_english\"," \
                   " (m_name::json)->>'Bangla' as \"module_name_bangla\", description, " \
                   "starting_year, ending_year, icon, \"order\" as module_order, node_parent,status,publish_status,archive from core.module_definition where id =" + project_id

    project_dict = __db_fetch_values_dict(module_query)[0]

    child_module_query = "select id, (m_name::json)->>'English' as \"module_name_english\"," \
                         " (m_name::json)->>'Bangla' as \"module_name_bangla\", " \
                         "applicable_for, (select title from logger_xform where id = xform_id) as xform_id, " \
                         "\"order\",node_parent as node, icon, list_def_id::text, xform_id::text, is_project, created_at::date, " \
                         "(case when module_type='1' then 'New Entry' when " \
                         "module_type='2' then 'List' when module_type='3' then 'Container' end ) module_type,status,publish_status,archive" \
                         " from module_definition where archive = 0 and node_parent = %s order by \"order\"" % (
                             project_id)
    child_module_df = pandas.read_sql(child_module_query, connection)
    child_module_df = child_module_df.fillna('')
    child_module_data = child_module_df.to_dict('records')

    child_archived_module_query = """
    select id, (m_name::json)->>'English' as "module_name_english", (m_name::json)->>'Bangla' as "module_name_bangla", applicable_for,
(select title from "instance".logger_xform where id = xform_id) as xform_id,
                         "order",node_parent as node, icon, list_def_id::text, xform_id::text, is_project, created_at::date,
                         (case when module_type='1' then 'New Entry' when 
                         module_type='2' then 'List' when module_type='3' then 'Container' end ) module_type,status,publish_status,archive
                         from core.module_definition where archive = 1 and node_parent = %s order by "order"
    """ % (project_id)

    child_archived_module_df = pandas.read_sql(child_archived_module_query, connection)
    child_archived_module_df = child_archived_module_df.fillna('')
    child_archived_module_data = child_archived_module_df.to_dict('records')

    template = loader.get_template('project/project_profile.html')
    context = RequestContext(request, {
        'project_data': project_dict,
        'project_id': project_id,
        'child_module_data': child_module_data,
        'child_archived_module_data': child_archived_module_data
    })
    return HttpResponse(template.render(context))


@csrf_exempt
def project_edit(request, project_id):
    """
    this function will render to project Edit Template
    :param request: request param
    :param project_id: `str` Project Id
    :return: template
    """
    redirect_url = request.GET.get('next')
    print redirect_url
    module_query = "select id, (m_name::json)->>'English' as \"module_name_english\"," \
                   " (m_name::json)->>'Bangla' as \"module_name_bangla\", description, " \
                   "starting_year, ending_year, icon, \"order\" as module_order from core.module_definition where id =" + project_id

    project_dict = __db_fetch_values_dict(module_query)[0]
    print project_dict
    if request.method == 'POST':

        module_name_bangla = request.POST.get('module_name_bangla')
        module_name_english = request.POST.get('module_name_english')
        starting_year = request.POST.get('starting_year')
        ending_year = request.POST.get('ending_year')
        description = request.POST.get('description')
        module_order = request.POST.get('module_order')

        m_name = {'English': module_name_english, 'Bangla': module_name_bangla}
        if request.FILES:
            myfile = request.FILES['module_icon']
            uploaded_file_url = utility_functions.document_upload(myfile, myfile.name, 'module_icon')
        update_query = "update module_definition set m_name='%s',starting_year='%s', ending_year = '%s'," \
                       "description = '%s', \"order\" = %s, updated_at=now(), updated_by = %d " \
                       "where id = %s " % (json.dumps(m_name), starting_year,
                                           ending_year, description, module_order, request.user.id, project_id)
        print update_query
        __db_commit_query(update_query)
        messages.success(request, '<i class="fa fa-check-circle"></i> Module Edited successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect(redirect_url)

    template = loader.get_template('project/edit_project.html')
    context = RequestContext(request, {
        'project_data': project_dict,
        'project_id': project_id,
        'redirect_url': redirect_url,
    })
    return HttpResponse(template.render(context))


@csrf_exempt
def project_settings(request):
    """
    this function will save project settings
    :param request: request param
    :return: template
    """
    if request.method == 'POST':
        print request.POST

        project_id = request.POST.get('project_id')
        project_active = request.POST.get('project_active')
        project_publish = request.POST.get('project_publish')
        project_archive = request.POST.get('project_archive')

        update_query = "update module_definition set updated_at=now(), status = %s," \
                       " \"publish_status\" = %s, archive=%s where id = %s" % (project_active,
                                                                               project_publish, project_archive,
                                                                               str(project_id))
        __db_commit_query(update_query)

    return HttpResponse('Sucess', status=200)


def project_add(request):
    """
    This function will save new project
    :return: template
    """
    if request.method == 'POST':
        uploaded_file_url = ''
        module_name_bangla = request.POST.get('module_name_bangla')
        module_name_english = request.POST.get('module_name_english')
        starting_year = request.POST.get('starting_year')
        ending_year = request.POST.get('ending_year')
        description = request.POST.get('description')
        module_order = request.POST.get('module_order')
        module_type = Constants.MODULE_TYPE_CONTAINER
        node_parent = __db_fetch_single_value("""select id 
                      from module_definition where node_parent is null""")
        if request.FILES:
            myfile = request.FILES['module_icon']
            uploaded_file_url = utility_functions.document_upload(myfile, myfile.name, 'module_icon')

        m_name = {'English': module_name_english, 'Bangla': module_name_bangla}

        try:
            insert_query = "INSERT INTO core.module_definition (m_name, module_type, starting_year," \
                           " ending_year, node_parent, \"order\", icon ,description, created_at, created_by, is_project) " \
                           "VALUES('%s', '%s', '%s', '%s', %s, %s, '%s','%s', now(), %d, 'true') returning id;" % (
                               json.dumps(m_name),
                               module_type, starting_year, ending_year, node_parent, module_order,
                               uploaded_file_url, description, request.user.id)
            id = __db_commit_query(insert_query)
            messages.success(request, '<i class="fa fa-check-circle"></i> Project Added successfully!',

                             extra_tags='alert-success crop-both-side')

            return HttpResponseRedirect('/bhmodule/project-list/')
        except Exception as ex:
            print ex
            messages.success(request, '<i class="fa fa-check-circle"></i> Project Add failed!',
                             extra_tags='alert-danger crop-both-side')

    template = loader.get_template('project/add_project.html')
    context = RequestContext(request, {
    })
    return HttpResponse(template.render(context))


def project_list(request):
    """
    This function will render project list template with data
    :return: template
    """
    project_module_query = """select id, (m_name::json)->>'English' as \"module_name_english\",
                   (m_name::json)->>'Bangla' as \"module_name_bangla\", 
                    module_type, applicable_for, 
                   \"order\",node_parent as node, icon, list_def_id::text, 
                   xform_id::text, status, publish_status, archive, starting_year, ending_year 
                   from module_definition where archive = 0 and node_parent = any(select id from 
                   module_definition where node_parent is null) order by \"order\""""
    archive_module_query = """select id, (m_name::json)->>'English' as \"module_name_english\",
                       (m_name::json)->>'Bangla' as \"module_name_bangla\", 
                        module_type, applicable_for, 
                       \"order\",node_parent as node, icon, list_def_id::text, 
                       xform_id::text, status, publish_status, archive, starting_year, ending_year 
                       from module_definition where archive = 1 and node_parent = any(select id from 
                       module_definition where node_parent is null) order by \"order\""""
    project_module_df = db_fetch_dataframe(project_module_query)
    project_module_df = project_module_df.fillna('')
    project_module_data = project_module_df.to_dict('records')

    archive_module_df = db_fetch_dataframe(archive_module_query)
    archive_module_df = archive_module_df.fillna('')
    archive_module_data = archive_module_df.to_dict('records')

    template = loader.get_template('project/project_list.html')
    context = RequestContext(request, {
        'project_module_data': project_module_data,
        'archive_module_data': archive_module_data
    })
    return HttpResponse(template.render(context))


def module_profile(request, module_id):
    """
    This function will render module profile
    :return: template
    """
    template_html = ''
    child_module_data = {}
    child_archived_module_data = {}
    module_data = db_fetch_dataframe("""select  (m_name::json)->>'English' as \"module_name_english\" , 
                                    m.*, created_at::date as created_date,  l.id_string, (select is_project
                                    from module_definition where id = m.node_parent) as parent_is_project 
                                    from module_definition m left join logger_xform l 
                                    on l.id = m.xform_id where m.id = %s""" % (module_id)).to_dict('r')[0]
    print module_data
    if module_data['module_type'] == Constants.MODULE_TYPE_CONTAINER:
        template_html = 'module_profile.html'
        child_module_query = """select id, (m_name::json)->>'English' as \"module_name_english\",
                        (m_name::json)->>'Bangla' as \"module_name_bangla\", module_type as module_type_id, 
                        (case when module_type='1' then 'New Entry' when 
                    module_type='2' then 'List' when module_type='3' then 'Container' end ) module_type ,
                    applicable_for, xform_id, 
                    \"order\",node_parent as node, icon, list_def_id::text, xform_id::text, created_at::date,archive,publish_status,status 
                    from module_definition  where archive = 0 and node_parent = %s order by \"order\"""" % (module_id)
        child_module_df = pandas.read_sql(child_module_query, connection)
        child_module_df = child_module_df.fillna('')
        child_module_data = child_module_df.to_dict('records')

        child_archived_module_query = """select id, (m_name::json)->>'English' as \"module_name_english\",
                                (m_name::json)->>'Bangla' as \"module_name_bangla\", module_type as module_type_id, 
                                (case when module_type='1' then 'New Entry' when 
                            module_type='2' then 'List' when module_type='3' then 'Container' end ) module_type ,
                            applicable_for, xform_id, 
                            \"order\",node_parent as node, icon, list_def_id::text, xform_id::text, created_at::date,archive,publish_status,status 
                            from module_definition  where archive = 1 and node_parent = %s order by \"order\"""" % (
            module_id)
        child_archived_module_df = pandas.read_sql(child_archived_module_query, connection)
        child_archived_module_df = child_archived_module_df.fillna('')
        child_archived_module_data = child_archived_module_df.to_dict('records')

    print template_html
    template = loader.get_template('module/module_profile.html')
    context = RequestContext(request, {
        'child_module_list': child_module_data,
        'child_archived_module_data': child_archived_module_data,
        'module_id': module_id,
        'module': module_data,
    })
    return HttpResponse(template.render(context))


def add_module(request, parent_id=None):
    """
    this function will create new module
    :param request: request param
    :return: template
    """

    redirect_url = request.GET.get('next')

    parent_module_name = __db_fetch_single_value(
        "select (m_name::json)->>'English' as \"module_name_english\" from module_definition where id =%s" % (
            parent_id))
    module_type_list = (('1', 'New Entry'), ('2', 'List'), ('3', 'Container'))
    form_query = "select id, title from logger_xform where id = any(select xform_id from xform_config_data where status= 0)"
    form_list = __db_fetch_values(form_query)
    module_applicable_list = [['ulo', 'ULO'], ['lab', 'LAB']]
    template = loader.get_template('module/add_module.html')

    if request.method == 'POST':
        uploaded_file_url = ''
        module_name_bangla = request.POST.get('module_name_bangla')
        module_name_english = request.POST.get('module_name_english')
        module_type = request.POST.get('module_type')
        module_order = request.POST.get('module_order')
        node_parent = request.POST.get('node_parent')
        if module_type == Constants.MODULE_TYPE_ENTRY:
            xform_id = request.POST.get('xform_id')
        else:
            xform_id = 'null'
        if request.FILES:
            myfile = request.FILES['module_icon']
            uploaded_file_url = utility_functions.document_upload(myfile, myfile.name, 'module_icon')

        parent_module = parent_id
        module_order = request.POST.get('module_order')
        applicable_for = request.POST.get('applicable_for')
        print
        applicable_for
        m_name = {'English': module_name_english, 'Bangla': module_name_bangla}

        try:
            insert_query = "INSERT INTO core.module_definition (m_name, module_type," \
                           " applicable_for, created_at, created_by,xform_id, node_parent, \"order\") " \
                           "VALUES('%s', '%s', '%s', now(), %d, %s, %s,%s) returning id;" % (json.dumps(m_name),
                                                                                             module_type,
                                                                                             applicable_for,
                                                                                             request.user.id, xform_id,
                                                                                             parent_module,
                                                                                             module_order)
            id = __db_commit_query(insert_query)

            update_query = "update core.module_definition set node_parent = %s," \
                           " \"order\" = %s, icon='%s' where id = %s" % (parent_module,
                                                                         module_order, uploaded_file_url, str(id))
            messages.success(request, '<i class="fa fa-check-circle"></i> Module Added successfully!',

                             extra_tags='alert-success crop-both-side')
            if redirect_url is None:

                return HttpResponseRedirect('/bhmodule/module-profile/' + str(parent_id) + '/')

            else:
                return HttpResponseRedirect(redirect_url)

        except:
            messages.success(request, '<i class="fa fa-check-circle"></i> Module Addition failed!',
                             extra_tags='alert-danger crop-both-side')

    context = RequestContext(request, {
        'module_type_choices': module_type_list,
        'form_choices': form_list,
        'module_applicable_choices': module_applicable_list,
        'parent_module_name': parent_module_name,
        'parent_id': parent_id,
        'redirect_url': redirect_url
    })
    return HttpResponse(template.render(context))


def edit_module(request, module_id):
    """
    this function will edit new module
    :param request: request param
    :return: template
    """
    redirect_url = request.GET.get('next')
    container_df = utility_functions.get_container_module()
    container_df = container_df[container_df.id != int(module_id)]
    module_query = "select id, (m_name::json)->>'English' as \"module_name_english\"," \
                   " (m_name::json)->>'Bangla' as \"module_name_bangla\", module_type, " \
                   "applicable_for, xform_id, icon, \"order\", node_parent from core.module_definition where id =" + module_id
    module_df = pandas.read_sql(module_query, connection)
    module_dict = module_df.to_dict('records')[0]
    if redirect_url is None:
        redirect_url = '/bhmodule/module-profile/' + str(module_dict['node_parent']) + '/'

    module_type_list = (('1', 'New Entry'), ('2', 'List'), ('3', 'Container'))
    form_query = "select id, title from logger_xform"
    form_list = __db_fetch_values(form_query)
    module_applicable_list = [['ulo', 'ULO'], ['lab', 'LAB']]
    template = loader.get_template('module/edit_module.html')
    if request.method == 'POST':
        module_name_bangla = request.POST.get('module_name_bangla')
        module_name_english = request.POST.get('module_name_english')
        module_type = request.POST.get('module_type')
        if module_type == Constants.MODULE_TYPE_ENTRY:
            xform_id = request.POST.get('xform_id')
            print
            xform_id
        else:
            xform_id = 'null'
        print xform_id
        applicable_for = request.POST.get('applicable_for')
        parent_module = request.POST.get('parent_module')
        if parent_module == '':
            parent_module = 'null'
            redirect_url = '/bhmodule/module-profile/' + str(module_id) + '/'
        module_order = request.POST.get('module_order')
        if request.FILES:
            myfile = request.FILES['module_icon']
            icon = utility_functions.document_upload(myfile, myfile.name, 'module_icon')
        else:
            icon = request.POST.get('icon')

        print applicable_for
        m_name = {'English': module_name_english, 'Bangla': module_name_bangla}
        update_query = "update core.module_definition set m_name='%s', module_type='%s'," \
                       "applicable_for='%s',updated_at=now(), updated_by = %d, xform_id=%s,node_parent = %s," \
                       " \"order\" = %s, icon='%s' " \
                       "where id = %s " % (json.dumps(m_name), module_type,
                                           applicable_for, request.user.id, xform_id, parent_module,
                                           module_order, icon, module_id)
        __db_commit_query(update_query)
        messages.success(request, '<i class="fa fa-check-circle"></i> Module Edited successfully!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponseRedirect(redirect_url)

    context = RequestContext(request, merge_dicts(module_dict, {
        'module_type_choices': module_type_list,
        'form_choices': form_list,
        'module_applicable_choices': module_applicable_list,
        'module_id': module_id,
        'module_list': container_df.to_dict('r'),
        'redirect_url': redirect_url

    }))
    return HttpResponse(template.render(context))


@login_required
def module_list(request):
    """
    this function will render Module List template
    :param request: request param
    :return: template
    """
    module_query = "select id, (m_name::json)->>'English' as \"module_name_english\"," \
                   " (m_name::json)->>'Bangla' as \"module_name_bangla\", " \
                   "(case when module_type='1' then 'New Entry' when " \
                   "module_type='2' then 'List' when module_type='3' then 'Container' end ) module_type, " \
                   "applicable_for, (select title from logger_xform where id = xform_id) as xform_id, " \
                   "\"order\",node_parent as node from core.module_definition "
    module_df = pandas.read_sql(module_query, connection)
    temp_df = module_df[['id', 'module_name_english']]
    temp_df.columns = ['node', 'node_parent']
    module_df = module_df.merge(temp_df, on="node", how="left")
    module_df = module_df.fillna('')
    module_data = module_df.to_dict('records')
    template = loader.get_template('module_list.html')
    context = RequestContext(request, {
        'module_list': json.dumps(module_data)
    })
    return HttpResponse(template.render(context))


@login_required
def upload_shared_file(file, title):
    if file:
        # get system time in miliseconds
        millis = int(round(time.time() * 1000))
        filePath = title + '_' + str(millis) + '_' + str(file.name).replace(' ', '_')
        destination = open('onadata/media/shared_file/' + filePath, 'w+')
        for chunk in file.chunks():
            destination.write(chunk)
        destination.close()
    return filePath


@login_required
@csrf_exempt
def update_module_properties(request, module_id):
    current_module_query = "select id, (m_name::json)->>'English' as \"module_name_english\",node_parent,icon, \"order\" from core.module_definition where id=" + module_id
    current_module = __db_fetch_values(current_module_query)[0]
    module_query = "select id, (m_name::json)->>'English' as \"module_name_english\" from core.module_definition where module_type='3' and id !=" + module_id
    module_data = __db_fetch_values(module_query)
    template = loader.get_template('module_properties.html')
    uploaded_file_url = ''
    if request.method == 'POST':
        node_parent = request.POST.get('node_parent')
        if request.FILES:
            # img_file = upload_shared_file(request.FILES['module_icon'], current_module[1])
            myfile = request.FILES['module_icon']
            # fs = FileSystemStorage()
            # filename = fs.save(current_module[1].strip().replace(" ","_")+'_'+myfile.name, myfile)
            #
            # uploaded_file_url = fs.url(filename)
            # print uploaded_file_url
            millis = int(round(time.time() * 1000))
            filePath = current_module[1].strip().replace(" ", "_") + '_' + str(millis) + '_' + str(myfile.name).replace(
                ' ', '_')
            destination = open('onadata/media/shared_file/' + filePath, 'w+')
            for chunk in myfile.chunks():
                destination.write(chunk)
            destination.close()
            uploaded_file_url = filePath
        if node_parent == '0':
            parent_module = 'null'
        else:
            parent_module = request.POST.get('parent_module')
        module_order = request.POST.get('module_order')
        try:
            update_query = "update core.module_definition set node_parent = %s, \"order\" = %s, icon='%s' where id = %s" % (
                parent_module, module_order, uploaded_file_url, module_id)
            cursor = connection.cursor()
            cursor.execute(update_query)
            cursor.close()
            messages.success(request, '<i class="fa fa-check-circle"></i> Property Updated Successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/bhmodule/module-list')
        except:
            messages.success(request, '<i class="fa fa-check-circle"></i> Property settings failed!',
                             extra_tags='alert-danger crop-both-side')

    context = RequestContext(request, {
        'module_id': module_id,
        'module_name': current_module[1],
        'node_parent': current_module[2],
        'icon': current_module[3],
        'order': current_module[4],
        'module_list': module_data
    })
    return HttpResponse(template.render(context))


def index(request):
    q = "select auth_user.id,username,email,(select organization from usermodule_organizations where id = organisation_name_id) as organization,usermodule_organizationrole.role from auth_user left join usermodule_usermoduleprofile on usermodule_usermoduleprofile.user_id = auth_user.id left join usermodule_userrolemap on usermodule_userrolemap.user_id = usermodule_usermoduleprofile.user_id left join usermodule_organizationrole on usermodule_organizationrole.id = usermodule_userrolemap.role_id where usermodule_usermoduleprofile.organisation_name_id =(select organisation_name_id from usermodule_usermoduleprofile where user_id = " + str(
        request.user.id) + ")"
    users = __db_fetch_values_dict(q)
    # print users
    template = loader.get_template('list_config.html')
    context = RequestContext(request, {
        'users': users
    })
    return HttpResponse(template.render(context))


# ------------------------------Module Entry -----------------------------

@login_required
def module_entry_config(request, module_id):
    """
    This function will render Entry Type Module Config Template
    :param request: request param
    :param module_id: `str` Module Id
    :return: template
    """
    datasource = __db_fetch_values_dict("select id, title from core.datasource_definition")
    table_list = __db_fetch_values_dict(
        "SELECT table_name,table_name as \"name\" FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' AND table_schema='core' ")
    template = loader.get_template('entry_config.html')

    query = "select xform_id,entry_type,publish_status,status,custom_settings from " \
            "core.module_definition where id=" + module_id + " and xform_id is not null"
    form_entry = __db_fetch_values(query)[0]
    xform_id = form_entry[0]
    input_columns = __db_fetch_values_dict("select distinct(field_name) field_name from "
                                           "xform_extracted where xform_id = " + str(xform_id) + " and "
                                                                                                 "Not (field_type =  any (array['repeat','group','username','gps','start','end','photo','geopoint',"
                                                                                                 "'note','calculate','end']))")

    print
    form_entry
    entry_type = form_entry[1]
    edited = False
    if entry_type is not None:
        edited = True

    context = RequestContext(request, {
        'module_id': module_id,
        'datasource_type_choices': datasource_type,
        'datasource_choices': json.dumps(datasource),
        'table_choices': json.dumps(table_list),
        'entry_type': entry_type,
        'publish_status': form_entry[2],
        'status': form_entry[3],
        'custom_settings': form_entry[4],
        'edited': edited,
        'form_input_list': json.dumps(input_columns),

    })
    return HttpResponse(template.render(context))


@csrf_exempt
def add_entry_config(request, module_id):
    """
    This function will add Entry Type Module Config in DB
    :param request: request param
    :param module_id: `str` Module Id
    :return: template
    """
    redirect_url = request.GET.get('next')
    if redirect_url is None:
        redirect_url = '/bhmodule/module-profile/' + module_id + '/'
    post_dict = dict(request.POST.iterlists())
    entry_type = Constants.MODULE_TYPE_ENTRY
    entry_info = 'null'
    publish = 'false'
    status = 'true'
    if 'publish' in post_dict:
        publish = post_dict['publish'][0]
    if 'status' in post_dict:
        status = post_dict['status'][0]

    publish = 1 if publish == 'true' else 0
    status = 0 if status == 'true' else 1
    # print post_dict
    entry_data = {}

    if 'entry_info' in post_dict:
        entry_info = json.loads(post_dict['entry_info'][0])
        print entry_info
        # entry_data = {}
        if 'entry_type' in entry_info:
            entry_type = entry_info['entry_type']
        if entry_type == Constants.ENTRY_TYPE_CUSTOM:
            if 'searching_attribute' in entry_info and entry_info['searching_attribute'] != '':
                entry_data['searching_attribute'] = entry_info['searching_attribute']
            entry_data['search_field_name_english'] = entry_info['search_field_name_english']
            entry_data['search_field_name_bangla'] = entry_info['search_field_name_bangla']
            entry_data['datasource_type'] = entry_info['datasource_type']
            entry_data['datasource'] = entry_info['datasource']
            column_def = get_column_def(entry_info, None)
            entry_data['col_def'] = column_def

    update_query = "update core.module_definition set entry_type= %s, " \
                   "custom_settings='%s',status=%d, publish_status=%d, " \
                   "updated_at=now(), updated_by = %d where id = %s " % (entry_type,
                                                                         json.dumps(entry_data), status, publish,
                                                                         request.user.id, module_id)
    print
    update_query
    __db_commit_query(update_query)
    messages.success(request, '<i class="fa fa-check-circle"></i> Module Edited successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponse(redirect_url, status=200)


# ------------------------------Module Entry -----------------------------

# ------------------------------Module Container -----------------------------

@login_required
def module_container_config(request, module_id):
    """
    this function will Render configuration template of container module
    :param request: request param
    :module_id: `str` Module ID
    :return: template
    """
    datasource = __db_fetch_values("select id, title from core.datasource_definition")
    table_list = __db_fetch_values_dict(
        """SELECT table_name,table_name as \"name\" FROM information_schema.tables
         WHERE table_type='BASE TABLE' AND table_schema='core' """)
    template = loader.get_template('container_config.html')

    query = "select publish_status, status from " \
            "core.module_definition where id=" + module_id + ""
    form_entry = __db_fetch_values(query)[0]

    edited = False
    if form_entry is not None:
        edited = True

    context = RequestContext(request, {
        'module_id': module_id,
        'publish_status': form_entry[0],
        'status': form_entry[1],
        'edited': edited,

    })

    return HttpResponse(template.render(context))


@csrf_exempt
def add_container_config(request, module_id):
    """
    this function will save configuration of container module
    :param request: request param
    :module_id: `str` Module ID
    :return: template
    """
    redirect_url = request.GET.get('next')
    if redirect_url is None:
        redirect_url = '/bhmodule/module-profile/' + module_id + '/'
    post_dict = dict(request.POST.iterlists())
    publish = 'false'
    status = 'true'
    if 'publish' in post_dict:
        publish = post_dict['publish'][0]
    if 'status' in post_dict:
        status = post_dict['status'][0]

    publish = 1 if publish == 'true' else 0
    status = 0 if status == 'true' else 1

    update_query = "update core.module_definition set status=%d, " \
                   "publish_status=%d, updated_at=now(), updated_by = %d " \
                   "where id = %s " % (status, publish, request.user.id, module_id)
    print
    update_query
    __db_commit_query(update_query)
    messages.success(request, '<i class="fa fa-check-circle"></i> Module Edited successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponse(redirect_url, status=200)


# ------------------------------Module Container -----------------------------

# ------------------------------Module List -----------------------------

@login_required
def module_list_config(request, module_id):
    """
    this function will Render Configurable Template of List module
    :param request: request param
    :module_id: `str` Module ID
    :return: template
    """
    query = "select list_def_id,status,publish_status from core.module_definition " \
            "where id=" + module_id + " and list_def_id is not null"
    module_list = __db_fetch_values(query)
    filter_type = {'number': 'Number', 'single_select': 'Single Select',
                   'multiple_select': 'Multiple Select', 'date': 'Date', 'text': 'Text'}
    form_query = "select id, title from logger_xform"
    form_list = __db_fetch_values(form_query)
    form_choices_lookup = __db_fetch_values_dict(form_query)

    datasource = __db_fetch_values_dict("select id, title from core.datasource_definition")
    table_list = __db_fetch_values_dict("SELECT table_name,table_name as \"name\" FROM "
                                        "information_schema.tables WHERE table_type='BASE TABLE'"
                                        " AND table_schema='core'")

    if len(module_list) == 0:
        template = loader.get_template('list_config.html')
        context = RequestContext(request, {
            'filter_type': filter_type,
            'module_id': module_id,
            'table_choices': json.dumps(table_list),
            'datasource_choices': json.dumps(datasource),
            'datasource_type_choices': datasource_type,
            'column_data_type': data_type,
            'form_choices': form_list,
            'form_choices_lookup': json.dumps(form_choices_lookup)
        })
        return HttpResponse(template.render(context))

    else:
        list_id = module_list[0][0]
        print
        list_id
        list_def_query = "SELECT  list_name, column_definition, datasource, " \
                         "filter_definition,datasource_type::text FROM core.list_definition " \
                         "where id=%s" % (list_id)
        list_def = __db_fetch_values(list_def_query)[0]
        datasource_name = list_def[2]
        column_def = list_def[1]
        list_name = json.loads(list_def[0])
        template = loader.get_template('list_config_edit.html')

        context = RequestContext(request, {
            'filter_type': filter_type,
            'module_id': module_id,
            'table_choices': json.dumps(table_list),
            'datasource_choices': json.dumps(datasource),
            'datasource': datasource,
            'datasource_name': datasource_name,
            'datasource_type_choices': datasource_type,
            'column_data_type': data_type,
            'list_name': list_name,
            'column_def': json.dumps(column_def),
            'filter_def': json.dumps(list_def[3]),
            'list_id': list_id,
            'datasource_type': str(list_def[4]),
            'publish': module_list[0][2],
            'status': module_list[0][1],
            'form_choices': form_list,
            'form_choices_lookup': json.dumps(form_choices_lookup)
        })
        return HttpResponse(template.render(context))


def create_list_link(link_name, list_id, publish):
    """
    This Function is to create link in the menu if a list is published 
    by the user otherwise delete the link
    @param link_name: `str` this name will be shown as link name
    @param list_id: `str` list id as string
    @return:
    """
    print "Publish"
    print publish
    if publish == 1:
        exist_query = "select count(*) from usermodule_menuitem " \
                      "where url = '/bhmodule/list-view/generate/" + list_id + "/'"
        exist_count = __db_fetch_single_value(exist_query)
        if exist_count == 0:
            query = "INSERT INTO core.usermodule_menuitem" \
                    "(title, url, list_class, icon_class, parent_menu_id, sort_order)" \
                    "VALUES('" + link_name + "', '/bhmodule/list-view/generate/" + list_id + "/'," \
                                                                                             " 'top-level-menu__item', 'fas fa-chart-bar', 35, 0);"
            __db_commit_query(query)

    else:
        try:
            menu = MenuItem.objects.get(url='/bhmodule/list-view/generate/' + list_id + '/')
            # deletes the menu as well as role wise menu map
            menu.delete()
        except Exception as ex:
            print (ex)


@csrf_exempt
def add_module_list(request, module_id):
    """
    this function will save configuration of List module
    :param request: request param
    :module_id: `str` Module ID
    :return: template
    """
    redirect_url = request.GET.get('next')
    if redirect_url is None:
        redirect_url = '/bhmodule/module-profile/' + module_id + '/'
    post_dict = dict(request.POST.iterlists())
    list_id = None
    print
    post_dict
    if 'list_id' in post_dict:
        list_id = post_dict['list_id'][0]

    publish = 'false'
    status = 'true'
    if 'publish' in post_dict:
        publish = post_dict['publish'][0]
    if 'status' in post_dict:
        status = post_dict['status'][0]

    publish = 1 if publish == 'true' else 0
    status = 0 if status == 'true' else 1

    # print publish
    # print status
    sort_column = None
    if 'sort_list[]' in post_dict:
        sort_column = post_dict['sort_list[]']

    col_def = json.loads(post_dict['col_def'][0])
    filter_def = json.loads(post_dict['filter_def'][0])
    basic_def = json.loads(post_dict['basic_info'][0])
    total_col_def = get_column_def(col_def, sort_column)
    # print json.dumps(total_col_def)
    total_filter_def = get_filter_def(filter_def)
    datasource_type = basic_def['datasource_type']
    list_name_dict = {'English': basic_def['list_name_english'], 'Bangla': basic_def['list_name_bangla']}
    datasource = basic_def['list_datasource']

    if list_id is None:

        query = "INSERT INTO core.list_definition (list_name, column_definition, datasource, filter_definition, created_at, created_by,datasource_type,status ) " \
                "VALUES('%s','%s','%s','%s',now(),%d,%s,1) returning id" % (
                    json.dumps(list_name_dict), json.dumps(total_col_def), datasource, json.dumps(total_filter_def),
                    request.user.id, datasource_type)
        # print query
        id = __db_insert_query(query)
        if id is not None:
            messages.success(request, '<i class="fa fa-check-circle"></i> Module List settings updated!',
                             extra_tags='alert-success crop-both-side')
            update_query = "update core.module_definition set list_def_id = " + str(id) + " where id = " + module_id
            __db_commit_query(update_query)
            return HttpResponse('/bhmodule/module-profile/' + str(module_id) + '/', status=200)

    else:
        # print post_dict
        query = "update core.list_definition set list_name='%s', column_definition = '%s',datasource='%s', filter_definition='%s', updated_at=now(), updated_by=%d,datasource_type =%s,publish_status=%d,status=%d where id = %s" % (
            json.dumps(list_name_dict), json.dumps(total_col_def), datasource, json.dumps(total_filter_def),
            request.user.id, datasource_type, publish, status, list_id)
        __db_commit_query(query)
        # print json.dumps(total_col_def)
        query = " update core.module_definition set status=%d, publish_status=%d where id = %s" % (
            status, publish, module_id)
        __db_commit_query(query)
        # to publish the link
        create_list_link(basic_def['list_name_english'], list_id, publish)
        messages.success(request, '<i class="fa fa-check-circle"></i> Module List settings updated!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponse('/bhmodule/module-profile/' + module_id + '/', status=200)


@csrf_exempt
def add_list_workflow(request, list_id):
    post_dict = dict(request.POST.iterlists())
    print
    post_dict
    flow_info = json.loads(post_dict['form_info'][0])
    definition_list = []
    title = {}
    workflow_type = 'entry'
    details_pk = ''
    if 'workflow_type' in flow_info:
        workflow_type = flow_info['workflow_type']
    if 'details_pk' in flow_info:
        details_pk = flow_info['details_pk']
    if 'xform_id' in flow_info and flow_info['xform_id'] != '':
        xform_id = flow_info['xform_id']
    else:
        xform_id = 'NULL'
    if 'workflow_label_bangla' in flow_info:
        title['Bangla'] = flow_info['workflow_label_bangla']
    if 'workflow_label_english' in flow_info:
        title['English'] = flow_info['workflow_label_english']
    # if 'status' in post_dict:
    #     status = post_dict['status'][0]

    workflow_keys = set()
    keys = flow_info.keys()
    definition_dict = {}
    for key in keys:
        def_dict = {}
        if '@data_embed_form' in key:
            workflow_keys.add(key.split('@data_embed_form')[0])
            def_dict['form_field'] = flow_info[key]
            def_dict['column'] = key.split('@data_embed_form')[0]
            definition_list.append(def_dict)

    query = "INSERT INTO core.list_workflow (title, workflow_definition, xform_id, created_at, created_by, list_id,workflow_type, details_pk) " \
            "VALUES('%s','%s',%s,now(),%d,%s,'%s','%s');" % (
                json.dumps(title), json.dumps(definition_list), xform_id, request.user.id, list_id, workflow_type,
                details_pk)
    __db_commit_query(query)
    __db_commit_query("""update core.list_definition set updated_at = now() where id = %s """ % list_id)
    messages.success(request, '<i class="fa fa-check-circle"></i> Module List settings updated!',
                     extra_tags='alert-success crop-both-side')

    return HttpResponse('List Workflow updated!', status=200)


@csrf_exempt
def fetch_lookup_info(request, list_id):
    field_name = request.POST.get('field_name')
    lookup_col_def = __db_fetch_single_value("""
            select col_def from core.vw_list_definition where list_id = %s and field_name = '%s'
            """ % (list_id, field_name))
    return HttpResponse(json.dumps(lookup_col_def))


@csrf_exempt
def save_lookup_info(request, list_id):
    try:
        lookup_definition = {}
        lookup_datasource_type = request.POST.get('lookup_datasource_type')
        lookup_target_field = request.POST.get('lookup_target_field')
        if lookup_datasource_type in ['datasource', 'table']:
            lookup_datasource = request.POST.get('lookup_datasource_list')
            match_lookup_column = request.POST.get('match_lookup_column')
            return_lookup_column = request.POST.get('return_lookup_column')
            if lookup_datasource_type == 'datasource':
                lookup_query = datasource_query_generate(lookup_datasource)
            elif lookup_datasource_type == 'table':
                lookup_query = 'select * from ' + str(lookup_datasource)

            lookup_definition['datasource'] = lookup_datasource
            lookup_definition['query'] = lookup_query
            lookup_definition['match_column'] = match_lookup_column
            lookup_definition['return_column'] = return_lookup_column
        elif lookup_datasource_type == 'label':
            source_form_id = request.POST.get('source_form_id')
            source_form_field = request.POST.get('source_form_field')

            lookup_definition['form_id'] = source_form_id
            lookup_definition['form_field'] = source_form_field

        print """
        select col_def from core.vw_list_definition where list_id = %s and field_name = '%s'
        """ % (list_id, lookup_target_field)

        lookup_col_def = __db_fetch_single_value("""
        select col_def from core.vw_list_definition where list_id = %s and field_name = '%s'
        """ % (list_id, lookup_target_field))

        lookup_definition['lookup_type'] = lookup_datasource_type

        lookup_col_def['lookup_definition'] = lookup_definition

        list_rest_col_def = __db_fetch_values_dict("""
        select col_def from core.vw_list_definition where list_id = %s and field_name != '%s'
        """ % (list_id, lookup_target_field))
        print "***************************************"
        print lookup_col_def
        final_col_def = [dict(lrcd['col_def']) for lrcd in list_rest_col_def]
        final_col_def.append(lookup_col_def)
        __db_commit_query("""
        update core.list_definition set column_definition = '%s'::json, updated_at = now() where id = %s
        """ % (json.dumps(final_col_def).replace("'", "''"), list_id))
        return HttpResponse(json.dumps({'success': True}))
    except Exception as ex:
        print str(ex)
        return HttpResponse(json.dumps({'success': False}))


@csrf_exempt
def add_lookup_column(request, list_id):
    query = "select column_definition::json from core.list_definition where id=" + list_id + " "
    col_def = __db_fetch_values(query)[0][0]
    print col_def
    post_dict = dict(request.POST.iterlists())
    # print post_dict
    lookup_dict = {}
    lookup_dict['sortable'] = True
    lookup_dict['data_type'] = 'lookup'
    lookup_dict['format'] = ""
    lookup_dict['field_name'] = ""
    lookup_info = json.loads(post_dict['form_info'][0])
    english_title = ''
    bangla_title = ''
    query = ''
    datasource = ''
    return_column = ''
    condition_list = []
    if 'lookup_title_english' in lookup_info:
        english_title = lookup_info['lookup_title_english']
    if 'lookup_title_bangla' in lookup_info:
        bangla_title = lookup_info['lookup_title_bangla']

    lookup_dict['label'] = {'Bangla': bangla_title, 'English': english_title}

    if 'lookup_datasource' in lookup_info:
        query = datasource_query_generate(lookup_info['lookup_datasource'])
        datasource = lookup_info['lookup_datasource']
    if 'lookup_return_column' in lookup_info:
        return_column = lookup_info['lookup_return_column']

    keys_list = lookup_info.keys()
    condition_key_list = [x for x in keys_list if 'lookup_source_column' in x]
    print condition_key_list

    for condition_key in condition_key_list:
        temp_condition = {}
        temp_condition['name'] = lookup_info[condition_key]
        condition_type = lookup_info[condition_key.replace('source_column', 'condition_type')]
        temp_condition['type'] = 'static' if condition_type == '1' else 'list'
        if condition_type == '1':
            temp_condition['value'] = lookup_info[condition_key.replace('source_column', 'condition_value')]
        else:
            temp_condition['column'] = lookup_info[condition_key.replace('source_column', 'condition_column')]
        condition_list.append(temp_condition)
    print condition_list

    lookup_dict['lookup_definition'] = {'datasource': datasource, 'query': query, 'return_column': return_column,
                                        'condition': condition_list}

    print lookup_dict
    col_def.append(lookup_dict)
    query = """update core.list_definition set column_definition = '%s', updated_at = now() where id = %s""" % (
        json.dumps(col_def).replace("'", "''"), list_id)
    __db_commit_query(query)
    messages.success(request, '<i class="fa fa-check-circle"></i> Module List settings updated!',
                     extra_tags='alert-success crop-both-side')

    return HttpResponse('/bhmodule/module-list/', status=200)

    # if isinstance(object, list):


def get_filter_def(filter_def):
    keys = filter_def.keys()
    field_list = set()
    total_filter_def = []

    for key in keys:
        field_list.add(key.split('_filter@')[0])

    for field in field_list:
        english_label = field + '_filter@english'
        bangla_label = field + '_filter@bangla'
        type = field + "_filter@type"
        appearance_type = field + '_filter@appearnace'
        searchable = field + '_filter@searchable'
        dependant = field + '_filter@dependant'
        parent = field + '_filter@parent'
        order = field + '_filter@order'
        temp_dict = {}
        label = {}
        appearance = {}
        dependency = []

        # table filter def
        temp_dict['name'] = field
        if english_label in filter_def:
            label['English'] = filter_def[english_label]
        if bangla_label in filter_def:
            label['Bangla'] = filter_def[bangla_label]
        if type in filter_def:
            temp_dict['type'] = filter_def[type]
        if appearance_type in filter_def:
            if filter_def[appearance_type] != '':
                appearance['type'] = filter_def[appearance_type]
        if searchable in filter_def:
            appearance['searchable'] = True
        if dependant in filter_def:
            if parent in filter_def:
                # print isinstance(filter_def[parent])
                if isinstance(filter_def[parent], list):
                    print "here in list"
                    temp_dict['dependency'] = filter_def[parent]
                else:
                    temp_dict['dependency'] = [filter_def[parent]]
        if order in filter_def and filter_def[order] != '':
            temp_dict['order'] = filter_def[order]
        else:
            temp_dict['order'] = 0

        temp_dict['appearance'] = appearance
        temp_dict['label'] = label
        total_filter_def.append(temp_dict)

    return total_filter_def


def get_column_def(col_def, sort_column):
    keys = col_def.keys()
    field_list = set()
    total_col_def = []
    if sort_column is not None:
        field_list = sort_column
        print "in sort list"
        print field_list
    else:
        for key in keys:
            if '@' in key:
                field_list.add(key.split('@')[0])
    # print field_list
    for field in field_list:
        lookup_definition = field + '@lookup_flag'
        lookup_lookup_type = field + '@lookup_lookup_type'
        lookup_match_column = field + '@lookup_match_column'
        lookup_datasource = field + '@lookup_datasource'
        lookup_return_column = field + '@lookup_return_column'
        lookup_query = field + '@lookup_query'
        lookup_form_id = field + '@lookup_form_id'
        lookup_form_field = field + '@lookup_form_field'
        english_label = field + '@english'
        bangla_label = field + '@bangla'
        sortable = field + "@sortable"
        format = field + '@format'
        data_type = field + '@data_type'
        is_hidden = field + '@is_hidden'
        is_exportable = field + '@is_exportable'
        order = field + '@order'
        temp_dict = {}
        label = {}

        # table column def
        temp_dict['field_name'] = field
        if english_label in col_def:
            label['English'] = col_def[english_label]
        if bangla_label in col_def:
            label['Bangla'] = col_def[bangla_label]
        temp_dict['label'] = label

        if lookup_definition in col_def:
            temp_dict['lookup_definition'] = {}
            if lookup_lookup_type in col_def:
                temp_dict['lookup_definition']['lookup_type'] = col_def[lookup_lookup_type]
            if lookup_match_column in col_def:
                temp_dict['lookup_definition']['match_column'] = col_def[lookup_match_column]
            if lookup_datasource in col_def:
                temp_dict['lookup_definition']['datasource'] = col_def[lookup_datasource]
            if lookup_return_column in col_def:
                temp_dict['lookup_definition']['return_column'] = col_def[lookup_return_column]
            if lookup_query in col_def:
                temp_dict['lookup_definition']['query'] = col_def[lookup_query]
            if lookup_form_id in col_def:
                temp_dict['lookup_definition']['form_id'] = col_def[lookup_form_id]
            if lookup_form_field in col_def:
                temp_dict['lookup_definition']['form_field'] = col_def[lookup_form_field]

        if sortable in col_def:
            temp_dict['sortable'] = True
        else:
            temp_dict['sortable'] = False

        if is_hidden in col_def:
            temp_dict['hidden'] = True
        else:
            temp_dict['hidden'] = False

        if is_exportable in col_def:
            temp_dict['exportable'] = True
        else:
            temp_dict['exportable'] = False

        if format in col_def:
            temp_dict['format'] = col_def[format]

        if data_type in col_def:
            temp_dict['data_type'] = 'text'
        else:
            temp_dict['data_type'] = 'text'

        if order in col_def and col_def[order] != '':
            temp_dict['order'] = col_def[order]
        else:
            temp_dict['order'] = 0
        print temp_dict
        ##optional for some cases
        destination_input = field + '@destination_input'
        if destination_input in col_def:
            if col_def[destination_input] != '':
                temp_dict['destination_input'] = col_def[destination_input]

        total_col_def.append(temp_dict)
    print total_col_def
    return total_col_def


# ------------------------------Module List End -----------------------------

@csrf_exempt
def get_form_column(request, xform_id):
    query = "select distinct(field_name) field_name from xform_extracted where xform_id =" + xform_id + " and field_type not in ('repeat','group','note','username')"
    column_df = pandas.read_sql(query, connection)
    column_dict = column_df.to_dict('records')
    return HttpResponse(json.dumps(column_dict))


@csrf_exempt
def get_column_details(request):
    post_dict = request.POST
    source_name = post_dict["datasource_name"]

    if 'datasource_type' in post_dict:
        datasource_type = post_dict['datasource_type']
        print datasource_type
        if datasource_type == 'datasource':
            query = datasource_query_generate(source_name)
            query = query + " limit 1"
            df = pandas.DataFrame()
            df = pandas.read_sql(query, connection)
            column_dict = []
            for col in df.columns:
                temp_dict = {'column_name': col}
                column_dict.append(temp_dict)
            return HttpResponse(json.dumps(column_dict))

    query = "SELECT column_name, data_type  FROM information_schema.columns WHERE table_name = '" + source_name + "'"
    # column_dict = __db_fetch_values_dict(query)
    column_df = pandas.DataFrame()
    column_df = pandas.read_sql(query, connection)
    column_dict = column_df.to_dict('records')

    return HttpResponse(json.dumps(column_dict))


# --------------------------- List Generation In server -------------------

@login_required
def get_list_workflow(request, list_id):
    """This function renders related json data of list workflow

    Args:
        request ([GET]): []
        list_id (str): List Id

    Returns:
        [json]: json data of list workflow
    """
    workflow_df = utility_functions.get_list_workflow(list_id)
    print workflow_df
    workflow_dict = workflow_df.to_dict('r')
    return HttpResponse(json.dumps(workflow_dict))


def get_list_action(list_id, data_df):
    print data_df.head(2)
    html_button = ''
    followup_forms = ''
    workflow_df = utility_functions.get_list_workflow(list_id)
    workflow_dict = workflow_df.to_dict('r')
    for each in workflow_dict:
        if each['workflow_type'] == 'entry':
            followup_forms += '<option><a href="#">' + each['title']['English'] + '</a></option>'
        elif each['workflow_type'] == 'details':
            html_button += '<a class="tooltips btn" data-placement="top" data-container="body" data-original-title="View" href="/bhmodule/list-profile/' + \
                           data_df[each['workflow_definition']['pk_form_field']] + '/">Details</a>'
    if followup_forms != '':
        followup_forms = """<div class="btn-group">
  
  <button type="button" value="Followup Forms" class="btn btn-danger dropdown-toggle" data-toggle="dropdown">
    <span class="caret"></span>
    <span class="sr-only">Toggle Dropdown</span>
  </button>
  <ul class="dropdown-menu" role="menu">
    %s
  </ul>
</div>""" % (followup_forms)
    data_df['Action'] = followup_forms + html_button
    return data_df


@login_required
def module_list_generate(request, list_id):
    """
    This Function generates list and related Filter
    @param request:
    @param list_id:
    @return:
    """
    list_def, data_df, action_df = get_list_definition(list_id)
    list_name = list_def['list_name']

    workflow_df = utility_functions.get_list_workflow(list_id)

    language_list = list_name.keys()

    filter_def = list_def['filter_definition']
    print "Before Filter sorting"
    try:
        # sorting Filter accroding to order
        filter_def = pandas.DataFrame(filter_def)
        filter_def['order'] = filter_def['order'].astype(int)
        filter_df = filter_def.sort_values(by=['order'], ascending=True)

        print filter_df
        filter_def = filter_df.to_dict('r')
    except Exception as ex:
        print ex
    final_filter = OrderedDict()
    print filter_def
    for i in range(len(filter_def)):
        filter = filter_def[i]
        field_name = filter['name']
        if filter['type'] == 'single_select' or filter['type'] == 'multiple_select':
            if "dependency" in filter:
                dependant = filter['dependency']
                temp_list = dependant[:]
                temp_list.append(field_name)
                related_data = data_df[temp_list].drop_duplicates().to_dict('records')

                for dep in dependant:
                    if dep not in final_filter:
                        final_filter[dep] = {'related_data': related_data, 'child': [field_name]}
                    else:
                        final_filter[dep]['related_data'] = related_data

                        if 'child' in final_filter[dep]:
                            if field_name not in final_filter[dep]['child']:
                                final_filter[dep]['child'].append(field_name)
                        else:
                            final_filter[dep]['child'] = [field_name]

            field_lookup_info = __db_fetch_values_dict("""
            with t1 as(with t as (select jsonb_array_elements(column_definition::jsonb) as column_definition from core.list_definition ld where id = %s)
            select column_definition::json->>'field_name' as field_name,(column_definition::json->>'lookup_definition')::json as lookup_definition from t)
            select field_name,lookup_definition->>'lookup_type' as lookup_type,
            lookup_definition->>'form_id' as form_id,
            lookup_definition->>'form_field' as form_field,
            lookup_definition->>'query' as query,
            lookup_definition->>'match_column' as match_column,
            lookup_definition->>'return_column' as return_column
            from t1 where lookup_definition is not null
            and field_name = '%s'
            """ % (list_id, field_name))

            if field_lookup_info:
                if field_lookup_info[0]['lookup_type'] == 'label':
                    lookup_df = pandas.read_sql("""
                    select value_text,value_label from instance.xform_extracted where xform_id = %s and field_name = '%s'
                    """ % (field_lookup_info[0]['form_id'], field_lookup_info[0]['form_field']), connection)
                    print lookup_df
                    field_data = [{'value': rw['value_text'], 'name': rw['value_label']} for idx, rw in
                                  lookup_df.iterrows()]
                else:
                    lookup_df = pandas.read_sql(field_lookup_info[0]['query'],connection)
                    field_data = [{'value': rw[field_lookup_info[0]['match_column']], 'name': rw[field_lookup_info[0]['return_column']]} for idx, rw in
                                  lookup_df.iterrows()]
            else:
                field_data = data_df[field_name].unique().tolist()
                field_data = [{'value': fd, 'name': fd} for fd in field_data]


            print field_data

            filter['field_data'] = field_data

        if field_name not in final_filter:
            final_filter[field_name] = filter
        else:
            final_filter[field_name].update(filter)

    template = loader.get_template('list_view.html')
    context = RequestContext(request, {'list_id': list_id, 'title': list_name['English'],
                                       'filter_def': json.dumps(final_filter)})

    return HttpResponse(template.render(context))


def get_list_definition(list_id):
    """
    To gather list related data and configuration definition
    @param list_id: `str`
    @return: list definition , Data dataframe
    """
    query = "select id, list_name::json ,column_definition::json,filter_definition::json, datasource_type, datasource from core.list_definition where id=" + list_id
    list_df = pandas.read_sql(query, connection)
    list_def = list_df.to_dict('records')[0]

    workflow_query = "select title::json,list_id,workflow_definition,workflow_type,xform_id,id, details_pk from list_workflow where list_id=any(array[%s])" % (
        list_id)
    workflow_df = pandas.read_sql(workflow_query, connection)

    action_df = workflow_df[workflow_df['list_id'] == list_def['id']]

    datasource_type = list_def['datasource_type']
    datasource = list_def['datasource']

    if datasource_type == 1:
        data_query = "select * from " + datasource
    else:
        data_query = datasource_query_generate(datasource)

    data_df = pandas.read_sql(data_query, connection)

    return list_def, data_df, action_df


def get_list_data(list_def, data_df, action_df):
    """
    Formatting Data according to column Definition and renaming column name
    @param list_def: `dict` List Definintion dictionary
    @param data_df: 'dataframe`  List as dataframe format
    @return: `dict`formatted column name as well as data formatted according to list_Def
    """
    has_workflow = False
    column_def = list_def['column_definition']
    if not action_df.empty:
        has_workflow = True

    try:
        # sorting column according to order
        col_df = pandas.DataFrame(column_def)
        col_df['order'] = col_df['order'].astype(int)
        col_df = col_df.sort_values(by=['order'], ascending=True)
        # print col_df
        column_def = col_df.to_dict('r')
    except Exception as ex:
        print ex
    column_list = [column['field_name'] for column in column_def if column['data_type'] != 'lookup']
    column_dict = {column['field_name']: column['label']['English'] for column in column_def}
    if has_workflow:
        column_list.append('instanceid')
        # column_list.append('Action')
        # column_dict['Action'] = 'Action'
        column_dict['instanceid'] = 'instanceid'
        # data_df['Action'] = 'Action'

    after_lookup_column_list = column_list
    hidden_cols = []
    counter = 0
    for col_def in column_def:
        counter = counter + 1
        left_on_lst = []
        right_on_lst = []
        if col_def['hidden'] == True:
            hidden_cols.append(col_def['field_name'])
        if 'lookup_definition' in col_def:
            if isinstance(col_def['lookup_definition'], dict):
                if col_def['lookup_definition']['lookup_type'] != 'label':
                    lookup_match = col_def['lookup_definition']['match_column']
                    lookup_return = col_def['lookup_definition']['return_column']
                    lookup_df = pandas.read_sql(col_def['lookup_definition']['query'], connection)
                    column_dict[col_def['lookup_definition']['return_column'] + '_' + str(counter)] = col_def['label'][
                        'English']
                    # after_lookup_column_list.remove(col_def['field_name'])
                    # after_lookup_column_list.append(col_def['lookup_definition']['return_column'] + '_' + str(counter))
                    after_lookup_column_list = map(
                        lambda x: x if x != col_def['field_name'] else col_def['lookup_definition'][
                                                                           'return_column'] + '_' + str(counter),
                        after_lookup_column_list)

                    left_on_lst.append(str(col_def['field_name']))
                    right_on_lst.append(str(lookup_match) + '_' + str(counter))
                    if left_on_lst and right_on_lst:
                        data_df = pandas.merge(data_df.astype(str),
                                               lookup_df.astype(str).add_suffix('_' + str(counter)),
                                               how='left', left_on=left_on_lst,
                                               right_on=right_on_lst)
                else:
                    lookup_form_id = col_def['lookup_definition']['form_id']
                    lookup_form_field = col_def['lookup_definition']['form_field']
                    lookup_df = pandas.read_sql("""
                    select value_text,case
		                when value_label like '{"%' then value_label::json->>'English'
		                else value_label 
	                end as value_label from instance.xform_extracted xe where xform_id = """ + str(
                        lookup_form_id) + """ and field_name = '""" + str(lookup_form_field) + """'
                    """, connection)
                    left_on_lst.append(str(col_def['field_name']))
                    right_on_lst.append('value_text_' + str(counter))
                    after_lookup_column_list = map(
                        lambda x: x if x != col_def['field_name'] else 'value_label_' + str(counter),
                        after_lookup_column_list)
                    column_dict['value_label_' + str(counter)] = col_def['label'][
                        'English']
                    if left_on_lst and right_on_lst:
                        data_df = pandas.merge(data_df.astype(str),
                                               lookup_df.astype(str).add_suffix('_' + str(counter)),
                                               how='left', left_on=left_on_lst,
                                               right_on=right_on_lst)

    if has_workflow:
        # column_list.append('instanceid')
        after_lookup_column_list.append('Action')
        column_dict['Action'] = 'Action'
        # column_dict['instanceid'] = 'instanceid'
        data_df['Action'] = 'Action'
        for dfidx, dfrw in data_df.iterrows():
            action_text = ''
            instance_id = dfrw['instanceid']
            for idx, row in action_df.iterrows():
                button_title = row['title']['English']
                form_id_string = __db_fetch_single_value(
                    "select id_string from logger_xform where id = %s" % row['xform_id'])
                form_owner_username = __db_fetch_single_value(
                    "select username from instance.auth_user where id = (select user_id from instance.logger_xform lx where id = %s)" %
                    row['xform_id'])
                mapping_cols = [str(d['column']) for d in row['workflow_definition']]
                mapping_fields = [str(d['form_field']) for d in row['workflow_definition']]
                data_json_list = [[mapping_fields[idxx], dfrw[md]] for idxx, md in enumerate(mapping_cols)]
                if row['workflow_type'] == 'entry':
                    get_part = ''
                    for djl in data_json_list:
                        get_part += '&' + djl[0] + '=' + ('' if djl[1] is None else djl[1])
                    action_text += '<a style="margin: 0 5px 5px 0;" target="_blank" href="/add/' + form_id_string + '?' + get_part + '" class="btn red pull-right"><i class="fa fa-plus" aria-hidden="true"></i> ' + button_title + '</a>'
                elif row['workflow_type'] == 'details':
                    details_pk_value = dfrw[row['details_pk']]
                    instances = __db_fetch_values("select instanceid from core.bahis_%s_table where %s = '%s'" % (
                        form_id_string, row['details_pk'], details_pk_value))
                    if instances:
                        for ins in instances:
                            action_text += '<a style="margin: 0 5px 5px 0;" target="_blank" href="/' + form_owner_username + '/forms/' + form_id_string + '/instance/?s_id=' + \
                                           ins[0] + '#/' + ins[
                                               0] + '" class="btn red pull-right"><i class="fa fa-info-circle" aria-hidden="true"></i> ' + button_title + '</a>'
            try:
                data_df.at[dfidx, 'Action'] = action_text
            except Exception as ex:
                dfrw['Action'] = action_text

    data_df = data_df[after_lookup_column_list]
    data_df = data_df.drop_duplicates()
    export_df = data_df
    data_df = data_df.drop(hidden_cols, axis=1)

    data_df.rename(columns=column_dict, inplace=True)
    export_df.rename(columns=column_dict, inplace=True)
    data_df = data_df.fillna('')
    export_df = export_df.fillna('')
    data_list = data_df.values.tolist()
    col_names = data_df.columns.tolist()

    data = {"col_name": col_names, 'data_list': data_list}

    return data,export_df


def get_export_data(list_def, data_df):
    """
    Formatting Data according to column Definition and renaming column name
    @param list_def: `dict` List Definintion dictionary
    @param data_df: 'dataframe`  List as dataframe format
    @return: `dict`formatted column name as well as data formatted according to list_Def
    """
    column_def = list_def['column_definition']
    # column_list = [column['field_name'] for column in column_def if column['exportable'] ]
    column_list = [column['field_name'] for column in column_def if
                   (column['exportable'] if 'exportable' in column else False)]
    column_dict = {column['field_name']: column['label']['English'] for column in column_def}

    #data_df = data_df[column_list]
    #data_df.rename(columns=column_dict, inplace=True)
    #data_df = data_df.fillna('')
    file_path = utility_functions.excel_file(data_df, list_def['list_name']['English'])
    print file_path
    return file_path


@csrf_exempt
def filtered_data(request, list_id):
    """
    This function filter data according to according to ajax request
    @param request:
    @param list_id: `str`
    @return: json
    """
    post_dict = dict(request.POST.iterlists())
    filter_dict = json.loads(post_dict['filter_data'][0])
    list_def, data_df, action_df = get_list_definition(list_id)
    keys = filter_dict.keys()

    filter_def = list_def['filter_definition']

    for filter in filter_def:
        field_name = filter['name']

        if any(field_name + '@filter' in s for s in keys):
            print("filter_type")
            print(filter['type'])
            if filter['type'] == 'single_select':
                data_df = data_df[data_df[field_name] == filter_dict[field_name + '@filter']]
            elif filter['type'] == 'multiple_select':
                data_df = data_df[data_df[field_name].isin(filter_dict[field_name + '@filter[]'])]
            elif filter['type'] == 'date':
                date_range = filter_dict[field_name + '@filter']
                start_date = date_range.strip().split(' - ')[0]
                end_date = date_range.strip().split(' - ')[1]
                data_df =  data_df[data_df[field_name].isin(pandas.date_range(start_date, end_date))]
            elif filter['type'] == 'text':
                condition = filter_dict[field_name + '@filter_condition']
                input1 = filter_dict[field_name + '@filter_input1']

                if condition == 'contains':
                    equation = data_df[field_name].str.contains(input1)
                if condition == 'startswith':
                    equation = data_df[field_name].str.startswith(input1)
                if condition == 'endswith':
                    equation = data_df[field_name].str.endsswith(input1)
                elif condition == '=':
                    equation = data_df[field_name] == input1
                data_df = data_df[equation]

    data,export_df = get_list_data(list_def, data_df, action_df)
    # parsing data excel file
    data['filePath'] = get_export_data(list_def, export_df)
    return HttpResponse(json.dumps(data))


# --------------------------- List Generation In server End -------------------


# --------------------------- Module Access -----------------------------------

@csrf_exempt
@login_required
def module_access(request, module_id):
    """
     This function Save and show access info of module rolewise
    @param request:
    @param module_id: `str`
    @return: template
    """
    if request.method == 'POST':
        print "Hello"
        print request.POST
        bulk_query = ''
        new_access = request.POST.getlist('access_id')
        for val in new_access:
            insert_query = "INSERT INTO core.modulerolemap" \
                           "(role_id, module_id, created_at, created_by)" \
                           "VALUES(%s, %s, now(), %d);" \
                           % (val, module_id, request.user.id)
            bulk_query += insert_query

        __db_commit_query("delete  from modulerolemap where module_id = %d" % (int(module_id)))
        if bulk_query != '':
            # __db_commit_query("delete  from modulerolemap;")
            __db_commit_query(bulk_query)

        # messages.success(request, '<i class="fa fa-check-circle"></i>'
        #                           ' Access List has been updated successfully!',
        #                  extra_tags='alert-success crop-both-side')
        # return HttpResponseRedirect('/bhmodule/module-profile/'+module_id+'/')

    module_query = "select id,'module_'||id::text as \"name\", " \
                   "(m_name::json)->>'English' as \"module_name_english\"," \
                   "node_parent, is_project from module_definition where  id = %d" % (int(module_id))
    module_df = db_fetch_dataframe(module_query)
    module_dict = module_df.to_dict('r')[0]
    print module_dict['is_project']
    if module_dict['is_project']:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]

        all_organizations = \
            get_recursive_organization_children(current_user.organisation_name, [])
        org_id_list = [org.pk for org in all_organizations]
        org_id_string = ",".join(str(x) for x in org_id_list)
        role_query = "select id, role from usermodule_organizationrole where organization_id = any (array[" + org_id_string + "])"
        roles = __db_fetch_values_dict(role_query)

    else:
        query = """Select ur.id, role from modulerolemap m, usermodule_organizationrole ur 
            where m.role_id = ur.id and module_id = %d""" % (int(module_dict['node_parent']))
        roles = __db_fetch_values_dict(query)

    query = "Select role_id from modulerolemap where module_id = %d" % (int(module_id))
    main_df = pandas.read_sql(query, connection)
    accessible_roles_list = main_df['role_id'].tolist()

    template = loader.get_template('module_access_v2.html')
    context = RequestContext(request, {

        'access_dict': accessible_roles_list,
        'roles': roles,
        'module_dict': module_dict
    })

    return HttpResponse(template.render(context))


# -------------------- Module Catchment Area ----------------------------

@csrf_exempt
@login_required
def add_children(request):
    """
    this function will fetch children of a root catchment area
    :param request: request param
    :return: json
    """
    id = request.POST.get('id')
    query = "select value,name from geo_cluster where parent = " + str(id) + ""
    all = __db_fetch_values(query)

    list_of_dictionary = []
    for child in all:
        id_ch, name = child[0], child[1]
        query = "select value from geo_cluster where parent =" + str(id_ch) + "limit 1"
        value = __db_fetch_values(query)
        if value:
            true = True
        else:
            true = False
        temp = {"id": id_ch, "text": name, "hasChildren": true, "children": []}
        list_of_dictionary.append(temp)

    return HttpResponse(json.dumps({'id': id, 'list_of_dictionary': list_of_dictionary}))


def get_module_check_nodes(module_id):
    query = "select * from module_catchment_area where module_id = " + str(module_id) + " and deleted_at is null"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    check_nodes = df.geoid.tolist()
    return check_nodes


@login_required
def module_catchment_tree(request, module_id):
    """
    this function will fetch all catchment data related to module
    :param request: request param
    :return: template
    """
    redirect_url = request.GET.get('next')
    print redirect_url
    query = "select * from geo_cluster where parent=-1"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    code = df.value.tolist()
    name = df.name.tolist()
    all = zip(code, name)
    list_of_dictionary = []
    start = time.time()

    for code, name in all:
        query = "select value from geo_cluster where parent =" + str(code) + " limit 1"
        df = pandas.read_sql(query, connection)
        if len(df.value.tolist()):
            true = True
        else:
            true = False
        temp = {"id": code, "text": name, "hasChildren": true, "children": []}
        list_of_dictionary.append(temp)
    print list_of_dictionary
    datasource = json.dumps({'list_of_dictionary': list_of_dictionary})

    check_nodes = get_module_check_nodes(module_id)
    json_content_dictionary = []
    for each in check_nodes:
        if each:
            query_for_json = "select uploaded_file_path from geo_data where id = " + str(each) + ""
            df = pandas.DataFrame()
            df = pandas.read_sql(query_for_json, connection)
            # uploaded_file_path = df.uploaded_file_path.tolist()[0]
            # if uploaded_file_path != "cd":
            #     file = open(uploaded_file_path, 'r')
            #     json_content = file.read()
            #     file.close()
            # else:
            json_content = "{}"
            json_content_dictionary.append(json_content)
    print("END    " + str(time.time() - start))
    query = "select *, (m_name)::json->>'English' as name from module_definition where id=" + str(module_id)
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization = df.name.tolist()[0]

    query = "with recursive t as( select value, name, parent from geo_cluster where value in ( select geoid from module_catchment_area where module_id = " + str(
        module_id) + " and deleted_at is null) union all select geo_cluster.value, geo_cluster.name, geo_cluster.parent from geo_cluster, t where t.parent = geo_cluster.value ) select distinct value, name, parent from t order by value"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    parent_list = df.value.tolist()

    return render(request, "module/module_catchment_tree.html", {'redirect_url': redirect_url, 'datasource': datasource
        , 'organization_name': organization
        , 'check_nodes': check_nodes, 'module_id': module_id, 'json_content': json_content_dictionary,
                                                                 'parent_list': parent_list})


@login_required
def module_catchment_data_insert(request):
    """
    this function will insert all catchment data related to module
    :param request: request param
    :return: template
    """
    redirect_url = request.GET.get('next')
    result_set = request.POST.get('result_set').split(',')
    module_id = int(request.POST.get('module_id'))
    delete_prev_module_catchment_record(module_id)
    result_set = list(set(result_set))

    for each in result_set:
        if each:
            query = "INSERT INTO module_catchment_area (module_id, geoid,created_at,created_by,updated_at,updated_by) VALUES(" + str(
                module_id) + ", " + str(
                each) + ",now()," + str(request.user.id) + ",now()," + str(request.user.id) + ")"
            __db_commit_query(query)
            # sql = 'refresh materialized view vwunion_mat; refresh materialized view vwbranchcoverage_mat;refresh materialized view vwbranchunioncoverage;'
            # database(sql)
    __db_commit_query("""
    update core.module_definition set updated_at = now() where id = %s
    """ % module_id)
    return HttpResponseRedirect(redirect_url)


def delete_prev_module_catchment_record(module_id):
    """
    this function will remove previous catchment data related to module
    :param request: request param
    :return: template
    """
    query = "update module_catchment_area set deleted_at =now() where module_id = " + str(module_id) + " "
    __db_commit_query(query)


# -------------- MAster Data Category ----------------
@login_required
def category_list(request):
    """This function will render Catgory List template with data

    Args:
        request ([GET]):
    """
    delete_success = -1
    if request.GET.get('delete_success') is not None:
        delete_success = request.GET.get('delete_success')
    query = """SELECT row_number() OVER (ORDER BY m.id DESC) as sl, m.id, m.category_name as category, m.parent_id , c.category_name as parent_category 
    FROM master_category m left join master_category c on m.parent_id = c.id where m.active is true order by m.created_date desc;"""

    category_dict = utility_functions.__db_fetch_values_dict(query)

    template = loader.get_template('master_data/category_list.html')
    context = RequestContext(request, {
        'category_list': category_dict,
        'delete_success':delete_success
    })

    return HttpResponse(template.render(context))


@login_required
def category_add(request):
    """This function will render Add Category template with related data

    Args:
        request ([GET/POST]):
    """
    query = """SELECT id, category_name as category
    FROM master_category m where m.active is true;"""
    category_dict = utility_functions.__db_fetch_values(query)

    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        category_parent = request.POST.get('category_parent')
        category_parent = category_parent if category_parent != '' else 'null'

        insert_query = """INSERT INTO core.master_category(category_name, parent_id, created_by, 
        created_date, active)VALUES('%s', %s, %s, now(), true);""" % (
            category_name, category_parent, str(request.user.id))

        utility_functions.__db_commit_query(insert_query)

        messages.success(request, '<i class="fa fa-check-circle"></i>'
                                  ' Category Added successfully!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponseRedirect('/bhmodule/master-data-category/list/')

    print category_dict
    template = loader.get_template('master_data/category_add.html')
    context = RequestContext(request, {
        'category_list': category_dict
    })

    return HttpResponse(template.render(context))


@login_required
@csrf_exempt
def category_edit(request, category_id):
    """This function will render Edit Category template with related data

    Args:
        request ([GET/POST]):
    """
    # fetching all other category except the requested category
    query = """SELECT id, category_name as category
    FROM master_category m where m.active is true and id != %s;""" % (category_id)
    all_category_dict = utility_functions.__db_fetch_values(query)
    # fetching info of the requested category
    query = """SELECT id, category_name, parent_id as category
    FROM master_category  where  id = %s;""" % (category_id)
    category_data = utility_functions.__db_fetch_values(query)[0]
    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        category_parent = request.POST.get('category_parent')
        category_parent = category_parent if category_parent != '' else 'null'

        update_query = """update master_category set category_name='%s', parent_id = %s, 
        updated_by = %s, updated_date = now() where id = %s""" % (
            category_name, category_parent, str(request.user.id), category_id)

        utility_functions.__db_commit_query(update_query)

        messages.success(request, '<i class="fa fa-check-circle"></i>'
                                  ' Category Updated successfully!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponseRedirect('/bhmodule/master-data-category/list/')

    # print category_dict
    template = loader.get_template('master_data/category_add.html')
    context = RequestContext(request, {
        'category_list': all_category_dict,
        'category_id': category_id,
        'category_name': category_data[1],
        'category_parent': category_data[2],
    })

    return HttpResponse(template.render(context))


@login_required
@csrf_exempt
def category_delete(request, category_id):
    """This function will delete Category with related data

    Args:
        request ([GET/POST]):
    """
    try:
        delete_item_q = """delete from core.master_category_item where category_id = %s""" % category_id
        delete_cat_q = """delete from core.master_category where id = %s""" % category_id
        __db_commit_query(delete_item_q)
        __db_commit_query(delete_cat_q)
        return HttpResponseRedirect('/bhmodule/master-data-category/list/?delete_success=1')
    except Exception as ex:
        print(str(ex))
        return HttpResponseRedirect('/bhmodule/master-data-category/list/?delete_success=0')


@login_required
@csrf_exempt
def category_item_delete(request, category_id, item_id):
    """This function will delete Category item

    Args:
        request ([GET/POST]):
    """
    try:
        delete_item_q = """delete from core.master_category_item where category_id = %s and id = %s""" % (category_id,item_id)
        __db_commit_query(delete_item_q)
        return HttpResponseRedirect('/bhmodule/master-data-category/view/'+str(category_id)+'/?delete_success=1')
    except Exception as ex:
        print(str(ex))
        return HttpResponseRedirect('/bhmodule/master-data-category/view/'+str(category_id)+'/?delete_success=0')


@login_required
def category_item_list(request, category_id):
    """This function will render Catgory Item List template with data

    Args:
        request ([GET]):
        category_id (str): category id of the item
    """
    delete_success = -1
    if request.GET.get('delete_success') is not None:
        delete_success = request.GET.get('delete_success')
    category_name = utility_functions.__db_fetch_single_value(
        "select category_name from master_category where id = %s" % (category_id))
    query = """SELECT row_number() OVER (ORDER BY m.id DESC) as sl, m.id, m.name_eng, 
    m.name_bangla, m.value, p.name_eng as parent_category_value, p.category_id,
    (select category_name from master_category where id=p.category_id) as parent_category,
    m.parent_item_id FROM master_category_item m left join master_category_item p 
    on m.parent_item_id = p.id where m.category_id = %s; """ % (category_id)

    category_dict = utility_functions.__db_fetch_values_dict(query)

    template = loader.get_template('master_data/category_item_view.html')
    context = RequestContext(request, {
        'category_list': category_dict,
        'category_name': category_name,
        'category_id': category_id,
        'delete_success':delete_success
    })

    return HttpResponse(template.render(context))


@login_required
def category_item_add(request, category_id):
    """This function will render Catgory Item add

    Args:
        request ([GET/POST]):
        category_id (str): category id of the item
    """
    category_data = utility_functions.__db_fetch_values("""select category_name,  (select category_name 
                                                              from master_category where id=p.parent_id) as parent_category  
                                                              from master_category p where id = %s""" % (category_id))
    print (category_data)

    query = """SELECT m.id, m.name_eng
    FROM master_category_item m where m.category_id = any(select parent_id 
    from master_category where id = %s );""" % (category_id)
    parent_item_dict = utility_functions.__db_fetch_values(query)

    if request.method == 'POST':
        item_name_eng = request.POST.get('item_name_eng')
        item_name_bangla = request.POST.get('item_name_bangla')
        item_value = request.POST.get('item_value')
        parent_item = request.POST.get('parent_item')
        parent_item = '' if parent_item is None else parent_item
        print(parent_item)
        parent_item = parent_item if parent_item != '' else 'null'

        insert_query = """INSERT INTO master_category_item(name_eng, name_bangla, value, 
        category_id, parent_item_id, created_date) VALUES('%s', '%s', '%s', %s, %s, now());""" % (
            item_name_eng, item_name_bangla, item_value, category_id, parent_item)

        utility_functions.__db_commit_query(insert_query)

        messages.success(request, '<i class="fa fa-check-circle"></i>'
                                  'Category Item Added successfully!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponseRedirect('/bhmodule/master-data-category/view/' + category_id + '/')

    template = loader.get_template('master_data/category_item_add.html')
    context = RequestContext(request, {
        'parent_item_list': parent_item_dict,
        'category_name': category_data[0][0],
        'parent_category_name': category_data[0][1],
        'category_id': category_id,
    })

    return HttpResponse(template.render(context))


@login_required
def category_item_edit(request, category_id, item_id):
    """This function will render Catgory Item add

    Args:
        request ([GET/POST]):
        category_id (str): category id of the item
        item_id: id of the item
    """
    category_data = utility_functions.__db_fetch_values("""select category_name,  (select category_name 
                                                              from master_category where id=p.parent_id) as parent_category  
                                                              from master_category p where id = %s""" % (category_id))

    query = """SELECT m.id, m.name_eng
    FROM master_category_item m where m.category_id = any(select parent_id 
    from master_category where id = %s );""" % (category_id)
    parent_item_dict = utility_functions.__db_fetch_values(query)

    item_query = """select id, name_eng, name_bangla, value, parent_item_id 
    from master_category_item where id = %s""" % (item_id)
    item_data = utility_functions.__db_fetch_values_dict(item_query)[0]

    if request.method == 'POST':
        item_name_eng = request.POST.get('item_name_eng')
        item_name_bangla = request.POST.get('item_name_bangla')
        item_value = request.POST.get('item_value')
        parent_item = request.POST.get('parent_item')
        parent_item = '' if parent_item is None else parent_item
        parent_item = parent_item if parent_item != '' else 'null'

        update_query = """Update master_category_item set name_eng = '%s', name_bangla = '%s', value = '%s', 
        parent_item_id = %s, updated_date = now() where id = %s""" % (
            item_name_eng, item_name_bangla, item_value, parent_item, item_id)

        utility_functions.__db_commit_query(update_query)

        messages.success(request, '<i class="fa fa-check-circle"></i>'
                                  'Category Item Updated successfully!',
                         extra_tags='alert-success crop-both-side')

        return HttpResponseRedirect('/bhmodule/master-data-category/view/' + category_id + '/')

    template = loader.get_template('master_data/category_item_add.html')
    context = RequestContext(request, {
        'parent_item_list': parent_item_dict,
        'category_name': category_data[0][0],
        'parent_category_name': category_data[0][1],
        'category_id': category_id,
        'item_id': item_id,
        'item_data': item_data
    })

    return HttpResponse(template.render(context))


def delete_list_workflow(request, workflow_id):
    try:
        workflow_remove_query = "delete from core.list_workflow lw where id = " + str(workflow_id)
        __db_commit_query(workflow_remove_query)
        return HttpResponse(True)
    except Exception as ex:
        print(ex)
        return HttpResponse(False)


@csrf_exempt
def delete_datasource(request):
    datasource_id = request.POST.get('datasource_id')
    deleted = 0
    primary_dependent_cnt = __db_fetch_single_value("""
    with t as(select * from core.datasource_definition dd where p_source_type = 2)
	   select count(*) from t where p_source::int4 = %s
    """ % datasource_id)

    secondary_dependent_cnt = __db_fetch_single_value("""
        with t as(select * from core.datasource_definition dd where s_source_type = 2)
    select count(*) from t where s_source::int4 = %s
        """ % datasource_id)

    if primary_dependent_cnt == 0:
        if secondary_dependent_cnt == 0:
            __db_commit_query("""
            delete from core.datasource_definition dd where id = %s
            """ % datasource_id)
            deleted = 1
            message = 'Successfully deleted'
        else:
            message = 'This datasource is a dependency to another datasource/s, delete it/those first as secondary source'
    else:
        message = 'This datasource is a dependency to another datasource/s, delete it/those first as primary source'

    return HttpResponse(json.dumps({
        'deleted': deleted,
        'message': message
    }))


@csrf_exempt
def fetch_lookup_select_fields(request):
    form_id = request.POST.get('form_id')
    if form_id:
        form_fields = __db_fetch_values_dict("""
            with t as(select
                distinct field_name,
                case
                    when field_label like '{"%' then field_label::json->>'English'
                    else field_label
                end as field_label
            from
                instance.xform_extracted
            where
                field_type in ('select one', 'select all that apply')
                and xform_id = """ + str(form_id) + """)
                select field_name,replace(field_label,'''','') as field_label from t""")
        return HttpResponse(json.dumps(form_fields))
    else:
        return HttpResponse([])
