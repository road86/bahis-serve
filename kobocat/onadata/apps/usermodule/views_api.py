#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import decimal
import numpy as np

from django.db import (IntegrityError,transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.usermodule.forms import UserForm, UserProfileForm, ChangePasswordForm, UserEditForm,OrganizationForm,ResetPasswordForm
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin,Organizations

from onadata.apps.usermodule.models import OrganizationRole,MenuRoleMap,UserRoleMap

from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import pandas
from django.shortcuts import render
from collections import OrderedDict

from django.core.files.storage import FileSystemStorage
import string
import random
import zipfile
import time
from django.conf import settings
import os



from django.core.mail import send_mail, BadHeaderError
import smtplib
from onadata.apps.usermodule import views



def __db_commit_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    #connection.commit()
    cursor.close()


@csrf_exempt
def get_hh_list(request):
    username = request.GET.get('username')
    user = User.objects.filter(username=username).first()
    role =""
    if user is not None:
        profile = user.usermoduleprofile
        role = profile.role.role


    dataset = []
    if role == 'FD':
        q = "select string_to_array(string_agg(sector_id::text,','),',')::int[]  from user_sector where user_id = " + str(
            user.id)
        dataset = views.__db_fetch_single_value(q)
    if role == 'TLI':
        q = "select string_to_array(string_agg(id::text,','),',')::int[] from sector where tlpin_id = ANY(select tlpin_id from user_tlpin where user_id = " + str(
            user.id) + ") "
        dataset = views.__db_fetch_single_value(q)

    main_q = "select id,household_id hh_id,(select sector_code from sector where id = sector_id limit 1) sector FROM household WHERE (status = 0 or status=1) and sector_id = ANY(Array"+str(dataset)+")"
    #print main_q
    main_df = pandas.read_sql(main_q, connection)

    date_q = "with t1 as( SELECT household_id id,max(schedule_date::date) latestest_sch_date FROM schedule WHERE household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) group by household_id)select id,to_char(latestest_sch_date::date, 'day') weekday, latestest_sch_date::text from t1"
    print date_q

    date_df  = pandas.read_sql(date_q, connection)

    main_df = main_df.merge(date_df, on=['id'], how='left', )
    #print main_df
    sche_q = "SELECT id as schedule_id,(SELECT id FROM household WHERE id =schedule.household_id limit 1) id, (SELECT id_string FROM logger_xform WHERE id=scheduled_form_id limit 1) schedule_form, (schedule_date::date)::text  as s_date,(select priority_value from form_priority where form_id=scheduled_form_id )::Integer priority FROM schedule WHERE household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) "
    #print sche_q
    sche_df = pandas.read_sql(sche_q, connection)
    #print sche_df
    main_df = main_df.merge(sche_df, on=['id'], how='left', )
    #print main_df


    j = main_df.groupby(['id','hh_id','latestest_sch_date','weekday','sector']).apply(lambda x: x[['schedule_id','schedule_form', 's_date','priority']].to_dict('r')).reset_index().rename(
        columns={0: 'sche_json'}).to_json(orient='records')

    return HttpResponse(j)



@csrf_exempt
def get_hh(request):
    username = request.GET.get('username')
    user = User.objects.filter(username=username).first()
    role =""
    if user is not None:
        profile = user.usermoduleprofile
        role = profile.role.role
    print role

    dataset = []
    if role =='FD':
        q = "select string_to_array(string_agg(sector_id::text,','),',')::int[]  from user_sector where user_id = "+str(user.id)
        dataset = views.__db_fetch_single_value(q)
    if role == 'TLI':
        q = "select string_to_array(string_agg(id::text,','),',')::int[] from sector where tlpin_id = ANY(select tlpin_id from user_tlpin where user_id = "+str(user.id)+") "
        dataset = views.__db_fetch_single_value(q)

    q = "select household_id as hhid,(select sector_code from sector where id = sector_id limit 1) sector from household where  (status=0 or status=1) and sector_id = ANY (ARRAY"+str(dataset)+")"

    data = json.dumps(views.__db_fetch_values_dict(q), default=views.decimal_date_default)
    return HttpResponse(data)


@csrf_exempt
def get_hh_member(request):
    username = request.GET.get('username')
    user = User.objects.filter(username=username).first()
    role =""
    if user is not None:
        profile = user.usermoduleprofile
        role = profile.role.role
    print role

    dataset = []
    if role =='FD':
        q = "select string_to_array(string_agg(sector_id::text,','),',')::int[]  from user_sector where user_id = "+str(user.id)
        dataset = views.__db_fetch_single_value(q)
    if role == 'TLI':
        q = "select string_to_array(string_agg(id::text,','),',')::int[] from sector where tlpin_id = ANY(select tlpin_id from user_tlpin where user_id = "+str(user.id)+") "
        dataset = views.__db_fetch_single_value(q)

    #q = "select household_id as hhid,(select sector_code from sector where id = sector_id limit 1) sector from household where sector_id = ANY (ARRAY"+str(dataset)+")"

    q="with t1 as (SELECT id,household_id, sector_id FROM public.household where sector_id=ANY (ARRAY" + str(dataset) + ") and (status=0 or status=1) ),t2 as(select id beneficiary_id,uid,name,coalesce((date_part('year',age(dob)))::text,'') age,(case sex when '1' then 'F' else 'M' end ) sex, type,coalesce(husband_name,'') husband_name,household_id from beneficiary where (status = 'ACTIVE' or status = 'ANC' or status = 'PNC_CHILD' or status = 'PNC_MC_SB' or status = 'ELCO' ) and  household_id=any(select id from t1))select t1.id,t1.household_id hhid,(select sector_code from sector where id =t1. sector_id) sector_id,t2.beneficiary_id::text,t2.uid,t2.name,t2.age,t2.sex,t2.type,t2.husband_name from t1 left outer join t2 on t1.id=t2.household_id"
    print q
    main_df = pandas.read_sql(q, connection)



    d = main_df.groupby(['id','hhid','sector_id']).apply(lambda x: x[['beneficiary_id','uid','name','age','sex','type','husband_name']].to_dict('r')).reset_index().rename(
        columns={0: 'member_json'})
    #print d

    for index,row in d.iterrows():
        v=row['member_json'][0]
        #print v['beneficiary_id']
        if str(v['beneficiary_id'])=="nan" or str(v['beneficiary_id'])=="None":
            #print "empty"
            #np.nan
            #d.xs(index)['member_json']=np.nan
            d.at[index, 'member_json'] = np.nan
     
    j=d.to_json(orient='records')
    
    return HttpResponse(j)


@csrf_exempt
def get_schedule_list(request):
    username = request.GET.get('username')
    user = User.objects.filter(username=username).first()
    if user == None:
        return HttpResponse("No Valid User")

    role = ""
    if user is not None:
        profile = user.usermoduleprofile
        role = profile.role.role
    print role

    dataset = []
    if role == 'FD':
        q = "select string_to_array(string_agg(sector_id::text,','),',')::int[]  from user_sector where user_id = " + str(
            user.id)
        dataset = views.__db_fetch_single_value(q)
    if role == 'TLI':
        q = "select string_to_array(string_agg(id::text,','),',')::int[] from sector where tlpin_id = ANY(select tlpin_id from user_tlpin where user_id = " + str(
            user.id) + ") "
        dataset = views.__db_fetch_single_value(q)

    #q="with t1 as(SELECT id schedule_id,household_id id,(schedule_date::date)  as s_date,(SELECT id_string FROM logger_xform WHERE id=scheduled_form_id) schedule_form,(select priority_value from form_priority where form_id=scheduled_form_id ) priority FROM schedule where status='ACTIVE' and schedule_user_id="+ str(user.id) +"),t2 as(select id,household_id,sector_id from household where id=any(select id from t1)),t3 as(select t1.*,t2.household_id hh_id,sector_id from t1,t2 where t1.id=t2.id),t4 as(select t3.schedule_id,t3.id,t3.s_date,t3.hh_id,sector.sector_code sector,t3.schedule_form,t3.priority from t3,sector where t3.sector_id=sector.id ),t5 as(select id,min(s_date) latestest_sch_date from t4 group by id) select t4.*,t5.latestest_sch_date::text, to_char(latestest_sch_date::date, 'day') weekday from t4 , t5 where t4.id=t5.id;"

    query = "SELECT id schedule_id,beneficiary_id::text ,(select sector_code from sector where id = (select sector_id from household where id = schedule.household_id) limit 1) sector,household_id id,(SELECT household_id FROM household WHERE id =schedule.household_id limit 1) hh_id, (SELECT id_string FROM logger_xform WHERE id=scheduled_form_id limit 1) schedule_form, (schedule_date::date)::text  as s_date,(select priority_value from form_priority where form_id=scheduled_form_id ) priority,(select shortname from form_shortname where form_id = schedule.scheduled_form_id limit 1)  || ' - ' ||(select short_name from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) form_shortname,(select short_name from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) study_short_name,(select id from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) study_id,(select xml::text  from logger_instance where id = schedule.submitted_instance_id limit 1) xml_data FROM schedule WHERE household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and (status='ACTIVE' or status = 'send_for_correction') and schedule_user_id="+str(user.id)+""


    main_df = pandas.read_sql(query, connection)

    #main_df['xml_data'] = main_df['xml_data'].apply(lambda x: x.encode('base64', 'strict') if x is not None else x)
    #main_df["beneficiary_id"] = main_df["beneficiary_id"].fillna('0')
    #main_df = main_df.astype({"beneficiary_id": np.int64})

    date_q = "with t1 as( SELECT household_id id,max(schedule_date::date) latestest_sch_date FROM schedule WHERE household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) group by household_id)select id,to_char(latestest_sch_date::date, 'day') weekday, latestest_sch_date::text from t1"
    date_df  = pandas.read_sql(date_q, connection)

    main_df = main_df.merge(date_df, on=['id'], how='left', )


    
    # Handle anc key error
    cols = main_df.columns.tolist()
    cols_extra = ['anc_1', 'anc_2', 'anc_3', 'anc_4']
    
    # add columns in existing data frame :: Added Column values will be Null
    main_df = main_df.reindex(columns=cols+cols_extra, fill_value=None)
    

    del_col = ['beneficiary_id']

    # Get latest PSRF , ANCF-1, ANCF-2, ANCF-3, ANCF-4
    psrf_q = "with t as( select beneficiary_id,submitted_instance_id from schedule where scheduled_form_id = 59 and household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and status='DONE' and schedule_user_id="+str(user.id)+"),t1 as( select t.beneficiary_id,beneficiary.status ,beneficiary.uid,max(submitted_instance_id) OVER(PARTITION BY uid) instance_id from t,beneficiary where t.beneficiary_id=beneficiary.id ) ,t2 as(select *,(select json from logger_instance where id =t1.instance_id) psrf_json from t1 where status='ACTIVE'), t3 as (SELECT t2.instance_id,t2.beneficiary_id, d.key, d.value FROM t2 JOIN json_each_text(t2.psrf_json) d ON true ) select value, beneficiary_id,(case when key='psrf_met/psrf_pregnant/FDHR_PSR' then 'existing_FDHR_PSR' when key='psrf_met/psrf_pregnant/FDHRP' then 'existing_FDHRP' when key='psrf_met/psrf_pregnant/FDVG' then 'existing_FDVG' when key='psrf_met/FDPSRLMP' then 'existing_psrlmp' when key='psrf_met/psrf_pregnant/cost_eligible' then 'existing_cost_eligible' else '' end ) key_new from t3 where key in('psrf_met/psrf_pregnant/FDHR_PSR','psrf_met/psrf_pregnant/FDHRP','psrf_met/psrf_pregnant/FDVG','psrf_met/FDPSRLMP','psrf_met/psrf_pregnant/cost_eligible') "

    df_psrf = pandas.read_sql(psrf_q, connection)

    ancf_1_q = "with t as(SELECT beneficiary_id, submitted_instance_id FROM schedule WHERE scheduled_form_id = 84 and household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and status='DONE' and schedule_user_id="+str(user.id)+"),t1 as (SELECT t.beneficiary_id, beneficiary.status , beneficiary.uid, max(submitted_instance_id) OVER(PARTITION BY uid) instance_id FROM t,beneficiary WHERE t.beneficiary_id=beneficiary.id) ,t2 as (SELECT *, (SELECT json FROM logger_instance WHERE id =t1.instance_id) ancf1_json FROM t1 WHERE status='ACTIVE'), t3 AS (SELECT t2.instance_id, t2.beneficiary_id, d.key, d.value FROM t2 JOIN json_each_text(t2.ancf1_json) d ON true ) SELECT value,beneficiary_id, (case WHEN key='HR_ANC1' THEN 'existing_HR_ANC1' ELSE '' END ) key_new FROM t3 WHERE key in('HR_ANC1') "

    df_ancf_1 = pandas.read_sql(ancf_1_q, connection)

    ancf_2_q = "with t as(SELECT beneficiary_id, submitted_instance_id FROM schedule WHERE scheduled_form_id = 39 AND household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and status='DONE' AND schedule_user_id="+str(user.id)+"),t1 as (SELECT t.beneficiary_id, beneficiary.status , beneficiary.uid, max(submitted_instance_id) OVER(PARTITION BY uid) instance_id FROM t,beneficiary WHERE t.beneficiary_id=beneficiary.id) ,t2 as (SELECT *, (SELECT json FROM logger_instance WHERE id =t1.instance_id) ancf2_json FROM t1 WHERE status='ACTIVE'), t3 AS (SELECT t2.instance_id, t2.beneficiary_id, d.key, d.value FROM t2 JOIN json_each_text(t2.ancf2_json) d ON true ) SELECT value,beneficiary_id, (case WHEN key='HR_ANC2' THEN 'existing_HR_ANC2' ELSE '' END ) key_new FROM t3 WHERE key in('HR_ANC2') "

    df_ancf_2 = pandas.read_sql(ancf_2_q, connection)

    ancf_3_q = "with t as(SELECT beneficiary_id, submitted_instance_id FROM schedule WHERE scheduled_form_id = 40 AND household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and status='DONE' AND schedule_user_id="+str(user.id)+"),t1 as (SELECT t.beneficiary_id, beneficiary.status , beneficiary.uid, max(submitted_instance_id) OVER(PARTITION BY uid) instance_id FROM t,beneficiary WHERE t.beneficiary_id=beneficiary.id) ,t2 as (SELECT *, (SELECT json FROM logger_instance WHERE id =t1.instance_id) ancf3_json FROM t1 WHERE status='ACTIVE'), t3 AS (SELECT t2.instance_id, t2.beneficiary_id, d.key, d.value FROM t2 JOIN json_each_text(t2.ancf3_json) d ON true ) SELECT value,beneficiary_id, (case WHEN key='HR_ANC3' THEN 'existing_HR_ANC3' ELSE '' END ) key_new FROM t3 WHERE key in('HR_ANC3') "

    df_ancf_3 = pandas.read_sql(ancf_3_q, connection)

    #UNION Dataframe

    df_psrf_ancf1 = pandas.concat([df_psrf, df_ancf_1])
    df_psrf_ancf1_ancf2 = pandas.concat([df_psrf, df_ancf_1, df_ancf_2], )
    df_psrf_ancf1_ancf2_ancf3 = pandas.concat([df_psrf, df_ancf_1, df_ancf_2, df_ancf_3], )

    #  ************         ANCF-1 Schedule      ****************#
    # First get all ancf-1 schedule
    anc1_sche_q = "select id schedule_id , beneficiary_id from schedule where  household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array"+str(dataset)+")) and status='ACTIVE' and schedule_user_id="+str(user.id)+" and scheduled_form_id =84;"

    df_anc1_sche = pandas.read_sql(anc1_sche_q, connection)

    if not df_psrf.empty:
        main_df = main_df.drop(['anc_1'], axis=1)

    m = (df_psrf.groupby(['beneficiary_id'])
         .apply(lambda x: x[['value', 'key_new']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'anc_1'}))

    df_anc1_sche = df_anc1_sche.merge(m, on=['beneficiary_id'], how='left', )

    df_anc1_sche = df_anc1_sche.drop(del_col, axis=1)

    main_df = main_df.merge(df_anc1_sche, on=['schedule_id'], how='left', )


    #  ************         ANCF-2 Schedule      ****************#

    anc2_sche_q = "select id schedule_id , beneficiary_id from schedule where  household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array" + str(dataset) + ")) and status='ACTIVE' and schedule_user_id=" + str(user.id) + " and scheduled_form_id =39;"

    df_anc2_sche = pandas.read_sql(anc2_sche_q, connection)

    if not df_psrf_ancf1.empty:
        main_df = main_df.drop(['anc_2'], axis=1)

    n = (df_psrf_ancf1.groupby(['beneficiary_id'])
         .apply(lambda x: x[['value', 'key_new']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'anc_2'}))

    df_anc2_sche = df_anc2_sche.merge(n, on=['beneficiary_id'], how='left', )

    df_anc2_sche = df_anc2_sche.drop(del_col, axis=1)

    main_df = main_df.merge(df_anc2_sche, on=['schedule_id'], how='left', )


    #  ************         ANCF-3 Schedule      ****************#

    anc3_sche_q = "select id schedule_id , beneficiary_id from schedule where  household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array" + str(dataset) + ")) and status='ACTIVE' and schedule_user_id=" + str(user.id) + " and scheduled_form_id =40;"

    df_anc3_sche = pandas.read_sql(anc3_sche_q, connection)

    if not df_psrf_ancf1_ancf2.empty:
        main_df = main_df.drop(['anc_3'], axis=1)

    p = (df_psrf_ancf1_ancf2.groupby(['beneficiary_id'])
         .apply(lambda x: x[['value', 'key_new']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'anc_3'}))

    df_anc3_sche = df_anc3_sche.merge(p, on=['beneficiary_id'], how='left', )

    df_anc3_sche = df_anc3_sche.drop(del_col, axis=1)

    main_df = main_df.merge(df_anc3_sche, on=['schedule_id'], how='left', )

    #  ************         ANCF-4 Schedule      ****************#

    anc4_sche_q = "select id schedule_id , beneficiary_id from schedule where  household_id = ANY (SELECT id FROM household WHERE sector_id = ANY(Array" + str(dataset) + ")) and status='ACTIVE' and schedule_user_id=" + str(user.id) + " and scheduled_form_id =41;"

    df_anc4_sche = pandas.read_sql(anc4_sche_q, connection)

    if not df_psrf_ancf1_ancf2_ancf3.empty:
        main_df = main_df.drop(['anc_4'], axis=1)

    q = (df_psrf_ancf1_ancf2_ancf3.groupby(['beneficiary_id'])
         .apply(lambda x: x[['value', 'key_new']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'anc_4'}))

    df_anc4_sche = df_anc4_sche.merge(q, on=['beneficiary_id'], how='left', )

    df_anc4_sche = df_anc4_sche.drop(del_col, axis=1)

    main_df = main_df.merge(df_anc4_sche, on=['schedule_id'], how='left', )

    #for index, row in main_df.iterrows():
    #    if row['xml_data']:
    #        print("***********************last**************************************")
    #        print (row['xml_data'])

    j = main_df.groupby(['id','sector','hh_id','latestest_sch_date','weekday'])\
        .apply(lambda x: x[['schedule_id','beneficiary_id','schedule_form','xml_data','form_shortname','study_short_name','study_id','s_date','priority','anc_1','anc_2','anc_3','anc_4']].to_dict('r')).reset_index().rename(
        columns={0: 'sche_json'}).to_json(orient='records')


    return HttpResponse(j)





@csrf_exempt
def get_beneficiary_hh(request):

    hhid = request.GET.get('hhid')
    secid = request.GET.get('secid')

    #q = "with t1 AS(SELECT id, uid, age, name, husband_name FROM beneficiary WHERE household_id = "+hhid+"),t2 AS (SELECT beneficiary_id, (SELECT id_string FROM logger_xform WHERE id=scheduled_form_id limit 1) schedule_form, (schedule_date::date)::text AS s_date FROM schedule WHERE household_id = (SELECT id FROM household WHERE household_id = '"+hhid+"' limit 1) ) SELECT t1.uid, t1.age, t1.name, t1.husband_name, coalesce(t2.schedule_form,'') schedule_form, coalesce(t2.s_date,'') s_date FROM t1 LEFT JOIN t2 ON t1.id = t2.beneficiary_id"

    q="SELECT id, uid, age, name, husband_name,type FROM beneficiary WHERE household_id=any(SELECT id FROM public.household where household_id='"+ hhid +"' and sector_id=any(select id from sector where sector_code='"+ secid +"'));"

    main_df = pandas.read_sql(q, connection)

    #j = main_df.groupby(['uid', 'age', 'name','husband_name']).apply(
    #    lambda x: x[['schedule_form', 's_date']].to_dict('r')).reset_index().rename(
    #    columns={0: 'sche_json'}).to_json(orient='records')

    j=main_df.to_json(orient='records')

    return HttpResponse(j)


@csrf_exempt
def get_hh_schedule(request):

    hhid = request.GET.get('hhid')

    q="SELECT id, uid, age, name, husband_name,type FROM beneficiary WHERE household_id=any(SELECT id FROM public.household where household_id='"+ hhid +"' and sector_id=any(select id from sector where sector_code='"+ secid +"'));"

    main_df = pandas.read_sql(q, connection)

    j=main_df.to_json(orient='records')

    return HttpResponse(j)


@csrf_exempt
def get_beneficiary_info(request):

    uid = request.GET.get('uid')

    q = "SELECT coalesce(name,'') as name,coalesce((date_part('year',age(dob)))::text,'') age, status, type,  coalesce(husband_name,'') husband_name, coalesce(mobile,'') mobile ,coalesce((select household_id from household where id = beneficiary.household_id),'') household_id,coalesce(nid,'') nid ,coalesce( bid,'') bid FROM public.beneficiary where uid like '"+uid+"'; "

    main_df = pandas.read_sql(q, connection)

    j = main_df.to_json(orient='records')

    return HttpResponse(j)





def get_user_schedule(request):
    userid = request.GET.get('username')

    q = " select id schedule_id ,date(schedule_date)::text schedule_date,COALESCE ((select sector_code from sector where id = schedule.sector_id),'') sector,COALESCE ((select household_id from household where id = schedule.household_id),'') household_id, COALESCE ((select uid from beneficiary where id = schedule.beneficiary_id),'') uid, (select id_string from logger_xform where id = schedule.scheduled_form_id) scheduled_form,(select shortname from form_shortname where form_id = schedule.scheduled_form_id limit 1) || ' - ' ||(select short_name from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) form_shortname ,household_id as hh_primary_id, beneficiary_id::text ben_primary_id ,(select short_name from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) study_short_name,(select id from study where id=(select study_id from study_form where form_id=schedule.scheduled_form_id limit 1) ) study_id,(select xml::text  from logger_instance where id = schedule.submitted_instance_id limit 1) xml_data from schedule where schedule_user_id=(select id from auth_user where username = '" + str(
        userid) + "') and (status='ACTIVE' or status = 'send_for_correction');"


    main_df = pandas.read_sql(q, connection)


    #main_df['xml_data'] = main_df['xml_data'].apply(lambda x: x.encode('base64', 'strict') if x is not None else x)

    date_q = "with t1 as( SELECT household_id hh_primary_id,max(schedule_date::date) latestest_sch_date FROM schedule  where schedule_user_id=(select id from auth_user where username = '" + str(
        userid) + "') and (status='ACTIVE' or status = 'send_for_correction') group by household_id)select hh_primary_id,to_char(latestest_sch_date::date, 'day') weekday, latestest_sch_date::text from t1"
    date_df = pandas.read_sql(date_q, connection)

    main_df = main_df.merge(date_df, on=['hh_primary_id'], how='left', )

    # Get FDGISV Data of corresponding GISV
    sche_gisv_q = "with t1 as( select id schedule_id, instance_id from schedule where schedule_user_id=(select id from auth_user where username = '" + str(
        userid) + "') and (status='ACTIVE' or status = 'send_for_correction') and scheduled_form_id = 16), t2 as( select id, json from logger_instance where id = ANY(select instance_id from t1) ), t3 as( SELECT t2.id, d.key, d.value FROM t2 JOIN json_each_text(t2.json) d ON true ), t4 as ( SELECT t3.id, t3.value,t3.key, (SELECT question FROM vw_label_fdgis WHERE field_name = t3.key) question, (SELECT field_type FROM vw_label_fdgis WHERE field_name = t3.key ) field_type FROM t3 ), t5 as ( select * from t4 where question is not null) select t5.*, t1.schedule_id , (case when t5.field_type = 'select one' then (select value_label::json->>'Bengali' from xform_extracted where xform_id = 57 and field_name = t5.key and value_text = t5.value ) else t5.value end) ans from t5 join t1 on t1.instance_id = t5.id;"

    sche_gisv_df = pandas.read_sql(sche_gisv_q, connection)

    m = (sche_gisv_df.groupby(['schedule_id'])
         .apply(lambda x: x[['question', 'ans', 'value', 'key']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'fdgis'}))
    print ("length of fdgis::"+str(len(m)))
    
    main_df = main_df.merge(m, on=['schedule_id'], how='left', )
    if len(m) == 0:
        main_df['fdgis'] = np.nan



    # Get NWRM Data of corresponding NWVM
    #q_1 = "with t1 as( select id schedule_id, instance_id from schedule where schedule_user_id=(select id from auth_user where username = '" + str(userid) + "') and status='ACTIVE' and scheduled_form_id = 58), t2 as( select id, json from logger_instance where id = ANY(select instance_id from t1) ), t3 as( SELECT t2.id, d.key, d.value FROM t2 JOIN json_each_text(t2.json) d ON true ), t4 as ( SELECT t3.id, t3.value,t3.key, (SELECT question FROM vw_label_nwrm WHERE field_name = t3.key) question,(SELECT serial_no FROM vw_label_nwrm WHERE field_name = t3.key) serial_no, (SELECT field_type FROM vw_label_nwrm WHERE field_name = t3.key ) field_type FROM t3 ), t5 as ( select * from t4 ) select t5.*, t1.schedule_id , (case when t5.field_type = 'select one' then (select value_label::json->>'Bengali' from xform_extracted where xform_id = 57 and field_name = t5.key and value_text = t5.value ) else t5.value end) ans from t5 join t1 on t1.instance_id = t5.id;"
    q_1 = "with t1 as(SELECT id schedule_id, instance_id FROM schedule WHERE schedule_user_id= (SELECT id FROM auth_user WHERE username = '"+str(userid)+"') AND status='ACTIVE' AND scheduled_form_id = 58), t2 as (SELECT id, json FROM logger_instance WHERE id = ANY (SELECT instance_id FROM t1)), t3 as (SELECT t2.id, d.key, d.value FROM t2 JOIN json_each_text(t2.json) d ON true ), t4 AS (SELECT t3.id, t3.value, t3.key, (SELECT question FROM vw_label_nwrm WHERE field_name = t3.key) question, (SELECT serial_no FROM vw_label_nwrm WHERE field_name = t3.key) serial_no, (SELECT field_type FROM vw_label_nwrm WHERE field_name = t3.key ) field_type FROM t3 ), t5 AS (SELECT *,(case when field_type = 'photo' then (select 'media/' || media_file from logger_attachment where instance_id = t4.id limit 1) else t4.value end) data_val FROM t4 ) SELECT t5.id,t5.key,t5.question,t5.serial_no,t5.data_val as value,t5.field_type, t1.schedule_id , (case WHEN t5.field_type = 'select one' THEN (SELECT value_label::json->>'Bengali' FROM xform_extracted WHERE xform_id = 57 AND field_name = t5.key AND value_text = t5.value ) ELSE t5.data_val end) ans FROM t5 JOIN t1 ON t1.instance_id = t5.id; "
    
    df = pandas.read_sql(q_1, connection)

    k = (df.groupby(['schedule_id'])
         .apply(lambda x: x[['question', 'ans', 'value', 'key','serial_no','field_type']].to_dict('r'))
         .reset_index()
         .rename(columns={0: 'nwrm'}))
    # print (len(k))
    main_df = main_df.merge(k, on=['schedule_id'], how='left', )

    if len(k) == 0:
        j = (main_df.groupby(['scheduled_form','form_shortname','study_short_name','study_id'])
             .apply(lambda x: x[
            ['schedule_id', 'latestest_sch_date', 'weekday', 'xml_data','schedule_date', 'sector', 'household_id', 'uid',
             'hh_primary_id','fdgis','ben_primary_id']].to_dict('r'))
             .reset_index()
             .rename(columns={0: 'sche_json'})
             .to_json(orient='records'))
    else:
        j = (main_df.groupby(['scheduled_form','form_shortname','study_short_name','study_id'])
             .apply(lambda x: x[
            ['schedule_id', 'latestest_sch_date', 'weekday', 'xml_data','schedule_date', 'sector', 'household_id', 'uid',
             'hh_primary_id','fdgis','nwrm','ben_primary_id']].to_dict('r'))
             .reset_index()
             .rename(columns={0: 'sche_json'})
             .to_json(orient='records'))


    return HttpResponse(j)


@csrf_exempt
def nwvm_previous_uid(request):

    uid = request.GET.get('uid')

    q  = "select *,(select household_id from household where id =beneficiary.household_id ) hh_id,(select sector_code from sector where id =(select sector_id from household where id =beneficiary.household_id )) sector from beneficiary where uid = '"+str(uid)+"' and status = 'ACTIVE' limit 1 "

    beneficiary = views.__db_fetch_values_dict(q)

    b_id = ''

    b_name = ''

    b_husbandname = ''

    hh_id = ''

    pmv_status = 0

    if beneficiary:

        for temp in beneficiary:

            b_id = temp['id']

            b_name = temp['name']

            b_husbandname = temp['husband_name']

            hh_id = temp['hh_id']

            sector = temp['sector']

        pmv_sche_done = views.__db_fetch_values_dict("select * from schedule where status = 'DONE' and scheduled_form_id = 80 and beneficiary_id = "+str(b_id))

        pmv_sche_active = views.__db_fetch_values_dict("select * from schedule where status = 'ACTIVE' and scheduled_form_id = 80 and beneficiary_id = " + str(b_id))

        #sector-777 will be not be restricted during NWVM even if there is no PMV reported
        if pmv_sche_done or sector == '777':

            pmv_status = 0

        #active pmv found for beneficiary uid
        elif pmv_sche_active:

            pmv_status = 1
        #No pmv scheduled found for beneficiary uid:
        else:

            pmv_status = 2

    #No similar woman found for beneficiary uid
    else:
        pmv_status = 0


    data = {
        'beneficiary_name' : b_name,'husband_name' : b_husbandname,'hhid' : hh_id,'pmv_status' : pmv_status,
    }

    return HttpResponse(json.dumps(data))


@csrf_exempt
def get_uid(request):

    type = request.GET.get('type')

    q = "select * from get_uid('"+str(type)+"')"

    data = views.__db_fetch_single_value(q)

    return HttpResponse(json.dumps(data))


@csrf_exempt
def get_user_data(request):

    username = request.GET.get('username')

    df = []

    if username:

        q = "select id data_id,(select title from logger_xform where id_string =((logger_instance.json->>'_xform_id_string')::text)) form_name, coalesce(json->>'householdid','') hh_id, coalesce(json->>'uid','') uid,coalesce(json->>'_submission_time','') submission_time from logger_instance where user_id = (select id from auth_user where username ='"+str(username)+"')"

        df = (pandas.read_sql(q, connection)).to_json(orient='records')

    return HttpResponse(df)


@csrf_exempt
def get_pregnant_woman_list(request):

    username = request.GET.get('username')

    user = User.objects.filter(username=username).first()

    if user == None:

        return HttpResponse("No Valid User")


    sector_dataset = []

    sector_q = "select string_to_array(string_agg(sector_id::text,','),',')::int[]  from user_sector where user_id = " + str(user.id)

    if views.__db_fetch_single_value(sector_q) == None:

        sector_dataset = []
    else:
        sector_dataset = views.__db_fetch_single_value(sector_q)

    q = "with hh_list as( SELECT id FROM public.household where sector_id=ANY(ARRAY"+str(sector_dataset)+"::int[]) and (status=0 or status=1)) select id as beneficiary_pri_id,name,husband_name,uid,(select household_id from household where id = beneficiary.household_id limit 1) hhid,nid,bid,date(lmp)::text lmp,coalesce((date_part('year',age(dob)))::text,'') age from beneficiary where household_id = any(select id from hh_list) and id = any(select beneficiary_id from schedule where status = 'ACTIVE' and scheduled_form_id = 55) "

    df = (pandas.read_sql(q, connection)).to_json(orient='records')

    return HttpResponse(df)


@csrf_exempt
def check_hh_existed(request):

    hh_id =  request.GET.get('hhid')

    sector = request.GET.get('sector')

    flag = ''

    if hh_id and sector:

        q = "select * from household where household_id = '"+hh_id+"' and sector_id = (select id from sector where sector_code = '"+sector+"')"

        data = views.__db_fetch_values_dict(q)

        if data:

            flag = 'yes'
        else:

            flag = 'no'

    return HttpResponse(json.dumps({'is_existed' : flag}))


@csrf_exempt
def generate_sche_bnt_sms(request):

    ben_primary_id = request.GET.get('id')

    hh_id = views.__db_fetch_single_value("select household_id from beneficiary where id = "+str(ben_primary_id)+"")

    username = request.GET.get('username')

    sche_user_id = views.__db_fetch_single_value("select id from auth_user where username = '"+str(username)+"'")

    # PVF=55,anc2=39,anc3=40,anc4=41,anc1=84

    others_sche_q = "update schedule set status='CANCELLED' where status='ACTIVE' and scheduled_form_id in(84,39,40,41) and beneficiary_id = "+str(ben_primary_id)+" and household_id = "+str(hh_id)+"  "

    __db_commit_query(others_sche_q)

    pvf_sche_q = "update schedule set status='CANCELLED' where status='ACTIVE' and date(schedule_date) >current_date  and scheduled_form_id =55 and beneficiary_id = " + str(ben_primary_id) + " and household_id = " + str(hh_id) + "  "

    __db_commit_query(pvf_sche_q)

    new_sche_q = "INSERT INTO public.schedule( created_date, status, schedule_date, scheduled_form_id, household_id,beneficiary_id, schedule_user_id,  created_by)VALUES (NOW(), 'ACTIVE', NOW(), 55, " + str(hh_id) + ", " + str(ben_primary_id) + ", " + str(sche_user_id) + ","+str(request.user.id)+");"

    __db_commit_query(new_sche_q)

    return HttpResponse("ok")


@csrf_exempt
def login_verify(request):

    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        print "check1"
        print request.body
        json_string = request.body
        # print "check2" +json_string
        data = json.loads(json_string)
        print "check3 "
        username = data['user_name']
        password = data['password']
        """firebase token saving"""
        # device_id = data['device_id']
        # firebase_token = data['firebase_token']

        # Use Django's machinery to attempt to see if the username/password
        # combination is valid - a User object is returned if it is.
        "To check if user exist in this username"
        user_exist = get_object_or_404(User, username=username)
        user = authenticate(username=username, password=password)

        # If we have a User object, the details are correct.
        # If None (Python's way of representing the absence of a value), no user
        # with matching credentials was found.

        if user:
            # number of login attempts allowed
            max_allowed_attempts = 5
            # count of invalid logins in db
            counter_login_attempts = UserFailedLogin.objects.filter(user_id=user.id).count()
            # check for number of allowed logins if it crosses limit do not login.
            if counter_login_attempts > max_allowed_attempts:
                # return HttpResponse("Your account is locked for multiple invalid logins, contact admin to unlock")
                messages.error(request,
                               'Your account is locked for multiple invalid logins, contact admin to unlock!')


                return HttpResponse('Login failed', status=409)

            # Is the account active? It could have been disabled.
            if user.is_active:

                if hasattr(user, 'usermoduleprofile'):
                    # user profile
                    user_profile = user.usermoduleprofile
                    # if date.today() > current_user.expired.date():
                    #     return HttpResponseRedirect('/usermodule/change-password')
                    # if user and password is valid then
                    # print user_profile.id
                    user_role = UserRoleMap.objects.filter(user_id=user_profile.id).first()



                    user_information = {

                    }
                    print user.id
                    print user_profile.id
                    user_information['user_name'] = username
                    user_information['name'] = user.first_name + " " + user.last_name
                    user_information['email'] = user.email
                    user_information['is_superuser'] = str(user.is_superuser)
                    user_information['is_staff'] = str(user.is_staff)
                    user_information['is_admin'] = str(user_profile.admin)
                    user_information['employee_id'] = ""
                    user_information['position'] = ""
                    user_information['role'] = "Admin"
                    user_information['organizations'] = ""
                    user_information['contact_number'] =""








                    print user_information

                login(request, user)
                UserFailedLogin.objects.filter(user_id=user.id).delete()
                # return HttpResponseRedirect(request.POST['redirect_url'])
                return HttpResponse(json.dumps(user_information))



            else:
                # An inactive account was used - no logging in!
                # return HttpResponse("Your User account is disabled.")
                user_information['login_status'] = 'Your account is Inactive!'
                return HttpResponse('Login failed', status=409)

    return HttpResponse('Login failed', status=409)



@csrf_exempt
def mobile_login(request):
    '''
    receives username and password and returns 200 if valid
    '''
    json_string = request.body
    data = json.loads(json_string)
    error_mes = {}

    if data:

        m_username = data['username']
        m_password = data['password']
        user = authenticate(username=m_username, password=m_password)
        if user:
            mobile_response = {}
            user = User.objects.get(username=m_username)
            user_profile = UserModuleProfile.objects.get(user_id=user.id)
            if not user.is_active:
                error_mes['code'] = 403
                error_mes['message'] = 'Your User account is disabled.'
                return HttpResponse(json.dumps(error_mes), status=403)
            role = ""
            role_q = "select (select role from usermodule_organizationrole where id = usermodule_userrolemap.role_id limit 1) role_name from usermodule_userrolemap where user_id = "+str(user_profile.id)+" limit 1"
            cursor = connection.cursor()
            cursor.execute(role_q)
            fetchVal = cursor.fetchone()
            if fetchVal:
                role = fetchVal[0]
            cursor.close()
            mobile_response['username'] = m_username
            mobile_response['name'] = user.first_name + " " + user.last_name
            mobile_response['email'] = user.email
            mobile_response['password'] = m_password

            mobile_response['role'] = role
            #update_token(data)
            return HttpResponse(json.dumps(mobile_response), content_type="application/json")
        else:
            # raise Http404("No such user exists with that pin and password combination")
            error_mes['code'] = 404
            error_mes['message'] = 'No such user exists with that username and password combination'
            return HttpResponse(json.dumps(error_mes), status=404)
    else:
        error_mes['code'] = 401
        error_mes['message'] = 'Invalid Login'
        return HttpResponse(json.dumps(error_mes), status=401)

