from onadata.apps.main.database_utility import __db_fetch_single_value, \
    __db_commit_query, __db_fetch_values, __db_fetch_single_value_excption

import pandas as pd
from django.db import connection
import json
import decimal
from django.conf import settings

PROJECT_KEY_NAME  = settings.PROJECT_KEY_NAME
FORM_TABLE_SCHEMA = settings.FORM_TABLE_SCHEMA

from django.http import (
    HttpResponseRedirect, HttpResponse , Http404)



################## Data mapper #####################

def generate_table_schema(table_cols, form_id_string):
    """ Schema genetation process

        Parameters
        ----------
        table_cols : `list`
            List of colums to be created in table
        form_id_string : `str`,
            Form id string
    """
    if PROJECT_KEY_NAME:
        table_key_name = PROJECT_KEY_NAME
    else:
        table_key_name = 'xform'
        
    if FORM_TABLE_SCHEMA:
        table_schema = FORM_TABLE_SCHEMA
    else:
        table_schema = 'public'
    global schema_dict
    global sqlite_schema_text
    schema_text = '--' + str(form_id_string)
    sqlite_schema_text = '--' + str(form_id_string)
    schema_text += '\n'
    schema_text += '\n'
    sqlite_schema_text += '\n'
    sqlite_schema_text += '\n'
    schema_text = 'CREATE TABLE '+table_schema+'.'+table_key_name+'_' + str(form_id_string) + '_table '
    sqlite_schema_text = 'CREATE TABLE '+table_key_name+'_' + str(form_id_string) + '_table '
    schema_text += '\n'
    sqlite_schema_text += '\n'
    schema_text += '(id bigserial NOT NULL,'
    sqlite_schema_text += '(id INTEGER PRIMARY KEY AUTOINCREMENT,'
    schema_text += '\n'
    sqlite_schema_text += '\n'
    for table_col in table_cols:
        schema_text += str(table_col) + ' TEXT NULL'
        sqlite_schema_text += str(table_col) + ' TEXT'
        if table_cols.index(table_col) != len(table_cols) - 1:
            schema_text += ','
            schema_text += '\n'
            sqlite_schema_text += ','
            sqlite_schema_text += '\n'
    schema_text += ');'
    sqlite_schema_text += ');'
    schema_dict[table_key_name+'_' + str(form_id_string) + '_table'] = {}
    schema_dict[table_key_name+'_' + str(form_id_string) + '_table']['schema'] = schema_text
    schema_dict[table_key_name+'_' + str(form_id_string) + '_table']['sqlite_schema'] = sqlite_schema_text
    schema_dict[table_key_name+'_' + str(form_id_string) + '_table']['columns'] = table_cols
    # print "#########In every loop "+ form_id_string+"######"
    # print sqlite_schema_text


def create_table_script(form_elements, form_id_string, **kwargs):
    """
        Recursive function for generating flat table scripts

        Parameters
        ----------
        form_elements : `list`
            List of form elements
        form_id_string : `str`,
            Form id string

        **kwargs Parameters
        ----------------
        parent : `str`, optional
            parent table name for establishing the link
    """
    table_cols = []
    for form_element in form_elements:
        if form_element['type'] != 'repeat' and form_element['type'] != 'group':
            if form_element['name'] != 'end' and form_element['name'] != 'start':
                table_cols.append(form_element['name'])
        else:
            if form_element['type'] == 'repeat':
                create_table_script(form_element['children'], form_id_string + '_' + form_element['name'],
                                    parent=form_id_string + '_id')
            elif form_element['type'] == 'group':
                for fc in form_element['children']:
                    if fc['type'] != 'repeat':
                        table_cols.append(form_element['name'] + '_' + fc['name'])
                    else:
                        create_table_script(fc['children'], form_id_string + '_' + fc['name'],
                                            parent=form_id_string + '_id')

    if kwargs.has_key('parent'):
        table_cols.append(kwargs['parent'])
    table_cols.append('instanceid')
    table_cols.append('xform_id')
    
    generate_table_schema(table_cols, form_id_string)


