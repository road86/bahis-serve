# coding: utf-8

from __future__ import (unicode_literals, print_function, absolute_import,
                        division)

from collections import OrderedDict
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json
import decimal
from onadata.apps.main.database_utility import __db_fetch_single_value, \
    __db_commit_query, __db_fetch_values, __db_fetch_values_dict, decimal_date_default
from django.views.decorators.csrf import csrf_exempt
import datetime
from datetime import timedelta
import pandas


@login_required
def index(request):
    """
        Test Function for module

        Args:
            request (str): Default Django request Object

        Returns:
            Render Html
    """
    return render(request, 'reportsmodule/index.html')


@csrf_exempt
def getDistrict_jq(request):
    selectedDivision_id = request.POST.get('division')
    districtQuery = "select value,name as district_name from core.geo_cluster where loc_type = 2 and parent::text  = '" + str(
        selectedDivision_id) + "'"

    district_List = __db_fetch_values(districtQuery)
    jsonDisList = json.dumps({'district_List': district_List}, default=decimal_date_default)

    return HttpResponse(jsonDisList)


@csrf_exempt
def getUpazilas_jq(request):
    selectedDistrict = request.POST.get('district')
    upazilaQuery = " select value,name as upazila_name from core.geo_cluster where loc_type = 3 and parent::text  = '" + str(
        selectedDistrict) + "'"
    upazila_List = __db_fetch_values(upazilaQuery)
    jsonUpaList = json.dumps({'upazila_List': upazila_List}, default=decimal_date_default)
    return HttpResponse(jsonUpaList)


@csrf_exempt
def getUnions_jq(request):
    selectedUpazila = request.POST.get('upazila')
    unionQuery = "select value,name as union_name from core.geo_cluster where loc_type = 4 and parent::text  = '" + str(
        selectedUpazila) + "'"
    union_List = __db_fetch_values(unionQuery)
    jsonUnionList = json.dumps({'union_List': union_List}, default=decimal_date_default)
    return HttpResponse(jsonUnionList)


@csrf_exempt
def get_species_list_by_ltype(request):
    livestock_id = request.POST.get('livestock_id')
    # qry = "select code,species_name_en from fao_species where livestock_type::text like '" + str(livestock_id) + "'"
    qry = """
    with t as (
select
	*
	, case when speciesid in ('1', '3', '5', '8') then 'Ruminant'
	when speciesid in ('21', '22', '23', '27') then 'Poultry'
	else 'Others'
end as atype
from
core.bahis_species_table bst)
select
	speciesid as code,
	speciesname as species_name_en
from
	t
where
	atype like '%s'
    """ % (livestock_id)
    species_data = __db_fetch_values_dict(qry)
    return HttpResponse(json.dumps(species_data))


def make_occurace_data(n, v, o):
    o_data = [];
    for i in range(0, len(n)):
        data = {
            "region": v[i],
            "name": n[i],
            "value": o[i]

        }
        o_data.append(json.loads(json.dumps(data)))
    return o_data


@login_required
def disease_stat_chart(request):
    user_geo_data = __db_fetch_values_dict(
        """
        select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)
        """)
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
    else:
        division_id = '%'
        district_id = '%'
        upazila_id = '%'

    species_id = '%'
    disease_id = '%'
    livestock_id = '%'
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    dwm_filter_id = 'Daily'

    title_text = 'Disease Situation'

    if request.method == 'POST':
        division_id = request.POST.get('division_id', division_id)
        district_id = request.POST.get('district_id', district_id)
        upazila_id = request.POST.get('upazila_id', upazila_id)
        species_id = request.POST.get('species_id')
        disease_id = request.POST.get('disease_id')
        livestock_id = request.POST.get('livestock_id')
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        dwm_filter_id = request.POST.get('dwm_filter_id')

    if livestock_id == '1':
        livestock_type_str = 'Mammal'
    elif livestock_id == '2':
        livestock_type_str = 'Bird'
    else:
        livestock_type_str = '%'

    if user_geo_data:
        if user_geo_data[0]['organization_type'] == 1:
            forWhom = "central"
        elif user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                # print 'division--'
                forWhom = "division"
            elif loc_type == 2:
                # print 'district--'
                forWhom = "district"
            elif loc_type == 3:
                # print 'upazila--'
                forWhom = 'upazila'
    else:
        forWhom = "central"
        loc_type = None
        geoid = None

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    query_species = "select speciesid as code,speciesname as species_name from core.bahis_species_table"
    get_species_list = __db_fetch_values(query_species)

    query_disease = "select distinct on (diagnosisname) diagnosisname as code,diagnosisname as disease from core.bahis_diagnosis_table bdt order by diagnosisname asc"
    get_disease_list = __db_fetch_values(query_disease)

    if dwm_filter_id == 'Daily':
        query = """
        with j as(with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) basic_info_date,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.basic_info_date,
	bdt.diagnosisname,
	count(*) as dc,
	sum(patient_cases.sick_number::int8) as sick_number,
	sum(patient_cases.herd_flock_number::int8) as herd_flock_number,
	sum(patient_cases.treated_number::int8) as treated_number
	from patient_cases
	left join core.bahis_diagnosis_table bdt
	on bdt.diagnosisid = patient_cases.tentative_diagnosis
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.basic_info_date,bdt.diagnosisname),
    k as(with dates as(select to_char(generate_series(timestamp '%s', timestamp '%s' , interval '1 day'), 'YYYY-MM-DD') as dates)
    select distinct date(dates.dates) as dates,dt.diagnosisname from dates
    cross join core.bahis_diagnosis_table dt)
    select k.dates as case_date,k.diagnosisname as tentative_diagnosis,coalesce(j.dc,0) as cnt,coalesce(j.sick_number,0) as sick_number,
    coalesce(j.herd_flock_number,0) as herd_flock_number,coalesce(j.treated_number,0) as treated_number
    from k
    left join j
    on j.basic_info_date = k.dates
    and j.diagnosisname = k.diagnosisname
    order by k.dates asc
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, '%', start_date, end_date, start_date,
            end_date)
    elif dwm_filter_id == 'Weekly':
        query = """
        with j as(with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) as basic_info_date,
	to_char(date(bprlt.basic_info_date),'yyyy-ww') wk_no,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.wk_no,
	bdt.diagnosisname,
	count(*) as dc,
	sum(patient_cases.sick_number::int8) as sick_number,
	sum(patient_cases.herd_flock_number::int8) as herd_flock_number,
	sum(patient_cases.treated_number::int8) as treated_number
	from patient_cases
	left join core.bahis_diagnosis_table bdt
	on bdt.diagnosisid = patient_cases.tentative_diagnosis
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.wk_no,bdt.diagnosisname),
    k as(with dates as(select to_char(generate_series(timestamp '%s', timestamp '%s' , interval '1 day'), 'YYYY-IW') as dates)
    select distinct dates.dates,dt.diagnosisname from dates
    cross join core.bahis_diagnosis_table dt)
    select (to_date(k.dates, 'yyyy-ww'))::text || ' - ' || (to_date(k.dates, 'yyyy-ww') + 6)::text as case_date,
    k.diagnosisname as tentative_diagnosis,coalesce(j.dc,0) as cnt,coalesce(j.sick_number,0) as sick_number,
    coalesce(j.herd_flock_number,0) as herd_flock_number,coalesce(j.treated_number,0) as treated_number
    from k
    left join j
    on j.wk_no = k.dates
    and j.diagnosisname = k.diagnosisname
    order by k.dates asc
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, '%', start_date, end_date, start_date,
            end_date)
    elif dwm_filter_id == 'Monthly':
        query = """
        with j as(with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) as basic_info_date,
	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.month_no,
	bdt.diagnosisname,
	count(*) as dc,
	sum(patient_cases.sick_number::int8) as sick_number,
	sum(patient_cases.herd_flock_number::int8) as herd_flock_number,
	sum(patient_cases.treated_number::int8) as treated_number
	from patient_cases
	left join core.bahis_diagnosis_table bdt
	on bdt.diagnosisid = patient_cases.tentative_diagnosis
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.month_no,bdt.diagnosisname),
    k as(with dates as(select to_char(generate_series(timestamp '%s', timestamp '%s' , interval '1 day'), 'yyyy-mm') as dates)
    select distinct dates.dates,dt.diagnosisname from dates
    cross join core.bahis_diagnosis_table dt)
    select to_char(to_date(k.dates, 'yyyy-mm'), 'MON, YYYY') as case_date,
    k.diagnosisname as tentative_diagnosis,coalesce(j.dc,0) as cnt,coalesce(j.sick_number,0) as sick_number,
    coalesce(j.herd_flock_number,0) as herd_flock_number,coalesce(j.treated_number,0) as treated_number
    from k
    left join j
    on j.month_no = k.dates
    and j.diagnosisname = k.diagnosisname
    order by k.dates asc
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, '%', start_date, end_date, start_date,
            end_date)

    # print "@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
    print(query)
    # print "@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
    df = pandas.read_sql(query, connection)
    data = []
    name = []
    pinfo = []
    categories = []
    if not df.empty:
        for each in df['tentative_diagnosis'].unique().tolist():
            data.append(df['cnt'][df['tentative_diagnosis'] == each].tolist())
        for idx, row in df.iterrows():
            pinfo.append({'case_date': row['case_date'], 'tentative_diagnosis': row['tentative_diagnosis'],
                          'sick_number': row['sick_number'], 'herd_flock_number': row['herd_flock_number'],
                          'treated_number': row['treated_number']})
        categories = json.dumps(df['case_date'].unique().tolist(), default=decimal_date_default)
        name = json.dumps(df['tentative_diagnosis'].unique().tolist(), default=decimal_date_default)
        data = json.dumps(data, default=decimal_date_default)
    return render(request, 'reportsmodule/reports/disease_stat_chart_main.html',
                  {'categories': categories, 'name': name, 'data': data, 'get_division_list': get_division_list,
                   'get_species_list': get_species_list, 'get_disease_list': get_disease_list, 'start_date': start_date,
                   'end_date': end_date, 'division_id': division_id, 'district_id': district_id,
                   'upazila_id': upazila_id, 'species_id': species_id, 'disease_id': disease_id,
                   'title_text': title_text,
                   'livestock_id': livestock_id, 'dwm_filter_id': dwm_filter_id, 'loc_type': loc_type, 'geoid': geoid,
                   'pinfo': json.dumps(pinfo, default=decimal_date_default), 'forWhom': forWhom})


@login_required
def disease_stat_chart_prior(request):
    user_geo_data = __db_fetch_values_dict(
        """select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
            gd.field_type_id as loc_type from core.branch_catchment_area bca 
            left join core.geo_data gd on
            gd.geocode::int8 = bca.geoid
            left join core.usermodule_branch ub
            on ub.id = bca.branch_id 
            where bca.branch_id in (
            select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)
                """)
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        ll = user_geo_data[0]['latitude']
        lg = user_geo_data[0]['longitude']
        # print ll
        # print lg
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
                show_by_id = 'upazilas'
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
                show_by_id = 'unions'
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
                show_by_id = 'unions'
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
            show_by_id = 'districts'
    else:
        division_id = '%'
        district_id = '%'
        upazila_id = '%'
        show_by_id = 'districts'
        loc_type = None
        geoid = None
        ll = None
        lg = None

    species_id = '%'
    disease_id = '%'
    livestock_id = '%'
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    livestock_type_str = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id', division_id)
        district_id = request.POST.get('district_id', district_id)
        upazila_id = request.POST.get('upazila_id', upazila_id)
        species_id = request.POST.get('species_id')
        disease_id = request.POST.get('disease_id')
        livestock_id = request.POST.get('livestock_id')
        livestock_type_str = livestock_id
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        show_by_id = request.POST.get('show_by_id')
    default_str = 'onadata/apps/reportsmodule/static/geojson/'

    if user_geo_data:
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                geojson_path_str = default_str + 'divisionwise/' + show_by_id + '/' + division_id + '_' + show_by_id + '.geojson'
            elif loc_type == 2:
                geojson_path_str = default_str + 'districtwise/' + show_by_id + '/' + district_id + '_' + show_by_id + '.geojson'
            elif loc_type == 3:
                geojson_path_str = default_str + 'upazilawise/' + show_by_id + '/' + upazila_id + '_' + show_by_id + '.geojson'

        elif user_geo_data[0]['organization_type'] == 1:
            geojson_path_str = default_str + 'centralwise/' + show_by_id + '/' + show_by_id + '.geojson'
    else:
        geojson_path_str = default_str + 'centralwise/' + show_by_id + '/' + show_by_id + '.geojson'
    # print geojson_path_str
    # Reading GeoJson
    with open(geojson_path_str) as f:
        geojson_data = json.load(f)
    # for feature in geojson_data['features']:
    #     print feature['geometry']['type']
    #     print feature['geometry']['coordinates']
    ##
    # print show_by_id

    title_text = 'Prioritized Disease Situation'

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    query_species = "select speciesid as code,speciesname as species_name from core.bahis_species_table"
    get_species_list = __db_fetch_values(query_species)

    query_disease = "select distinct on (diagnosisname) diagnosisname as code,diagnosisname as disease from core.bahis_diagnosis_table bdt order by diagnosisname asc"
    get_disease_list = __db_fetch_values(query_disease)
    # show_by
    if show_by_id == 'districts':
        query_map = """
        select
	gc.name,
	gc.value,
	coalesce(fnl.count, 0) as no_of_occurance
