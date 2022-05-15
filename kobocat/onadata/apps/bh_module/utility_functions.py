import pandas
from django.db import connection
import os
import time
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from onadata.apps.main.database_utility import db_fetch_dataframe, __db_fetch_single_value_excption, \
    __db_fetch_values_dict, __db_fetch_values, __db_fetch_single_value, __db_commit_query, __db_insert_query, database


def get_module_dict(module_query, media_url):
    module_df = pandas.read_sql(module_query, connection)
    module_df = module_df.fillna('')
    root = module_df['node_parent'] == ''
    root_df = module_df[root]
    root_dict = root_df.drop(['node_parent'], axis=1).to_dict('records')
    module_dict = module_dict_generate(module_df)
    root_dict = get_children_dict(root_dict, module_df, media_url)

    return root_dict, module_dict


def get_children_dict(module_dict, module_df, media_url):
    final_dict = []
    for module in module_dict:
        child_df = module_df[module_df['node_parent'] == module['id']]
        child_dict = child_df.drop(['node_parent'], axis=1).to_dict('records')
        if 'xform_id' in module:
            if module['xform_id'] != '':
                module['xform_id'] = int(module['xform_id'])

        if 'img_id' in module:
            if module['img_id'] != '':
                module['img_id'] = media_url + module['img_id']

        module['children'] = get_children_dict(child_dict, module_df, media_url)
        final_dict.append(module)

    return final_dict


def module_dict_generate(module_df):
    module_dict = module_df.to_dict('records')
    final_dict = {}
    for module in module_dict:
        child_df = module_df[module_df['node_parent'] == module['id']]

        module['children'] = child_df['name'].tolist()
        final_dict[module['name']] = module
    return final_dict


def get_user_role(user_id):
    """
    this function will return user role
    :param user_id: `int` user ID
    :return: `int` role Id
    """
    query = """SELECT role_id FROM core.usermodule_userrolemap 
    where user_id = %d""" % (user_id)
    role_id = __db_fetch_single_value_excption(query)
    return role_id


def get_user_branch(user_id):
    """
    this function will return user branch
    :param user_id: `int` user ID
    :return: `dataframe` geo Definition
    """
    query = """SELECT branch_id FROM core.usermodule_userbranchmap
    where user_id = %d""" % (user_id)
    branch_id = __db_fetch_single_value_excption(query)
    return branch_id


def get_branch_catchment(branch_id):
    """
    this function will return branch catchment
    :param branch_id: `int` branch ID
    :return: `dataframe` geo Definition
    """

    geo_query = """with t as ( WITH RECURSIVE starting (id, value, name, parent, loc_type) 
    AS ( select id, value, name, parent, loc_type from core.geo_cluster where 
    value = any(select geoid from branch_catchment_area where 
    branch_id = %s and deleted_at is null) ), descendants (id, value, name, parent, loc_type) 
    AS ( SELECT id, value, name, parent, loc_type FROM starting AS s 
    UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type 
    FROM core.geo_cluster AS t JOIN descendants AS d ON t.parent = d.value ), 
    ancestors (id, value, name, parent, loc_type) AS ( SELECT t.id, t.value ,t.name, 
    t.parent, t.loc_type FROM core.geo_cluster AS t WHERE t.value IN (SELECT parent FROM starting) 
    UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type FROM core.geo_cluster AS t JOIN 
    ancestors AS a ON t.value = a.parent ) TABLE ancestors UNION ALL TABLE descendants) 
    select t.*, c.node_name as loc_name  from t 
    join core.geo_definition c on t.loc_type = c.id order by value asc ;""" % (str(branch_id))
    print(geo_query)
    geo_df = pandas.read_sql(geo_query, connection)
    geo_df = geo_df.fillna('')
    return geo_df


def get_module_catchment(module_id):
    """
    this function will return module catchment
    :param module_id: `int` module ID
    :return: `dataframe` geo Definition
    """
    '''
    geo_query = """with t as ( WITH RECURSIVE starting (id, value, name, parent, loc_type) 
    AS ( select id, value, name, parent, loc_type from core.geo_cluster where 
    value = any(select geoid from module_catchment_area where 
    module_id = %s and deleted_at is null) ), descendants (id, value, name, parent, loc_type) 
    AS ( SELECT id, value, name, parent, loc_type FROM starting AS s 
    UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type 
    FROM core.geo_cluster AS t JOIN descendants AS d ON t.parent = d.value ), 
    ancestors (id, value, name, parent, loc_type) AS ( SELECT t.id, t.value ,t.name, 
    t.parent, t.loc_type FROM core.geo_cluster AS t WHERE t.value IN (SELECT parent FROM starting) 
    UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type FROM core.geo_cluster AS t JOIN 
    ancestors AS a ON t.value = a.parent ) TABLE ancestors UNION ALL TABLE descendants) 
    select t.*, c.node_name as loc_name  from t 
    join core.geo_definition c on t.loc_type = c.id order by value asc ;"""%(str(module_id))
    '''

    geo_query = """with t as ( WITH RECURSIVE starting (id, value, name, parent, loc_type) 
    AS ( select id, value, name, parent, loc_type from core.geo_cluster where 
    value = any(select geoid from module_catchment_area where 
    module_id = %s and deleted_at is null) ), descendants (id, value, name, parent, loc_type) 
    AS ( SELECT id, value, name, parent, loc_type FROM starting AS s 
    UNION ALL SELECT t.id, t.value, t.name, t.parent, t.loc_type 
    FROM core.geo_cluster AS t JOIN descendants AS d ON t.parent = d.value ) TABLE descendants) 
    select t.*, c.node_name as loc_name  from t 
    join core.geo_definition c on t.loc_type = c.id order by value asc ;""" % (str(module_id))

    if module_id == 74:
        print(geo_query)
    geo_df = pandas.read_sql(geo_query, connection)
    geo_df = geo_df.fillna('')
    return geo_df