def generate_or_update_flat_table(xform_id):
    """Process of generating flat table(s)
       scripts for a single forms

        Parameters
        ----------
        xform_id : `int`
            Xform Id fot the form
    """
    global schema_dict
    global sqlite_schema_text
    schema_dict = {}
    form_data = pd.read_sql("select id_string,json from logger_xform where id = " + str(xform_id), connection)
    form_def = json.loads(form_data.iloc[0]['json'])
    form_id_string = form_data.iloc[0]['id_string']
    form_elements = form_def['children']
    create_table_script(form_elements, form_id_string)

    # generate sqlite script
    sqlite_script = ''
    form_exists = __db_fetch_single_value(
        "select count(*) from xform_config_data where xform_id = " + str(xform_id))
    print form_exists

    # update or create flat in postgres database
    table_list = []
    for sd in schema_dict:
        tc = __db_fetch_single_value(
            "select count(*) as c from pg_catalog.pg_tables where tablename = '" + str(sd.lower()) + "'")
        print tc
        # print schema_dict[sd]['sqlite_schema']
        table_list.append(sd)
        sqlite_script += schema_dict[sd]['sqlite_schema']
        print(sqlite_script)
        if tc == 0:  # check whether the table already exists
            print schema_dict[sd]['schema']
            __db_commit_query(schema_dict[sd]['schema'])
        else:
            new_cols = schema_dict[sd]['columns'] + ['id']
            # get existing columns from table
            existing_table_columns = __db_fetch_values(
                "SELECT column_name FROM information_schema.columns WHERE table_name   = '" + str(
                    sd.lower()) + "'")
            ex_cols = [el[0] for el in existing_table_columns]
            alter_script = ''
            # check if new column has been added to the table
            for nc in new_cols:
                if nc.lower() not in ex_cols:
                    query = "ALTER TABLE " + str(sd.lower()) + " ADD column " + str(nc.lower()) + " TEXT NULL;\n"
                    __db_commit_query(query)
                    alter_script += query

            sqlite_script = alter_script

    print sqlite_script
    table_string = ",".join('"' + table + '"' for table in table_list)
    if form_exists > 0:

        sql_script = __db_fetch_single_value(
            "select sql_script from xform_config_data where xform_id = " + str(xform_id))
        print str(sql_script + sqlite_script)
        __db_commit_query(
            "update xform_config_data set sql_script = '" + str(sql_script +
                                                                       sqlite_script) + "', table_mapping='[" + table_string + "]' where xform_id=" + str(
                xform_id))
    else:
        print sqlite_script
        __db_commit_query(
            "insert into xform_config_data(xform_id,sql_script,table_mapping)values(" + str(
                xform_id) + ",'" + str(
                sqlite_script) + "','[" + table_string + "]')")
        
        
    if sqlite_script != '':
        __db_commit_query("INSERT INTO core.database_static_script (sql_script, created_at, xform_id) VALUES('"+str(
                            sqlite_script)+"', now(), "+str(xform_id)+");")



# ----------------- Data parse Start----------------