from
	core.geo_cluster gc
left join (with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) as basic_info_date,
	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.basic_info_district,count(*) from patient_cases
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
	and patient_cases.tentative_diagnosis like '%s'
	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.basic_info_district) fnl
    on fnl.basic_info_district::int4 = gc.value
where
	gc.loc_type = 2
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    elif show_by_id == 'upazilas':
        query_map = """
        select
	gc.name,
	gc.value,
	coalesce(fnl.count, 0) as no_of_occurance
from
	core.geo_cluster gc
left join (with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) as basic_info_date,
	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.basic_info_upazila,count(*) from patient_cases
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
	and patient_cases.tentative_diagnosis like '%s'
	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.basic_info_upazila) fnl
    on fnl.basic_info_upazila::int4 = gc.value
where
	gc.loc_type = 3
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    elif show_by_id == 'unions':
        query_map = """
        select
	gc.name,
	gc.value,
	coalesce(fnl.count, 0) as no_of_occurance
from
	core.geo_cluster gc
left join (with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.basic_info_union,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) as basic_info_date,
	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.basic_info_union,count(*) from patient_cases
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
	and patient_cases.tentative_diagnosis like '%s'
	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.basic_info_union) fnl
    on fnl.basic_info_union::int4 = gc.value
where
	gc.loc_type = 4
        """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    ##for map
    forWhom = 'central'
    if user_geo_data:
        if user_geo_data[0]['organization_type'] == 1:
            forWhom = "central"
        elif user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                # print 'division--'
                forWhom = "division"
            elif loc_type == 2:
                # print 'district--'
                forWhom = "district"
            elif loc_type == 3:
                # print 'upazila--'
                forWhom = 'upazila'

    ##for map

    query = """
    with j as(with patient_cases as(select
	bprlt.basic_info_district,
	bprlt.basic_info_division,
	bprlt.basic_info_upazila,
	bprlt.patient_info_species,
	date(bprlt.basic_info_date) basic_info_date,
	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
	else 'Others' end as animal_type,
	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
from
	core.bahis_patient_registrydyncsv_live_table bprlt)
	select patient_cases.basic_info_date,
	bdt.diagnosisname,
	count(*) as dc,
	sum(patient_cases.sick_number::int8) as sick_number,
	sum(patient_cases.herd_flock_number::int8) as herd_flock_number,
	sum(patient_cases.treated_number::int8) as treated_number
	from patient_cases
	left join core.bahis_diagnosis_table bdt
	on bdt.diagnosisid = patient_cases.tentative_diagnosis
	where patient_cases.basic_info_district like '%s'
	and patient_cases.basic_info_division like '%s'
	and patient_cases.basic_info_upazila like '%s'
	and patient_cases.patient_info_species like '%s'
	and patient_cases.animal_type like '%s'
	and patient_cases.species_type like '%s'
	and patient_cases.tentative_diagnosis like '%s'
	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
    and patient_cases.basic_info_date between symmetric '%s' and '%s'
    group by patient_cases.basic_info_date,bdt.diagnosisname),
    k as(with dates as(select to_char(generate_series(timestamp '%s', timestamp '%s' , interval '1 day'), 'YYYY-MM-DD') as dates)
    select distinct date(dates.dates) as dates,dt.diagnosisname from dates
    cross join core.bahis_diagnosis_table dt)
    select k.dates as case_date,k.diagnosisname as tentative_diagnosis,coalesce(j.dc,0) as cnt,coalesce(j.sick_number,0) as sick_number,
    coalesce(j.herd_flock_number,0) as herd_flock_number,coalesce(j.treated_number,0) as treated_number
    from k
    left join j
    on j.basic_info_date = k.dates
    and j.diagnosisname = k.diagnosisname
    order by k.dates asc
    """ % (district_id, division_id, upazila_id, species_id, livestock_type_str, '%', disease_id, start_date, end_date,
           start_date, end_date)

    df = pandas.read_sql(query, connection)
    df_map = pandas.read_sql(query_map, connection)
    # print '-----'
    # print df_map
    map_name = json.loads(json.dumps(df_map['name'].tolist()))
    map_value = json.loads(json.dumps(df_map['value'].tolist()))
    map_no_of_occurance = json.loads(json.dumps(df_map['no_of_occurance'].tolist()))
    occurace_data = make_occurace_data(map_name, map_value, map_no_of_occurance)
    # print map_no_of_occurance
    # print map_name
    # print map_name[0]
    # print '-----'
    data = []
    name = []
    pinfo = []
    categories = []
    if not df.empty:
        for each in df['tentative_diagnosis'].unique().tolist():
            # print each
            # print df['cnt'][df['tentative_diagnosis'] == each].tolist()
            data.append(df['cnt'][df['tentative_diagnosis'] == each].tolist())
        for idx, row in df.iterrows():
            pinfo.append({'case_date': row['case_date'], 'tentative_diagnosis': row['tentative_diagnosis'],
                          'sick_number': row['sick_number'], 'herd_flock_number': row['herd_flock_number'],
                          'treated_number': row['treated_number']})
        categories = json.dumps(df['case_date'].unique().tolist(), default=decimal_date_default)
        name = json.dumps(df['tentative_diagnosis'].unique().tolist(), default=decimal_date_default)
        data = json.dumps(data, default=decimal_date_default)
        # print '-data--'
        # print data
        # print '-name-'
        # print name
        # print '-categories-'
        # print categories
        # print '-pinfo-'
        # print pinfo
        # data = json.loads(data)
        # categories = json.loads(categories)
        # print len(data[0])
        # print len(categories)
        # print '=data=='

    return render(request, 'reportsmodule/reports/disease_stat_chart.html',
                  {'categories': categories, 'name': name, 'data': data, 'get_division_list': get_division_list,
                   'get_species_list': get_species_list, 'get_disease_list': get_disease_list, 'start_date': start_date,
                   'end_date': end_date, 'division_id': division_id, 'district_id': district_id,
                   'title_text': title_text,
                   'upazila_id': upazila_id, 'species_id': species_id, 'disease_id': disease_id,
                   'livestock_id': livestock_id, 'loc_type': loc_type, 'geoid': geoid,
                   'pinfo': json.dumps(pinfo, default=decimal_date_default),
                   'occurace_data': json.dumps(occurace_data, default=decimal_date_default),
                   'map_no_of_occurance': json.dumps(map_no_of_occurance, default=decimal_date_default),
                   'forWhom': forWhom, 'll': ll, 'lg': lg,
                   'geojson_data': json.dumps(geojson_data, default=decimal_date_default), 'show_by_id': show_by_id})


@login_required
def disease_stat_chart_map(request):
    user_geo_data = __db_fetch_values_dict(
        """
        select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        ll = user_geo_data[0]['latitude']
        lg = user_geo_data[0]['longitude']
        # print ll
        # print lg
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
                show_by_id = 'upazilas'
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
                show_by_id = 'unions'
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
                show_by_id = 'unions'
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
            show_by_id = 'districts'
    else:
        division_id = '%'
        district_id = '%'
        upazila_id = '%'
        show_by_id = 'districts'
        loc_type = None
        geoid = None
        ll = None
        lg = None

    species_id = '%'
    disease_id = '%'
    livestock_id = '%'
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    livestock_type_str = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id', division_id)
        district_id = request.POST.get('district_id', district_id)
        upazila_id = request.POST.get('upazila_id')
        species_id = request.POST.get('species_id')
        disease_id = request.POST.get('disease_id')
        livestock_id = request.POST.get('livestock_id')
        livestock_type_str = livestock_id
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        show_by_id = request.POST.get('show_by_id')
    default_str = 'onadata/apps/reportsmodule/static/geojson/'
    if user_geo_data:
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                geojson_path_str = default_str + 'divisionwise/' + show_by_id + '/' + division_id + '_' + show_by_id + '.geojson'
            elif loc_type == 2:
                geojson_path_str = default_str + 'districtwise/' + show_by_id + '/' + district_id + '_' + show_by_id + '.geojson'
            elif loc_type == 3:
                geojson_path_str = default_str + 'upazilawise/' + show_by_id + '/' + upazila_id + '_' + show_by_id + '.geojson'

        elif user_geo_data[0]['organization_type'] == 1:
            geojson_path_str = default_str + 'centralwise/' + show_by_id + '/' + show_by_id + '.geojson'
    else:
        geojson_path_str = default_str + 'centralwise/' + show_by_id + '/' + show_by_id + '.geojson'
    # print geojson_path_str
    # Reading GeoJson
    with open(geojson_path_str) as f:
        geojson_data = json.load(f)
    # for feature in geojson_data['features']:
    #     print feature['geometry']['type']
    #     print feature['geometry']['coordinates']
    ##
    # print show_by_id

    title_text = 'Prioritized Disease Situation'

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    query_species = "select speciesid as code,speciesname as species_name from core.bahis_species_table"
    get_species_list = __db_fetch_values(query_species)

    query_disease = "select distinct on (diagnosisname) diagnosisname as code,diagnosisname as disease from core.bahis_diagnosis_table bdt order by diagnosisname asc"
    get_disease_list = __db_fetch_values(query_disease)
    # show_by
    if show_by_id == 'districts':
        query_map = """
            select
    	gc.name,
    	gc.value,
    	coalesce(fnl.count, 0) as no_of_occurance
    from
    	core.geo_cluster gc
    left join (with patient_cases as(select
    	bprlt.basic_info_district,
    	bprlt.basic_info_division,
    	bprlt.basic_info_upazila,
    	bprlt.patient_info_species,
    	date(bprlt.basic_info_date) as basic_info_date,
    	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
    	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
    	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
    	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
    	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
    	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
    	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
    	else 'Others' end as animal_type,
    	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
    from
    	core.bahis_patient_registrydyncsv_live_table bprlt)
    	select patient_cases.basic_info_district,count(*) from patient_cases
    	where patient_cases.basic_info_district like '%s'
    	and patient_cases.basic_info_division like '%s'
    	and patient_cases.basic_info_upazila like '%s'
    	and patient_cases.patient_info_species like '%s'
    	and patient_cases.animal_type like '%s'
    	and patient_cases.species_type like '%s'
    	and patient_cases.tentative_diagnosis like '%s'
    	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
        and patient_cases.basic_info_date between symmetric '%s' and '%s'
        group by patient_cases.basic_info_district) fnl
        on fnl.basic_info_district::int4 = gc.value
    where
    	gc.loc_type = 2
            """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    elif show_by_id == 'upazilas':
        query_map = """
            select
    	gc.name,
    	gc.value,
    	coalesce(fnl.count, 0) as no_of_occurance
    from
    	core.geo_cluster gc
    left join (with patient_cases as(select
    	bprlt.basic_info_district,
    	bprlt.basic_info_division,
    	bprlt.basic_info_upazila,
    	bprlt.patient_info_species,
    	date(bprlt.basic_info_date) as basic_info_date,
    	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
    	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
    	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
    	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
    	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
    	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
    	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
    	else 'Others' end as animal_type,
    	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
    from
    	core.bahis_patient_registrydyncsv_live_table bprlt)
    	select patient_cases.basic_info_upazila,count(*) from patient_cases
    	where patient_cases.basic_info_district like '%s'
    	and patient_cases.basic_info_division like '%s'
    	and patient_cases.basic_info_upazila like '%s'
    	and patient_cases.patient_info_species like '%s'
    	and patient_cases.animal_type like '%s'
    	and patient_cases.species_type like '%s'
    	and patient_cases.tentative_diagnosis like '%s'
    	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
        and patient_cases.basic_info_date between symmetric '%s' and '%s'
        group by patient_cases.basic_info_upazila) fnl
        on fnl.basic_info_upazila::int4 = gc.value
    where
    	gc.loc_type = 3
            """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    elif show_by_id == 'unions':
        query_map = """
            select
    	gc.name,
    	gc.value,
    	coalesce(fnl.count, 0) as no_of_occurance
    from
    	core.geo_cluster gc
    left join (with patient_cases as(select
    	bprlt.basic_info_district,
    	bprlt.basic_info_division,
    	bprlt.basic_info_upazila,
    	bprlt.basic_info_union,
    	bprlt.patient_info_species,
    	date(bprlt.basic_info_date) as basic_info_date,
    	to_char(date(bprlt.basic_info_date),'yyyy-mm') month_no,
    	coalesce(bprlt.patient_info_sick_number,'0') as sick_number,
    	coalesce(bprlt.patient_info_herd_flock,'0') as herd_flock_number,
    	coalesce(bprlt.diagnosis_treatment_treated,'0') as treated_number,
    	unnest(string_to_array(trim(bprlt.diagnosis_treatment_tentative_diagnosis),' ')) as tentative_diagnosis, 
    	case when bprlt.patient_info_species in ('1','3','5','8') then 'Ruminant'
    	when bprlt.patient_info_species in ('21','22','23','27') then 'Poultry'
    	else 'Others' end as animal_type,
    	case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as species_type
    from
    	core.bahis_patient_registrydyncsv_live_table bprlt)
    	select patient_cases.basic_info_union,count(*) from patient_cases
    	where patient_cases.basic_info_district like '%s'
    	and patient_cases.basic_info_division like '%s'
    	and patient_cases.basic_info_upazila like '%s'
    	and patient_cases.patient_info_species like '%s'
    	and patient_cases.animal_type like '%s'
    	and patient_cases.species_type like '%s'
    	and patient_cases.tentative_diagnosis like '%s'
    	and patient_cases.tentative_diagnosis in (select diagnosisname from core.vw_prior_diseases)
        and patient_cases.basic_info_date between symmetric '%s' and '%s'
        group by patient_cases.basic_info_union) fnl
        on fnl.basic_info_union::int4 = gc.value
    where
    	gc.loc_type = 4
            """ % (
            district_id, division_id, upazila_id, species_id, livestock_type_str, disease_id, '%', start_date, end_date)
    ##for map
    forWhom = 'central'
    if user_geo_data:
        if user_geo_data[0]['organization_type'] == 1:
            forWhom = "central"
        elif user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                # print 'division--'
                forWhom = "division"
            elif loc_type == 2:
                # print 'district--'
                forWhom = "district"
            elif loc_type == 3:
                # print 'upazila--'
                forWhom = 'upazila'

    df_map = pandas.read_sql(query_map, connection)
    # print '-----'
    # print df_map
    map_name = json.loads(json.dumps(df_map['name'].tolist()))
    map_value = json.loads(json.dumps(df_map['value'].tolist()))
    map_no_of_occurance = json.loads(json.dumps(df_map['no_of_occurance'].tolist()))
    occurace_data = make_occurace_data(map_name, map_value, map_no_of_occurance)

    return render(request, 'reportsmodule/reports/map.html',
                  {'get_division_list': get_division_list,
                   'get_species_list': get_species_list, 'get_disease_list': get_disease_list, 'start_date': start_date,
                   'end_date': end_date, 'division_id': division_id, 'district_id': district_id,
                   'title_text': title_text,
                   'upazila_id': upazila_id, 'species_id': species_id, 'disease_id': disease_id,
                   'livestock_id': livestock_id, 'loc_type': loc_type, 'geoid': geoid,
                   'occurace_data': json.dumps(occurace_data, default=decimal_date_default),
                   'map_no_of_occurance': json.dumps(map_no_of_occurance, default=decimal_date_default),
                   'forWhom': forWhom, 'll': ll, 'lg': lg,
                   'geojson_data': json.dumps(geojson_data, default=decimal_date_default), 'show_by_id': show_by_id})