def document_upload(datafile, file_name, file_folder):
    file_name = file_name.replace(' ', '_')
    user_path_filename = os.path.join(settings.MEDIA_ROOT, file_folder)
    if not os.path.exists(user_path_filename):
        os.makedirs(user_path_filename)
    fs = FileSystemStorage(location=user_path_filename)

    myfile_name = str(int(round(time.time() * 1000))) + "_" + str(file_name) + "_" + str(datafile.name)
    filename = fs.save(myfile_name, datafile)
    full_file_path = "media/" + file_folder + "/" + myfile_name

    return full_file_path


def get_list_workflow(list_id):
    workflow_query = "select lx.title form_title, lw.title::json, list_id, workflow_definition, " \
                     "workflow_type,xform_id,lw.id, details_pk from list_workflow lw left join logger_xform lx on lx.id = lw.xform_id  where list_id=%s" % (
                         list_id)
    workflow_df = db_fetch_dataframe(workflow_query)
    return workflow_df


def get_container_module():
    # fetching all container module
    all_module_query = "select (m_name::json)->>'English' as \"module_name_english\" , *" \
                       "from core.module_definition where module_type='3'"
    df = db_fetch_dataframe(all_module_query)
    return df


# datasource Query generate
def datasource_query_generate(datasource_id):
    """
    This function generate query by arranging various parts of query accroding to the definition
    @param datasource_id: `str` datasource row unique id
    @return: `str` generated query as string
    """
    #print "Here I am"
    source_query = "SELECT  ds_name, title, p_source, p_source_type, s_source, s_source_type, " \
                   "column_mapping, columns_list FROM core.datasource_definition WHERE " \
                   "id = %s" % (datasource_id)
    datasource_df = pandas.read_sql(source_query, connection)
    # print datasource_df
    datasource = datasource_df.to_dict('records')[0]
    column_mapping = datasource['column_mapping']
    #print column_mapping

    where_query = ' where '
    group_query = ' group by '
    having_query = ' having '

    p_source_column = column_mapping['p_source']['column_names']
    p_queryset = get_subquery(datasource['p_source'], datasource['p_source_type'],
                              p_source_column, 'p')

    if 'operation' in column_mapping:
        operation = column_mapping['operation']
        operation_on = operation['on']
        operation_how = ''
        operation_type = operation['type']
        if operation_type == 'left Join':
            operation_type = 'Left Outer Join'

        s_source_column = column_mapping['s_source']['column_names']
        s_queryset = get_subquery(datasource['s_source'], datasource['s_source_type'],
                                  s_source_column, 's')
        view_query = 'with ' + p_queryset['source_query'] + ", " + s_queryset['source_query']
        join_string = " and ".join("cast(p." + operation['p_key'] + " as text) = cast(s."
                                   + operation['s_key'] + " as text)" for operation in operation_on)
        final_sub_query = 'select ' + p_queryset['column_string'] + ',' + s_queryset['column_string'] + ' ' \
                                                                                                        'from p ' + operation_how + ' ' + operation_type + ' s on ' + join_string

        if s_queryset['where_string'] != '':
            where_query += s_queryset['where_string']
        if s_queryset['group_by_string'] != '':
            group_query += s_queryset['group_by_string']
        if s_queryset['having_string'] != '':
            having_query += s_queryset['having_string']

    else:
        view_query = 'with ' + p_queryset['source_query']
        final_sub_query = ' select ' + p_queryset['column_string'] + ' from p '

    if p_queryset['where_string'] != '':
        # final_sub_query += where_query + ' and ' + p_queryset['where_string']
        final_sub_query += where_query + ('' if where_query == ' where ' else ' and ') + p_queryset['where_string']
    if p_queryset['group_by_string'] != '':
        final_sub_query += group_query + p_queryset['group_by_string']
    if p_queryset['having_string'] != '':
        final_sub_query += having_query + p_queryset['having_string']

    final_query = view_query + final_sub_query
    #print final_query
    return final_query