def generate_update_query(xform_id, instance_id):
    """
       Function to generate update query for edited instance
    """
    if check_parser_function(xform_id):
        try:
            function_name = __db_fetch_single_value("select function_name "
                                                             "from form_function where "
                                                             "form_id = " + str(xform_id))

            __db_commit_query("select * from "+function_name+"("+str(instance_id)+")")
            return True

        except Exception as ex:
            print(ex)
            return False

    global column_dict

    get_form_data(xform_id, instance_id)

    try:

        for key in column_dict.keys():
            value = column_dict[key]
            table_name = key

            tc = __db_fetch_single_value(
                "select count(*) as c from pg_catalog.pg_tables where tablename = '" + str(table_name) + "'")
            if tc == 0:
                return False

            if 'columns' in value:
                value_dict = value['columns']
                col_list = list(value_dict.keys())
                val_list = list(value_dict.values())
                # additional info added
                col_list.append('instanceid')
                val_list.append(str(instance_id))
                col_list.append('xform_id')
                val_list.append(str(xform_id))
                col_string = ','.join(col_list)

                val_string = ','.join("'" + x + "'" for x in val_list)
                query_string = "insert into " + table_name + " (" + col_string + ") values(" + val_string + ")"
                print("Main Query")
                print(query_string)
                __db_commit_query(query_string)

                if 'children' in value:
                    data_id = __db_fetch_single_value(
                        "select id from " + table_name + " where instanceid ='%s' " % (str(instance_id)))
                    child_list = value['children']
                    for child in child_list:

                        for k in child.keys():
                            child_table_name = k
                            child_col_list = []
                            child_val_list = []
                            child_data = child[k]
                            for col_name in child_data:
                                if col_name == 'parent':
                                    child_col_list.append(child_data[col_name])
                                    child_val_list.append(str(data_id))
                                else:
                                    child_col_list.append(col_name)
                                    child_val_list.append(child_data[col_name])

                            col_string = ','.join(child_col_list)
                            val_string = ','.join("'" + x + "'" for x in child_val_list)
                            query_string = "insert into " + child_table_name + " (" + col_string + ") values(" + val_string + ")"
                            print("child_query")
                            print(query_string)
                            __db_commit_query(query_string)

                return True
    except Exception as ex:
        print(ex)
        return False


def check_parser_function(xform_id):
    print ("in checking")
    function_name = __db_fetch_single_value_excption("select function_name "
                                                     "from form_function where "
                                                     "form_id = "+str(xform_id))
    if function_name == 0:
        return False
    else:
        return True


def generate_insert_query( xform_id, instance_id):
    """
    Process of generating query for the submitted form

    """
    if check_parser_function(xform_id):
        try:
            function_name = __db_fetch_single_value("select function_name "
                                                             "from form_function where "
                                                             "form_id = " + str(xform_id))

            __db_commit_query("select * from "+function_name+"("+str(instance_id)+")")
            return True

        except Exception as ex:
            print(ex)
            return False



    global column_dict

    get_form_data(xform_id, instance_id)
    print "Here Final Dict all-1"
    print (column_dict)
    print("Expecting here")
    print(column_dict.keys())
    col_list = []
    val_list = []
    try:
        for key in column_dict.keys():
            value = column_dict[key]
            table_name = key

            tc = __db_fetch_single_value(
                "select count(*) as c from pg_catalog.pg_tables where tablename = '" + str(table_name.lower()) + "'")
            if tc == 0:
                return False

            if 'columns' in value:
                value_dict = value['columns']
                for col in value_dict:
                    col_list.append(col)
                    val_list.append(value_dict[col])
                # additional info added
                col_list.append('instanceid')
                val_list.append(str(instance_id))
                col_list.append('xform_id')
                val_list.append(str(xform_id))
                col_string = ','.join(col_list)
                
                val_string = ','.join("'" + x + "'" for x in val_list)
                query_string = "insert into " + table_name + " (" + col_string + ") values(" + val_string + ")"
                print ("Main Query")
                print (query_string)
                __db_commit_query(query_string)

                if 'children' in value:
                    data_id = __db_fetch_single_value(
                        "select id from " + table_name + " where instanceid ='%s' " % (str(instance_id)))
                    child_list = value['children']
                    for child in child_list:

                        for k in child.keys():
                            child_table_name = k
                            child_col_list = []
                            child_val_list = []
                            child_data = child[k]
                            for col_name in child_data:
                                if col_name == 'parent':
                                    child_col_list.append(child_data[col_name])
                                    child_val_list.append(str(data_id))
                                else:
                                    child_col_list.append(col_name)
                                    child_val_list.append(child_data[col_name])

                            col_string = ','.join(child_col_list)
                            val_string = ','.join("'" + x + "'" for x in child_val_list)
                            query_string = "insert into " + child_table_name + " (" + col_string + ") values(" + val_string + ")"
                            print ("child_query")
                            print (query_string)
                            __db_commit_query(query_string)


                            #return True
        return True                            
    except Exception as ex:
        print("Exception occurred")
        print(ex)
        return False