@login_required
def aware_cat_reports(request):
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    loc_type = None
    geoid = None
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    fam_cnt = __db_fetch_single_value(
        """
        select
            count(*)
        from
            core.bahis_farm_assessment_p2_table
        where
            meta_instanceid not in (
            select
                basic_info_farm_id
            from
                core.bahis_farm_assessment_closer_p2_table)
            and date(basic_info_date) between symmetric '%s' and '%s'
            and basic_info_division like '%s'
            and basic_info_district like '%s'
            and basic_info_upazila like '%s'
        """ % (start_date, end_date, division_id, district_id, upazila_id))

    query = """
    with t3 as(with t2 as(with t as (
    select
        basic_info_farm_id as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, g1_product1, g1_product1_generic1, g1_product1_generic2, g1_product1_generic3, g1_product1_generic4, g2_product2, g2_product2_generic1, g2_product2_generic2, g2_product2_generic3, g2_product2_generic4, g3_product3, g3_product3_generic1, g3_product3_generic2, g3_product3_generic3, g3_product3_generic4, g4_product4, g4_product4_generic1, g4_product4_generic2, g4_product4_generic3, g4_product4_generic4, g5_product5, g5_product5_generic1, g5_product5_generic2, g5_product5_generic3, g5_product5_generic4
    from
        core.bahis_farm_assessment_followup_p2_table
    union all
    select
        meta_instanceid as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, g1_product1, g1_product1_generic1, g1_product1_generic2, g1_product1_generic3, g1_product1_generic4, g2_product2, g2_product2_generic1, g2_product2_generic2, g2_product2_generic3, g2_product2_generic4, g3_product3, g3_product3_generic1, g3_product3_generic2, g3_product3_generic3, g3_product3_generic4, g4_product4, g4_product4_generic1, g4_product4_generic2, g4_product4_generic3, g4_product4_generic4, g5_product5, g5_product5_generic1, g5_product5_generic2, g5_product5_generic3, g5_product5_generic4
    from
        core.bahis_farm_assessment_p2_table)
    select
        row_number() over (partition by farm_id
    order by
        date(basic_info_date) desc) as rn, *
    from
        t)
    select
        *
    from
        t2
    where
        rn = 1
        and farm_id not in (
        select
            basic_info_farm_id
        from
            core.bahis_farm_assessment_closer_p2_table bfacpt)
        and date(basic_info_date) between symmetric '%s' and '%s'
        and basic_info_division like '%s'
        and basic_info_district like '%s'
        and basic_info_upazila like '%s'),
    k as (
    select
        farm_id, g1_product1_generic1 as generic_name
    from
        t3
    where
        g1_product1_generic1 is not null
    union all
    select
        farm_id, g1_product1_generic2 as generic_name
    from
        t3
    where
        g1_product1_generic2 is not null
    union all
    select
        farm_id, g1_product1_generic3 as generic_name
    from
        t3
    where
        g1_product1_generic3 is not null
    union all
    select
        farm_id, g1_product1_generic4 as generic_name
    from
        t3
    where
        g1_product1_generic4 is not null
    union all
    select
        farm_id, g2_product2_generic1 as generic_name
    from
        t3
    where
        g2_product2_generic1 is not null
    union all
    select
        farm_id, g2_product2_generic2 as generic_name
    from
        t3
    where
        g2_product2_generic2 is not null
    union all
    select
        farm_id, g2_product2_generic3 as generic_name
    from
        t3
    where
        g2_product2_generic3 is not null
    union all
    select
        farm_id, g2_product2_generic4 as generic_name
    from
        t3
    where
        g2_product2_generic4 is not null
    union all
    select
        farm_id, g3_product3_generic1 as generic_name
    from
        t3
    where
        g3_product3_generic1 is not null
    union all
    select
        farm_id, g3_product3_generic2 as generic_name
    from
        t3
    where
        g3_product3_generic2 is not null
    union all
    select
        farm_id, g3_product3_generic3 as generic_name
    from
        t3
    where
        g3_product3_generic3 is not null
    union all
    select
        farm_id, g3_product3_generic4 as generic_name
    from
        t3
    where
        g3_product3_generic4 is not null
    union all
    select
        farm_id, g4_product4_generic1 as generic_name
    from
        t3
    where
        g4_product4_generic1 is not null
    union all
    select
        farm_id, g4_product4_generic2 as generic_name
    from
        t3
    where
        g4_product4_generic2 is not null
    union all
    select
        farm_id, g4_product4_generic3 as generic_name
    from
        t3
    where
        g4_product4_generic3 is not null
    union all
    select
        farm_id, g4_product4_generic4 as generic_name
    from
        t3
    where
        g4_product4_generic4 is not null
    union all
    select
        farm_id, g5_product5_generic1 as generic_name
    from
        t3
    where
        g5_product5_generic1 is not null
    union all
    select
        farm_id, g5_product5_generic2 as generic_name
    from
        t3
    where
        g5_product5_generic2 is not null
    union all
    select
        farm_id, g5_product5_generic3 as generic_name
    from
        t3
    where
        g5_product5_generic3 is not null
    union all
    select
        farm_id, g5_product5_generic4 as generic_name
    from
        t3
    where
        g5_product5_generic4 is not null),
    t5 as(
    select
        count(*) as fam_cnt
    from
        t3),
    j as(
    select
        *
    from
        core.vw_antibiotics_list),
    fx as(
    select
        distinct on
        (k.farm_id) k.*, j.generic_aware_class, j.generic_aware_category
    from
        k, j
    where
        j.generic_label = k.generic_name),
    tx as(
    select
        aware_cats, count(fx.farm_id) as fc
    from
        fx
    right join (
        select
            unnest(string_to_array('ACCESS,WATCH,RESERVE', ',')) as aware_cats) gx on
        gx.aware_cats = fx.generic_aware_category
    group by
        gx.aware_cats)
    select
        tx.aware_cats,
        coalesce(tx.fc::float / nullif(t5.fam_cnt::float, 0) * 100, 0) as fc
    from
        tx,
        t5
    """ % (start_date, end_date, division_id, district_id, upazila_id)

    try:
        df = pandas.read_sql(query, connection, coerce_float=True)
        df_headers = list(df)
        df_cat_col = df_headers[0]
        df_headers.pop(0)
        chart_data = generate_chart_data(df, df_cat_col, df_headers, None, ['ACCESS', 'WATCH', 'RESERVE'])
    except Exception, e:
        chart_data = {'categories': [], 'series': [], 'datasum': 'NULL'}

    query2 = """
    with t3 as(with t2 as(with t as (
    select
        basic_info_farm_id as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, g1_product1, g1_product1_generic1, g1_product1_generic2, g1_product1_generic3, g1_product1_generic4, g2_product2, g2_product2_generic1, g2_product2_generic2, g2_product2_generic3, g2_product2_generic4, g3_product3, g3_product3_generic1, g3_product3_generic2, g3_product3_generic3, g3_product3_generic4, g4_product4, g4_product4_generic1, g4_product4_generic2, g4_product4_generic3, g4_product4_generic4, g5_product5, g5_product5_generic1, g5_product5_generic2, g5_product5_generic3, g5_product5_generic4
    from
        core.bahis_farm_assessment_followup_p2_table
    union all
    select
        meta_instanceid as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, g1_product1, g1_product1_generic1, g1_product1_generic2, g1_product1_generic3, g1_product1_generic4, g2_product2, g2_product2_generic1, g2_product2_generic2, g2_product2_generic3, g2_product2_generic4, g3_product3, g3_product3_generic1, g3_product3_generic2, g3_product3_generic3, g3_product3_generic4, g4_product4, g4_product4_generic1, g4_product4_generic2, g4_product4_generic3, g4_product4_generic4, g5_product5, g5_product5_generic1, g5_product5_generic2, g5_product5_generic3, g5_product5_generic4
    from
        core.bahis_farm_assessment_p2_table)
    select
        row_number() over (partition by farm_id
    order by
        date(basic_info_date) desc) as rn, *
    from
        t)
    select
        *
    from
        t2
    where
        rn = 1
        and farm_id not in (
        select
            basic_info_farm_id
        from
            core.bahis_farm_assessment_closer_p2_table bfacpt)
        and date(basic_info_date) between symmetric '%s' and '%s'
        and basic_info_division like '%s'
        and basic_info_district like '%s'
        and basic_info_upazila like '%s'),
    k as (
    select
        farm_id, g1_product1_generic1 as generic_name
    from
        t3
    where
        g1_product1_generic1 is not null
    union all
    select
        farm_id, g1_product1_generic2 as generic_name
    from
        t3
    where
        g1_product1_generic2 is not null
    union all
    select
        farm_id, g1_product1_generic3 as generic_name
    from
        t3
    where
        g1_product1_generic3 is not null
    union all
    select
        farm_id, g1_product1_generic4 as generic_name
    from
        t3
    where
        g1_product1_generic4 is not null
    union all
    select
        farm_id, g2_product2_generic1 as generic_name
    from
        t3
    where
        g2_product2_generic1 is not null
    union all
    select
        farm_id, g2_product2_generic2 as generic_name
    from
        t3
    where
        g2_product2_generic2 is not null
    union all
    select
        farm_id, g2_product2_generic3 as generic_name
    from
        t3
    where
        g2_product2_generic3 is not null
    union all
    select
        farm_id, g2_product2_generic4 as generic_name
    from
        t3
    where
        g2_product2_generic4 is not null
    union all
    select
        farm_id, g3_product3_generic1 as generic_name
    from
        t3
    where
        g3_product3_generic1 is not null
    union all
    select
        farm_id, g3_product3_generic2 as generic_name
    from
        t3
    where
        g3_product3_generic2 is not null
    union all
    select
        farm_id, g3_product3_generic3 as generic_name
    from
        t3
    where
        g3_product3_generic3 is not null
    union all
    select
        farm_id, g3_product3_generic4 as generic_name
    from
        t3
    where
        g3_product3_generic4 is not null
    union all
    select
        farm_id, g4_product4_generic1 as generic_name
    from
        t3
    where
        g4_product4_generic1 is not null
    union all
    select
        farm_id, g4_product4_generic2 as generic_name
    from
        t3
    where
        g4_product4_generic2 is not null
    union all
    select
        farm_id, g4_product4_generic3 as generic_name
    from
        t3
    where
        g4_product4_generic3 is not null
    union all
    select
        farm_id, g4_product4_generic4 as generic_name
    from
        t3
    where
        g4_product4_generic4 is not null
    union all
    select
        farm_id, g5_product5_generic1 as generic_name
    from
        t3
    where
        g5_product5_generic1 is not null
    union all
    select
        farm_id, g5_product5_generic2 as generic_name
    from
        t3
    where
        g5_product5_generic2 is not null
    union all
    select
        farm_id, g5_product5_generic3 as generic_name
    from
        t3
    where
        g5_product5_generic3 is not null
    union all
    select
        farm_id, g5_product5_generic4 as generic_name
    from
        t3
    where
        g5_product5_generic4 is not null),
    t5 as(
    select
        count(*) as fam_cnt
    from
        t3),
    j as(
    select
        *
    from
        core.vw_antibiotics_list),
    fx as(
    select
        distinct on
        (k.farm_id) k.*, j.generic_aware_class, j.generic_aware_category
    from
        k, j
    where
        j.generic_label = k.generic_name),
    tx as(
    select
        gx.generic_aware_class, count(fx.farm_id) as fc
    from
        fx
    right join (with q as(
        select
            generic1_aware_class as generic_aware_class
        from
            core.bahis_medicine_table bmt
        where
            generic1_aware_class != ''
            and treatment_type = 'Antibiotic'
    union all
        select
            generic2_aware_class as generic_aware_class
        from
            core.bahis_medicine_table bmt
        where
            generic2_aware_class != ''
            and treatment_type = 'Antibiotic'
    union all
        select
            generic3_aware_class as generic_aware_class
        from
            core.bahis_medicine_table bmt
        where
            generic3_aware_class != ''
            and treatment_type = 'Antibiotic'
    union all
        select
            generic4_aware_class as generic_aware_class
        from
            core.bahis_medicine_table bmt
        where
            generic4_aware_class != ''
            and treatment_type = 'Antibiotic')
        select
            distinct generic_aware_class
        from
            q
        where
            generic_aware_class != '') gx on
        gx.generic_aware_class = fx.generic_aware_category
    group by
        gx.generic_aware_class)
    select
        tx.generic_aware_class,
        tx.fc
    from
        tx,
        t5
    """ % (start_date, end_date, division_id, district_id, upazila_id)

    df2 = pandas.read_sql(query2, connection, coerce_float=True)
    pchart_data = generate_pie_chart_data(df2, 'generic_aware_class', 'fc')

    return render(request, 'reportsmodule/reports/aware_cat_reports.html',
                  {'pchart_data': json.dumps(pchart_data), 'chart_data': json.dumps(chart_data),
                   'get_division_list': get_division_list, 'start_date': start_date, 'end_date': end_date,
                   'division_id': division_id, 'district_id': district_id, 'upazila_id': upazila_id,
                   'loc_type': loc_type, 'geoid': geoid, 'fam_cnt': fam_cnt})