def get_subquery(source, source_type, source_column, flag):
    """
    This function is to generate subquery according to configuration
    @param source: `str` source_info
    @param source_type:  `int` source type. two types of source datasource and table
    @param source_column: `list`
    @param flag: `str` flag types (p for primary and s for secondary)
    @return: `dict` generated subquery as dictionary
    """
    if source_type == 2:
        source_query = datasource_query_generate(source)
        source_query = flag + ' as (' + source_query + ')'
    elif source_type == 1:
        # here general query of view created
        # here we are fetching unique column of every datasource
        unique_column_list = list(set([x['name'] for x in source_column]))
        column_query = ",".join('"' + x + '"' for x in unique_column_list)
        source_query = flag + ' as (select ' + column_query + " from " + source + " )"

    column_list = [get_column_query(x, flag) for x in source_column]
    column_string = ", ".join(x[0] for x in column_list)
    group_by_string = ", ".join(x[1] for x in column_list if x[1] != '')
    where_list = [condition_generate(x, flag) for x in source_column if 'condition' in x and 'agg_function' not in x]
    where_string = " and ".join(where_list)
    having_list = [condition_generate(x, flag) for x in source_column if 'condition' in x and 'agg_function' in x]
    having_string = " and ".join(having_list)
    # print "______________________"
    # print source_query
    # print column_string
    # print "______________________"
    return {'source_query': source_query,
            'column_string': column_string,
            'group_by_string': group_by_string,
            'where_string': where_string,
            'having_string': having_string}


def get_column_query(x, flag):
    """ This function is to generate query column string
    @param x: `dict` column definition dict
    @param flag: `str` flag types (p for primary and s for secondary)
    @return: `list` Formatted string list
    """
    final_string = flag + "." + x['name']
    if 'column_type' in x:
        # final_string = "cast(" + flag + "." + x['name'] + " as " + x['column_type'] + ")"
        final_string = "cast(" + flag + "." + x['name'] + " as " + (
            'numeric' if x['column_type'] == "number" else x['column_type']) + ")"

    group_by = ''
    if 'groupby' in x:
        group_by = flag + "." + x['name']

    if 'agg_function' in x:
        if 'agg_columntype' in x and x['agg_columntype'] != '':
            final_string = x['agg_function'] + "( cast(" + flag + "." + x['name'] + " as " + x['agg_columntype'] + "))"
        else:
            final_string = x['agg_function'] + "(" + flag + "." + x['name'] + ") "

    if 'rename' in x:
        final_string += " as \"" + x['rename'] + "\""
    else:
        final_string += " as \"" + x['name'] + "\""

    return [final_string, group_by]


def condition_generate(col_def, flag):
    """
    This function is to generate condition query string based on type and aggregate function
    @param col_def: `dict` column definition
    @param flag: `str` flag types (p for primary and s for secondary)
    @return: `str` generated string condition
    """
    condition, column_name = col_def['condition'], col_def['name']

    if 'agg_columntype' in col_def:
        column_type = 'numeric' if col_def['agg_columntype'] == 'number' else col_def['agg_columntype']
    else:
        column_type = 'numeric' if condition['column_type'] == 'number' else condition['column_type']

    if 'agg_function' in col_def:
        condition_start = col_def['agg_function'] + "( cast(" + flag + "." + column_name + " as " + column_type + "))"
    else:
        condition_start = " cast(" + flag + "." + column_name + " as " + column_type + ") "

    if condition['condition_type'] in ['between', 'not between']:
        input_string = " cast('" + condition['input1'] + "' as " + column_type + ') and ' + " cast('" + condition[
            'input2'] + "' as " + column_type + ") "
    elif condition['condition_type'] == 'like':
        input_string = " cast('%" + condition['input1'] + "%' as " + column_type + ") "
    else:
        input_string = " cast('" + condition['input1'] + "' as " + column_type + ") "

    condition_string = "(" + condition_start + " " + condition[
        'condition_type'] + " " + input_string + ")"
    # print "????????????????????????????"
    # print condition_string
    return condition_string


def excel_file(df, file_name):
    excel_file = file_name.replace(' ', '_') + '.xls'
    # current_user = UserModuleProfile.objects.filter(user=user)
    user_path_filename = os.path.join(settings.MEDIA_ROOT, "exported_file")
    if not os.path.exists(user_path_filename):
        os.makedirs(user_path_filename)

    filename = os.path.join(user_path_filename, excel_file)
    writer = pandas.ExcelWriter(filename, engine='xlwt')
    # Convert the dataframe to an XlsxWriter Excel object.
    df.to_excel(writer, sheet_name='Sheet1')
    # Close the Pandas Excel writer and output the Excel file.
    writer.save()

    return '/media/exported_file/' + excel_file