def get_form_data(xform_id, instance_id):
    """
        Parsing form defination of the submitted form
    """
    global column_dict
    column_dict = {}
    form_data = pd.read_sql("select id_string,json from logger_xform where id = " + str(xform_id), connection)
    form_def = json.loads(form_data.iloc[0]['json'])
    form_id_string = form_data.iloc[0]['id_string']
    form_elements = form_def['children']
    data = pd.read_sql("select json from logger_instance where id = " + str(instance_id), connection)
    data_json = data.iloc[0]['json']
    create_query_script(form_elements, data_json, form_id_string)


def update_column_dict(table_cols, form_id_string, parent):
    global column_dict
    print
    table_cols, form_id_string, parent

    if PROJECT_KEY_NAME:
        table_key_name = PROJECT_KEY_NAME
    else:
        table_key_name = 'xform'

    parent_table_name = table_key_name +'_' +str(form_id_string) + '_table'
    if parent != '':
        child_table_name = table_key_name +'_' + str(form_id_string) + '_' + parent + '_table'
        table_cols['parent'] = form_id_string + '_id'
        child_dict = {child_table_name: table_cols}
        if parent_table_name in column_dict:
            if 'children' in column_dict[parent_table_name]:
                column_dict[parent_table_name]['children'].append(child_dict)
            else:
                column_dict[parent_table_name]['children'] = []
                column_dict[parent_table_name]['children'].append(child_dict)
        else:
            column_dict[parent_table_name] = {}
            column_dict[parent_table_name]['children'] = []
            column_dict[parent_table_name]['children'].append(child_dict)
    else:
        if parent_table_name in column_dict:
            column_dict[parent_table_name]['columns'] = table_cols
        else:
            column_dict[parent_table_name] = {}
            column_dict[parent_table_name]['columns'] = table_cols


def create_query_script(form_elements, data_json, form_id_string, **kwargs):
    """
        Recursive function for parsing form data

        Parameters
        ----------
        form_elements : `list`
            List of form elements
        data_json : `json`
            Form Data json
        form_id_string : `str`,
            Form id string

        **kwargs Parameters
        ----------------
        parent : `str`, optional
            parent table name for establishing the link
        group_name : `str`, optional
            parent group name for parsing data
    """
    table_cols = {}
    parent = ''
    group_name = ''
    table_string = ''
    if kwargs.has_key('parent'):
        parent = kwargs['parent']
    if kwargs.has_key('group_name'):
        group_name = kwargs['group_name']

    key_name = parent + '/' if parent != '' else ''
    key_name = group_name + '/' + key_name if group_name != '' else '' + key_name

    for form_element in form_elements:
        if form_element['type'] != 'repeat' and form_element['type'] != 'group':
            if form_element['name'] != 'end' and form_element['name'] != 'start':
                if key_name + form_element['name'] in data_json:
                    table_cols[form_element['name']] = data_json[key_name + form_element['name']]
        else:
            if form_element['type'] == 'repeat':
                print
                form_element['name']
                if key_name + form_element['name'] in data_json:
                    data_list = data_json[form_element['name']]
                    for data in data_list:
                        create_query_script(form_element['children'], data, form_id_string,
                                            parent=form_element['name'])
            elif form_element['type'] == 'group':
                group_parent = form_element['name']
                for fc in form_element['children']:
                    field_name = key_name + group_parent + '/' + fc['name']
                    if fc['type'] != 'repeat':
                        if field_name in data_json:
                            table_cols[form_element['name'] + '_' + fc['name']] = data_json[field_name]
                    else:
                        if field_name in data_json:
                            data_list = data_json[field_name]
                            for data in data_list:
                                create_query_script(fc['children'], data, form_id_string,
                                                    parent=fc['name'], group_name=form_element['name'])

    update_column_dict(table_cols, form_id_string, parent)

# ----------------- Data parse ----------------