@login_required
def biosecurity_reports(request):
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    loc_type = None
    geoid = None
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    practice_id = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        practice_id = request.POST.get('practice_id')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)
    if practice_id == '%':
        fixed_cat = ['A.1 Outside vehicles do not enter farm, only essential vehicles',
                     'A.2 Only workers and approved visitors enter farm', 'A.3 No manure collectors enter farm',
                     'A.4 Farm area is fully fenced and duck/chicken proof', 'A.5 Dead birds disposed safely',
                     'A.6 Signs posted', 'B.1 No movement of vehicles in and out the production area',
                     'B.2 Only workers enter production area',
                     'B.3 Only visitors enter production area if accompanied by farm manager', 'B.4 Signs posted',
                     'C.1 Outside footwear left outside farm',
                     'C.2 Workers and visitors change clothes upon entering farm',
                     'C.3 Workers and visitors use only dedicated footwear in production area',
                     'C.4 Worker and visitors shower upon entering farm',
                     'D.1 materials returning from market or other farm cleaned with soap and water before entering the farm',
                     'D.2 materials returning from market or other farm disinfected before entering the farm']
    elif practice_id == 'A':
        fixed_cat = ['A.1 Outside vehicles do not enter farm, only essential vehicles',
                     'A.2 Only workers and approved visitors enter farm', 'A.3 No manure collectors enter farm',
                     'A.4 Farm area is fully fenced and duck/chicken proof', 'A.5 Dead birds disposed safely',
                     'A.6 Signs posted']
    elif practice_id == 'B':
        fixed_cat = ['B.1 No movement of vehicles in and out the production area',
                     'B.2 Only workers enter production area',
                     'B.3 Only visitors enter production area if accompanied by farm manager', 'B.4 Signs posted']
    elif practice_id == 'C':
        fixed_cat = ['C.1 Outside footwear left outside farm',
                     'C.2 Workers and visitors change clothes upon entering farm',
                     'C.3 Workers and visitors use only dedicated footwear in production area',
                     'C.4 Worker and visitors shower upon entering farm']
    elif practice_id == 'D':
        fixed_cat = [
            'D.1 materials returning from market or other farm cleaned with soap and water before entering the farm',
            'D.2 materials returning from market or other farm disinfected before entering the farm']

    query = """
    with t6 as( with t3 as(with t2 as(with t as(
    select
        meta_instanceid as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, biosecurity_practices_outsider_vehicles_entry, biosecurity_practices_workers_approve_visitor_entry, biosecurity_practices_visitors_approved_production_area, biosecurity_practices_manure_collector_entry, biosecurity_practices_fenced_and_duck_chicken_proof, biosecurity_practices_dead_birds_disposed_safely, biosecurity_practices_sign_posted_1st, biosecurity_practices_vehical_movement_production_area, biosecurity_practices_workers_entry_production_area, biosecurity_practices_sign_posted_2nd, biosecurity_practices_footwear_left_outside, biosecurity_practices_change_clothes_upon_entering_farm, biosecurity_practices_use_dedicated_footwear, biosecurity_practices_shower_before_enter_farm, biosecurity_practices_materials_cleaned, biosecurity_practices_materials_disinfect
    from
        core.bahis_farm_assessment_p2_table
    union all
    select
        basic_info_farm_id as farm_id, basic_info_date, basic_info_division, basic_info_district, basic_info_upazila, biosecurity_practices_outsider_vehicles_entry, biosecurity_practices_workers_approve_visitor_entry, biosecurity_practices_visitors_approved_production_area, biosecurity_practices_manure_collector_entry, biosecurity_practices_fenced_and_duck_chicken_proof, biosecurity_practices_dead_birds_disposed_safely, biosecurity_practices_sign_posted_1st, biosecurity_practices_vehical_movement_production_area, biosecurity_practices_workers_entry_production_area, biosecurity_practices_sign_posted_2nd, biosecurity_practices_footwear_left_outside, biosecurity_practices_change_clothes_upon_entering_farm, biosecurity_practices_use_dedicated_footwear, biosecurity_practices_shower_before_enter_farm, biosecurity_practices_materials_cleaned, biosecurity_practices_materials_disinfect
    from
        core.bahis_farm_assessment_followup_p2_table)
    select
        row_number() over (partition by farm_id
    order by
        date(basic_info_date) desc) as rn, *
    from
        t)
    select
        *
    from
        t2
    where
        rn = 1
        and date(basic_info_date) between symmetric '%s' and '%s'
        and basic_info_division like '%s'
        and basic_info_district like '%s'
        and basic_info_upazila like '%s'
        and farm_id not in (
        select
            basic_info_farm_id
        from
            core.bahis_farm_assessment_closer_p2_table)) , t4 as(
    select
        Count(*) as fc
    from
        t3), t5 as (
    select
        Count(*) filter (
        where biosecurity_practices_outsider_vehicles_entry = '1') as biosecurity_practices_outsider_vehicles_entry, count(*) filter (
        where biosecurity_practices_workers_approve_visitor_entry = '1') as biosecurity_practices_workers_approve_visitor_entry, count(*) filter (
        where biosecurity_practices_manure_collector_entry = '1') as biosecurity_practices_manure_collector_entry, count(*) filter (
        where biosecurity_practices_fenced_and_duck_chicken_proof = '1') as biosecurity_practices_fenced_and_duck_chicken_proof, count(*) filter (
        where biosecurity_practices_dead_birds_disposed_safely = '1') as biosecurity_practices_dead_birds_disposed_safely, count(*) filter (
        where biosecurity_practices_sign_posted_1st = '1') as biosecurity_practices_sign_posted_1st, count(*) filter (
        where biosecurity_practices_vehical_movement_production_area = '1') as biosecurity_practices_vehical_movement_production_area, count(*) filter (
        where biosecurity_practices_workers_entry_production_area = '1') as biosecurity_practices_workers_entry_production_area, count(*) filter (
        where biosecurity_practices_visitors_approved_production_area = '1') as biosecurity_practices_visitors_approved_production_area, count(*) filter (
        where biosecurity_practices_sign_posted_2nd = '1') as biosecurity_practices_sign_posted_2nd, count(*) filter (
        where biosecurity_practices_footwear_left_outside = '1') as biosecurity_practices_footwear_left_outside, count(*) filter (
        where biosecurity_practices_change_clothes_upon_entering_farm = '1') as biosecurity_practices_change_clothes_upon_entering_farm, count(*) filter (
        where biosecurity_practices_use_dedicated_footwear = '1') as biosecurity_practices_use_dedicated_footwear, count(*) filter (
        where biosecurity_practices_shower_before_enter_farm = '1') as biosecurity_practices_shower_before_enter_farm, count(*) filter (
        where biosecurity_practices_materials_cleaned = '1') as biosecurity_practices_materials_cleaned, count(*) filter (
        where biosecurity_practices_materials_disinfect = '1') as biosecurity_practices_materials_disinfect
    from
        t3)
    select
        'A' as practice_type, 'A.1 Outside vehicles do not enter farm, only essential vehicles (e.g. feed, egg)' as biopractice, to_char((biosecurity_practices_outsider_vehicles_entry::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'A' as practice_type, 'A.2 Only workers and approved visitors enter farm (select one)' as biopractice, to_char((biosecurity_practices_workers_approve_visitor_entry::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'A' as practice_type, 'A.3 No manure collectors enter farm' as biopractice, to_char((biosecurity_practices_manure_collector_entry::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'A' as practice_type, 'A.4 Farm area is fully fenced and duck/chicken proof' as biopractice, to_char((biosecurity_practices_fenced_and_duck_chicken_proof::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'A' as practice_type, 'A.5 Dead birds disposed safely' as biopractice, to_char((biosecurity_practices_dead_birds_disposed_safely::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'A' as practice_type, 'A.6 Signs posted' as biopractice, to_char((biosecurity_practices_sign_posted_1st::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'B' as practice_type, 'B.1 No movement of vehicles in and out the production area' as biopractice, to_char((biosecurity_practices_vehical_movement_production_area::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'B' as practice_type, 'B.2 Only workers enter production area (select one option)' as biopractice, to_char((biosecurity_practices_workers_entry_production_area::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'B' as practice_type, 'B.3 Only visitors enter production area if accompanied by farm manager' as biopractice, to_char((biosecurity_practices_visitors_approved_production_area::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'B' as practice_type, 'B.4 Signs posted (you are allowed select only one option)' as biopractice, to_char((biosecurity_practices_sign_posted_2nd::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'C' as practice_type, 'C.1 Outside footwear left outside farm (select one option)' as biopractice, to_char((biosecurity_practices_footwear_left_outside::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'C' as practice_type, 'C.2 Workers and visitors change clothes upon entering farm' as biopractice, to_char((biosecurity_practices_change_clothes_upon_entering_farm::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'C' as practice_type, 'C.3 Workers and visitors use only dedicated footwear in production area' as biopractice, to_char((biosecurity_practices_use_dedicated_footwear::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'C' as practice_type, 'C.4 Worker and visitors shower upon entering farm' as biopractice, to_char((biosecurity_practices_shower_before_enter_farm::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'D' as practice_type, 'D.1 materials returning from market or other farm cleaned with soap and water before entering the farm' as biopractice, to_char((biosecurity_practices_materials_cleaned::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4
    union all
    select
        'D' as practice_type, 'D.2 materials returning from market or other farm disinfected before entering the farm' as biopractice, to_char((biosecurity_practices_materials_disinfect::float / nullif(t4.fc::float , 0)) * 100, 'FM999999999.00') as amount
    from
        t5, t4)
    select
        biopractice,
        amount
    from
        t6
    where
        practice_type like '%s'
    """ % (start_date, end_date, division_id, district_id, upazila_id, practice_id)

    df = pandas.read_sql(query, connection, coerce_float=True)
    df_headers = list(df)
    df_cat_col = df_headers[0]
    df_headers.pop(0)
    chart_data = generate_chart_data(df, df_cat_col, df_headers, None, fixed_cat)
    return render(request, 'reportsmodule/reports/biosecurity_reports.html',
                  {'chart_data': json.dumps(chart_data), 'get_division_list': get_division_list,
                   'start_date': start_date, 'end_date': end_date, 'division_id': division_id,
                   'district_id': district_id, 'upazila_id': upazila_id, 'practice_id': practice_id,
                   'loc_type': loc_type, 'geoid': geoid})


