import string
import openpyxl
#from openpyxl.cell import get_column_letter
import psycopg2
import json
import os
import re
from collections import OrderedDict
import copy
import pandas as pd
from pandas import ExcelWriter


def getXLSQuestionType(q_type, repeat="false"):
    type = ""
    if q_type == "Group Question":
        type = "begin_repeat" if repeat == "true" else "begin group"
    elif q_type == "Select One":
        type = "select_one"
    elif q_type == "Multiple Select":
        type = "select_multiple"
    elif q_type == "Text":
        type = "text"
    elif q_type == "Number":
        type = "integer"
    elif q_type == "Note":
        type = "note"
    elif q_type == "DateTime":
        type = "dateTime"
    elif q_type == "Date":
        type = "date"
    elif q_type == "Decimal":
        type = "decimal"
    else:
        type = q_type
    return type


def parse_json(json_str, ql, cl):
    od = OrderedDict()
    cd = OrderedDict()
    if not isinstance(json_str, (list, dict)):
        json_str = json.loads(json_str)
    for node in json_str:
        question_type = node['type']
        question_name = node['name']
        question_label = node['label']

        required = '1' if node['mandatory'] == "yes" else ''
        required_message = node["requiredMessage"]

        repeat = str(node["repeat"])
        appearance = node["appearance"]
        list_name = node["list_name"] if "list_name" in node else ""
        readonly = ""
        relevant = ""
        choice_filter = ""
        constraint = ""
        constraint_message = ""
        calculation = ""
        jr_count = ""
        repeat_count = ""
        hint = node["hint"]
        relevance = node["logicList"]

        # if len(relevant)>0:
        #     for item in relevant:

        calculation = ""
        # print(repeat)
        # print(question_type)
        q_type = getXLSQuestionType(question_type, repeat)
        od['type'] = (q_type + ' ' + list_name) if (q_type ==
                                                    "select_multiple" or q_type == "select_one") else q_type
        od['name'] = question_name

        if type(question_label) is dict:
            for key in question_label.keys():
                od['label:'+key.title()] = question_label[key]
        else:
            od['label'] = question_label

        # required_message
        od['required'] = required

        if type(required_message) is dict:
            for key in required_message.keys():
                od['required_message:'+key] = required_message[key]
        else:
            od['required_message'] = required_message
        od['appearance'] = appearance
        od['hint'] = hint

        if (q_type == "select_multiple" or q_type == "select_one"):
            options = node["options"]
            for op in options:
                cd['list_name'] = list_name
                cd['name'] = op['value']
                cd['label:English'] = op['option']
                cd['label:Bangla'] = op['option']
                cl.append(copy.deepcopy(cd))
                cd = OrderedDict()

        ql.append(copy.deepcopy(od))

        if question_type == "Group Question":
            parse_json(node['questions'], ql, cl)
            #od['type'] = "end group"
            od['type'] = "end_repeat" if repeat == "true" else "end group"
            ql.append(copy.deepcopy(od))

    return ql, cl



def publish_ui_form(json_str,form_title,form_id):
    ql = []
    cl = []

    od = OrderedDict()

    od['type'] = 'start'
    od['name'] = 'start'

    ql.append(copy.deepcopy(od))

    od['type'] = 'end'
    od['name'] = 'end'
    ql.append(copy.deepcopy(od))

    od['type'] = 'username'
    od['name'] = 'username'
    ql.append(copy.deepcopy(od))

    qs, cs = parse_json(json_str, ql, cl)
    df = pd.DataFrame(qs)

    if cs:
        df_choice = pd.DataFrame(cs).drop_duplicates()
    else:
        df_choice = pd.DataFrame()

    default_language = "English"

    df_setting = pd.DataFrame([[form_title, form_id, default_language]], columns=[
        'form_title', 'form_id', 'default_language'])

    if not os.path.exists("onadata/media/ui_published_forms"):
        os.mkdir("onadata/media/ui_published_forms")

    xls_path = "onadata/media/ui_published_forms/"+str(form_id)+".xlsx"
    with ExcelWriter(xls_path) as writer:
        df.to_excel(writer, sheet_name="survey", engine="xlsxwriter", index=False)
        if not df_choice.empty:
            df_choice.to_excel(writer, sheet_name="choices",
                           engine="xlsxwriter", index=False)
        df_setting.to_excel(writer, sheet_name="settings",
                            engine="xlsxwriter", index=False)

    return xls_path