@login_required
def patient_aware_cat_reports(request):
    livestock_id = '%'
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    loc_type = None
    geoid = None
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        livestock_id = request.POST.get('livestock_id')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    pcnt = __db_fetch_single_value(
        """
        select count(*) from core.bahis_patient_registrydyncsv_live_table bprlt
        where bprlt.basic_info_division like '%s'
        and bprlt.basic_info_district like '%s'
        and bprlt.basic_info_upazila like '%s'
        and date(bprlt.basic_info_date) between symmetric '%s' and '%s'
        """ % (division_id, district_id, upazila_id, start_date, end_date))

    query = """
    with tx as(with tbl2 as (with tbl3 as(with s as(with t2 as(with t as(select id as patient_id,basic_info_date,basic_info_division,basic_info_district,basic_info_upazila,
    unnest(string_to_array(trim(diagnosis_treatment_treatment_govt),' ')) diagnosis_treatment_treatment_govt,
    diagnosis_treatment_treatment_govt_other,
    unnest(string_to_array(trim(diagnosis_treatment_treatment_own),' ')) diagnosis_treatment_treatment_own,
    diagnosis_treatment_treatment_own_other, 
    case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as livestock_type
    from core.bahis_patient_registrydyncsv_live_table bprlt
    where date(bprlt.basic_info_date) between symmetric '%s' and '%s'
        and bprlt.basic_info_division like '%s'
        and bprlt.basic_info_district like '%s'
        and bprlt.basic_info_upazila like '%s')
    select t.*,bmt.product_label as treatment_govt,bmt2.product_label as treatment_own from t
    left join core.bahis_medicine_table bmt
    on bmt.product_id = t.diagnosis_treatment_treatment_govt
    left join core.bahis_medicine_table bmt2
    on bmt2.product_id = t.diagnosis_treatment_treatment_own
    where t.livestock_type like '%s')
    select date(basic_info_date) basic_info_date,patient_id,case treatment_govt when 'Other' then diagnosis_treatment_treatment_govt_other else treatment_govt end as treatment from t2
    union all
    select date(basic_info_date) basic_info_date,patient_id,case treatment_own when 'Other' then diagnosis_treatment_treatment_own_other else treatment_own end as treatment from t2)
    select
        row_number() over(partition by s.patient_id
    order by
        DATE(s.basic_info_date) desc) as rn,*
    from
        s
    inner join core.vw_antibiotics_list val on
        val.product_label = s.treatment)
        select * from tbl3 where rn = 1)
        select
        aware_cats, Count(patient_id) as fc
    from
        tbl2
    right join (
        select
            unnest(String_to_array('ACCESS,WATCH,RESERVE', ',')) as aware_cats) gx on
        gx.aware_cats = tbl2.generic_aware_category
    group by
        gx.aware_cats),
    dx as(with dx1 as(
select *,case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as livestock_type from core.bahis_patient_registrydyncsv_live_table bprlt
        where bprlt.basic_info_division like '%s'
        and bprlt.basic_info_district like '%s'
        and bprlt.basic_info_upazila like '%s'
        and date(bprlt.basic_info_date) between symmetric '%s' and '%s')
        select count(*) pcnt from dx1
        where livestock_type like '%s')
            select
        tx.aware_cats,
        tx.fc::float / dx.pcnt::float * 100 as fc
    from
        tx,
        dx
    """ % (
        start_date, end_date, division_id, district_id, upazila_id, livestock_id, division_id, district_id, upazila_id,
        start_date, end_date, livestock_id)

    try:
        df = pandas.read_sql(query, connection, coerce_float=True)
        df_headers = list(df)
        df_cat_col = df_headers[0]
        df_headers.pop(0)
        chart_data = generate_chart_data(df, df_cat_col, df_headers, None, ['ACCESS', 'WATCH', 'RESERVE'])
    except Exception, e:
        chart_data = {'categories': [], 'series': [], 'datasum': 'NULL'}

    query2 = """
    with tbl2 as (with tbl3 as(with s as(with t2 as(with t as(select id as patient_id,basic_info_date,basic_info_division,basic_info_district,basic_info_upazila,
    unnest(string_to_array(trim(diagnosis_treatment_treatment_govt),' ')) diagnosis_treatment_treatment_govt,
    diagnosis_treatment_treatment_govt_other,
    unnest(string_to_array(trim(diagnosis_treatment_treatment_own),' ')) diagnosis_treatment_treatment_own,
    diagnosis_treatment_treatment_own_other, 
    case when bprlt.patient_info_species in ('1','2','3','4','5','6','7','8') then 'Mammal' else 'Bird' end as livestock_type
    from core.bahis_patient_registrydyncsv_live_table bprlt
    where date(bprlt.basic_info_date) between symmetric '%s' and '%s'
        and bprlt.basic_info_division like '%s'
        and bprlt.basic_info_district like '%s'
        and bprlt.basic_info_upazila like '%s')
    select t.*,bmt.product_label as treatment_govt,bmt2.product_label as treatment_own from t
    left join core.bahis_medicine_table bmt
    on bmt.product_id = t.diagnosis_treatment_treatment_govt
    left join core.bahis_medicine_table bmt2
    on bmt2.product_id = t.diagnosis_treatment_treatment_own
    where t.livestock_type like '%s')
    select date(basic_info_date) basic_info_date,patient_id,case treatment_govt when 'Other' then diagnosis_treatment_treatment_govt_other else treatment_govt end as treatment from t2
    union all
    select date(basic_info_date) basic_info_date,patient_id,case treatment_own when 'Other' then diagnosis_treatment_treatment_own_other else treatment_own end as treatment from t2)
    select
        row_number() over(partition by s.patient_id
    order by
        DATE(s.basic_info_date) desc) as rn,*
    from
        s
    inner join core.vw_antibiotics_list val on
        val.product_label = s.treatment)
        select * from tbl3 where rn = 1)
        select
        gx.generic_aware_class, Count(patient_id) as fc
    from
        tbl2
    right join (with q as(
            select
                generic1_aware_class as generic_aware_class
            from
                core.bahis_medicine_table bmt
            where
                generic1_aware_class != ''
                and treatment_type = 'Antibiotic'
        union all
            select
                generic2_aware_class as generic_aware_class
            from
                core.bahis_medicine_table bmt
            where
                generic2_aware_class != ''
                and treatment_type = 'Antibiotic'
        union all
            select
                generic3_aware_class as generic_aware_class
            from
                core.bahis_medicine_table bmt
            where
                generic3_aware_class != ''
                and treatment_type = 'Antibiotic'
        union all
            select
                generic4_aware_class as generic_aware_class
            from
                core.bahis_medicine_table bmt
            where
                generic4_aware_class != ''
                and treatment_type = 'Antibiotic')
            select
                distinct generic_aware_class
            from
                q
            where
                generic_aware_class != '') gx on
        gx.generic_aware_class = tbl2.generic_aware_class
    group by
        gx.generic_aware_class
    """ % (start_date, end_date, division_id, district_id, upazila_id, livestock_id)

    df2 = pandas.read_sql(query2, connection, coerce_float=True)
    pchart_data = generate_pie_chart_data(df2, 'generic_aware_class', 'fc')

    return render(request, 'reportsmodule/reports/patient_aware_cat_reports.html',
                  {'pchart_data': json.dumps(pchart_data), 'chart_data': json.dumps(chart_data),
                   'get_division_list': get_division_list, 'start_date': start_date, 'end_date': end_date,
                   'division_id': division_id, 'district_id': district_id, 'upazila_id': upazila_id,
                   'loc_type': loc_type, 'geoid': geoid, 'livestock_id': livestock_id, 'pcnt': pcnt})


def generate_chart_data(df, yaxis, xaxis, fd_type, predefined_cats=None):
    if fd_type is not None:
        datasum = df.iloc[0]['denominator']
        df.drop('denominator', axis=1, inplace=True)
        xaxis.remove('denominator')
    else:
        datasum = 'NULL'

    categories = []
    series = [{} for _ in range(len(xaxis))]

    if predefined_cats is None:
        for index, row in df.iterrows():
            categories.append(str(row[yaxis].encode('UTF-8')))
            c = 0
            for xx in xaxis:
                # percentage = round(float(row[xx]) / float(sum(df[xx])) * 100, 1) if sum(df[xx]) != 0 else 0
                if not series[c].has_key('data'):
                    series[c]['data'] = []
                series[c]['data'].append({'y': float(checkNone(row[xx]))})
                if not series[c].has_key('name'):
                    series[c]['name'] = xx
                c = c + 1
    else:
        categories = predefined_cats
        for pc in predefined_cats:
            for index, row in df.iterrows():
                if row[yaxis] == pc:
                    c = 0
                    for xx in xaxis:
                        # percentage = round(float(row[xx]) / float(sum(df[xx])) * 100, 1) if sum(df[xx]) != 0 else 0
                        if not series[c].has_key('data'):
                            series[c]['data'] = []
                        series[c]['data'].append({'y': float(checkNone(row[xx]))})
                        if not series[c].has_key('name'):
                            series[c]['name'] = xx
                        c = c + 1

    return {'categories': categories, 'series': series, 'datasum': datasum}


def generate_pie_chart_data(df, label, value):
    dataseries = []
    for index, row in df.iterrows():
        d = []
        d.append(row[label].encode('utf-8'))
        d.append(row[value])
        dataseries.append(d)
    return dataseries


def checkNone(val):
    if val is None:
        return 0
    else:
        return val


@login_required
def sick_treated_report(request):
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = datetime.datetime.now() + timedelta(-30)
    start_date = start_date.strftime("%Y-%m-%d")
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    disagg_id = '3'
    loc_type = None
    geoid = None
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
                disagg_id = '1'
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
                disagg_id = '2'
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
                disagg_id = str(loc_type)
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'
            disagg_id = '3'
    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')
        start_date = request.POST.get('collecion_from_date')
        end_date = request.POST.get('collecion_to_date')
        disagg_id = request.POST.get('disagg_id')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)

    if disagg_id == '3':
        query = """
        with t as(select gd1.field_name as division_name,gd2.field_name as district_name,gd3.field_name as upazila_name,
        bprlt.patient_info_sick_number::int4,bprlt.diagnosis_treatment_treated::int4 from core.bahis_patient_registrydyncsv_live_table bprlt
        left join core.geo_data gd1
        on gd1.geocode = bprlt.basic_info_division
        left join core.geo_data gd2
        on gd2.geocode = bprlt.basic_info_district
        left join core.geo_data gd3
        on gd3.geocode = bprlt.basic_info_upazila
        where basic_info_division like '%s'
        and basic_info_district like '%s'
        and basic_info_upazila like '%s'
        and date(basic_info_date) between symmetric '%s' and '%s')
        select division_name,district_name,upazila_name,sum(patient_info_sick_number) as sick_number,sum(diagnosis_treatment_treated) as treated_number from t
        group by division_name,district_name,upazila_name
                """ % (division_id, district_id, upazila_id, start_date, end_date)
    elif disagg_id == '2':
        query = """
                with t as(select gd1.field_name as division_name,gd2.field_name as district_name,gd3.field_name as upazila_name,
                bprlt.patient_info_sick_number::int4,bprlt.diagnosis_treatment_treated::int4 from core.bahis_patient_registrydyncsv_live_table bprlt
                left join core.geo_data gd1
                on gd1.geocode = bprlt.basic_info_division
                left join core.geo_data gd2
                on gd2.geocode = bprlt.basic_info_district
                left join core.geo_data gd3
                on gd3.geocode = bprlt.basic_info_upazila
                where basic_info_division like '%s'
                and basic_info_district like '%s'
                and basic_info_upazila like '%s'
                and date(basic_info_date) between symmetric '%s' and '%s')
                select division_name,district_name,sum(patient_info_sick_number) as sick_number,sum(diagnosis_treatment_treated) as treated_number from t
                group by division_name,district_name
                        """ % (division_id, district_id, upazila_id, start_date, end_date)
    elif disagg_id == '1':
        query = """
            with t as(select gd1.field_name as division_name,gd2.field_name as district_name,gd3.field_name as upazila_name,
            bprlt.patient_info_sick_number::int4,bprlt.diagnosis_treatment_treated::int4 from core.bahis_patient_registrydyncsv_live_table bprlt
            left join core.geo_data gd1
            on gd1.geocode = bprlt.basic_info_division
            left join core.geo_data gd2
            on gd2.geocode = bprlt.basic_info_district
            left join core.geo_data gd3
            on gd3.geocode = bprlt.basic_info_upazila
            where basic_info_division like '%s'
            and basic_info_district like '%s'
            and basic_info_upazila like '%s'
            and date(basic_info_date) between symmetric '%s' and '%s')
            select division_name,sum(patient_info_sick_number) as sick_number,sum(diagnosis_treatment_treated) as treated_number from t
            group by division_name
                    """ % (division_id, district_id, upazila_id, start_date, end_date)
    sick_treated_data = __db_fetch_values_dict(query)
    return render(request, 'reportsmodule/reports/sick_treated_report.html',
                  {'sick_treated_data': sick_treated_data, 'get_division_list': get_division_list,
                   'start_date': start_date, 'end_date': end_date,
                   'division_id': division_id, 'district_id': district_id, 'upazila_id': upazila_id,
                   'loc_type': loc_type, 'geoid': geoid, 'disagg_id': disagg_id})


@login_required
def submission_count_list(request):
    all_geo_id = []
    col_name = []
    json_data = []
    loc_type = None
    geoid = None
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)
    select_query = """
    with p as(with q as (with dx as (select li.id,lx.id_string from instance.logger_instance li 
    left join instance.logger_xform lx
    on lx.id = li.xform_id
    where li.deleted_at is null
    and lx.id_string in ('patient_registrydyncsv_live','farm_assessment_p2','avian_influenza_investigate_p2','avian_influenza_sample_p2','disease_investigation_p2','participatory_livestock_assessment'))
    select 'Patients Registry'as form_name,bprlt.basic_info_division as division,bprlt.basic_info_district as district,bprlt.basic_info_upazila as upazila,date(bprlt.basic_info_date) as action_date from core.bahis_patient_registrydyncsv_live_table bprlt, dx where instanceid::int8 in (dx.id) 
    union all
    select 'Farm Assessment Monitoring'as form_name,bfapt.basic_info_division as division,bfapt.basic_info_district as district,bfapt.basic_info_upazila as upazila,date(bfapt.basic_info_date) as action_date from core.bahis_farm_assessment_p2_table bfapt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Avian Influenza Investigation'as form_name,baiipt.basic_info_division as division,baiipt.basic_info_district as district,baiipt.basic_info_upazila as upazila,date(baiipt.basic_info_date) as action_date from core.bahis_avian_influenza_investigate_p2_table baiipt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Avian Influenza Sample'as form_name,baispt.basic_info_division as division,baispt.basic_info_district as district,baispt.basic_info_upazila as upazila,date(baispt.basic_info_date) as action_date from core.bahis_avian_influenza_sample_p2_table baispt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Disease Investigation'as form_name,bdipt.basic_info_division as division,bdipt.basic_info_district as district,bdipt.basic_info_upazila as upazila,date(bdipt.basic_info_date) as action_date from core.bahis_disease_investigation_p2_table bdipt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Participatory Livestock Assessment'as form_name,bplat.basic_info_division as division,bplat.basic_info_district as district,bplat.basic_info_upazila as upazila,date(bplat.basic_info_date) as action_date from core.bahis_participatory_livestock_assessment_table bplat, dx where instanceid::int8 in (dx.id))
    select *,Date_part('year', Date(action_date)) as yr, Date_part('month', Date(action_date)) as mon, Date_part('day', Date(action_date)) as day from q
    where division like '%s'
    and district like '%s'
    and upazila like '%s'
    )
    select
        form_name,
        Count(*) filter (
        where date_part('day', CURRENT_DATE) = day) as cday,
        count(*) filter (
        where date_part('month', CURRENT_DATE) = mon) as cmonth,
        count(*) filter (
        where date_part('year', CURRENT_DATE) = yr) as cyear,
        count(*) filter (
        where date_part('year', CURRENT_DATE) -1 = yr) as last_yr,
        count(*) as total
    from
        p
    group by
        form_name
    order by
        form_name
    """ % (division_id,district_id,upazila_id)

    data = __db_fetch_values_dict(select_query)
    for each1 in data:
        json_data.append(handle_none(each1))
        for key, value in each1.items():
            if key not in col_name and key != "data_id":
                # unique column name insert in col_name list
                col_name.append(key)
    all_geo_id.append(1)
    return render(request, 'reportsmodule/reports/submission_count_list.html',
                  {'get_division_list': get_division_list, 'col_name': col_name, 'json_data': json_data, 'all_geo_id': all_geo_id,
                   'division_id': division_id, 'district_id': district_id, 'upazila_id': upazila_id,
                   'loc_type': loc_type, 'geoid': geoid
                   })



@login_required
def form_summary_report(request):
    all_geo_id = []
    col_name = []
    json_data = []
    loc_type = None
    geoid = None
    division_id = '%'
    district_id = '%'
    upazila_id = '%'
    user_geo_data = __db_fetch_values_dict(
        """
    select bca.id,case ub.organization_id when 10 then 2 when 41 then 3 else 1 end as organization_type,bca.geoid,
    gd.field_type_id as loc_type from core.branch_catchment_area bca 
    left join core.geo_data gd on
    gd.geocode::int8 = bca.geoid
    left join core.usermodule_branch ub
    on ub.id = bca.branch_id 
    where bca.branch_id in (
    select branch_id from core.usermodule_userbranchmap uu where user_id = """ + str(request.user.id) + """)"""
    )
    if user_geo_data:
        loc_type = user_geo_data[0]['loc_type']
        geoid = user_geo_data[0]['geoid']
        if user_geo_data[0]['organization_type'] == 2:
            if loc_type == 1:
                division_id = geoid
            else:
                division_id = '%'

            if loc_type == 2:
                district_id = geoid
            else:
                district_id = '%'
            if loc_type == 3:
                upazila_id = geoid
            else:
                upazila_id = '%'
        elif user_geo_data[0]['organization_type'] == 1:
            division_id = '%'
            district_id = '%'
            upazila_id = '%'

    if request.method == 'POST':
        division_id = request.POST.get('division_id')
        district_id = request.POST.get('district_id')
        upazila_id = request.POST.get('upazila_id')

    query_division = "select value,name as division_name from core.geo_cluster where loc_type = 1"
    get_division_list = __db_fetch_values(query_division)
    select_query = """
    with gl as(select gd1.field_name as div_name,gd1.geocode as div_code,
    gd2.field_name as dist_name,gd2.geocode as dist_code,
    gd3.field_name as upz_name,gd3.geocode as upz_code
    from core.geo_data gd1
    left join core.geo_data gd2
    on gd2.field_parent_id = gd1.id
    left join core.geo_data gd3
    on gd3.field_parent_id = gd2.id
    where gd1.field_type_id = 1
    and gd2.field_type_id = 2
    and gd3.field_type_id = 3
    and gd1.geocode like '%s'
    and gd2.geocode like '%s'
    and gd3.geocode like '%s'),
    datax as (with dx as (select li.id,lx.id_string from instance.logger_instance li 
    left join instance.logger_xform lx
    on lx.id = li.xform_id
    where li.deleted_at is null
    and lx.id_string in ('patient_registrydyncsv_live','farm_assessment_p2','avian_influenza_investigate_p2','avian_influenza_sample_p2','disease_investigation_p2','participatory_livestock_assessment'))
    select 'Patients Registry'as form_name,bprlt.basic_info_division as division,bprlt.basic_info_district as district,bprlt.basic_info_upazila as upazila,date(bprlt.basic_info_date) as action_date from core.bahis_patient_registrydyncsv_live_table bprlt, dx where instanceid::int8 in (dx.id) 
    union all
    select 'Farm Assessment Monitoring'as form_name,bfapt.basic_info_division as division,bfapt.basic_info_district as district,bfapt.basic_info_upazila as upazila,date(bfapt.basic_info_date) as action_date from core.bahis_farm_assessment_p2_table bfapt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Avian Influenza Investigation'as form_name,baiipt.basic_info_division as division,baiipt.basic_info_district as district,baiipt.basic_info_upazila as upazila,date(baiipt.basic_info_date) as action_date from core.bahis_avian_influenza_investigate_p2_table baiipt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Avian Influenza Sample'as form_name,baispt.basic_info_division as division,baispt.basic_info_district as district,baispt.basic_info_upazila as upazila,date(baispt.basic_info_date) as action_date from core.bahis_avian_influenza_sample_p2_table baispt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Disease Investigation'as form_name,bdipt.basic_info_division as division,bdipt.basic_info_district as district,bdipt.basic_info_upazila as upazila,date(bdipt.basic_info_date) as action_date from core.bahis_disease_investigation_p2_table bdipt, dx where instanceid::int8 in (dx.id)
    union all
    select 'Participatory Livestock Assessment'as form_name,bplat.basic_info_division as division,bplat.basic_info_district as district,bplat.basic_info_upazila as upazila,date(bplat.basic_info_date) as action_date from core.bahis_participatory_livestock_assessment_table bplat, dx where instanceid::int8 in (dx.id))
    select gl.div_name as division,gl.dist_name as district,gl.upz_name as upazila,count(*) filter(where datax.form_name = 'Patients Registry') as pr_cnt,
    count(*) filter(where datax.form_name = 'Farm Assessment Monitoring') as fam_cnt,
    count(*) filter(where datax.form_name = 'Avian Influenza Investigation') as aii_cnt,
    count(*) filter(where datax.form_name = 'Avian Influenza Sample') as ais_cnt,
    count(*) filter(where datax.form_name = 'Disease Investigation') as di_cnt,
    count(*) filter(where datax.form_name = 'Participatory Livestock Assessment') as pla_cnt
    from gl
    left join datax
    on datax.division = gl.div_code
    and datax.district = gl.dist_code
    and datax.upazila = gl.upz_code
    group by gl.div_name,gl.dist_name,gl.upz_name
    """ % (division_id,district_id,upazila_id)

    form_summary_data = __db_fetch_values_dict(select_query)
    all_geo_id.append(1)
    return render(request, 'reportsmodule/reports/form_summary_report.html',
                  {'get_division_list': get_division_list, 'col_name': col_name, 'form_summary_data': form_summary_data, 'all_geo_id': all_geo_id,
                   'division_id': division_id, 'district_id': district_id, 'upazila_id': upazila_id,
                   'loc_type': loc_type, 'geoid': geoid
                   })



def handle_none(dictionary):
    for key, value in dictionary.items():
        if value is None:
            dictionary[key] = " "
    return dictionary


def handle_nan(dictionary):
    for key, value in dictionary.items():
        if value == "nan":
            dictionary[key] = " "
    return dictionary


def set_nan_to_space(var):
    if var == "nan":
        var = " "
    return var
