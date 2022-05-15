# -*- coding: utf-8 -*-
"""report module routing file

This module contains the all routing urls used in farmmodule apps

"""
from django.conf.urls import patterns, url
from . import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name='index'),
    url(r'^getDistrict_jq/$', views.getDistrict_jq,
        name='getDistrict_jq'),
    url(r'^getUpazilas_jq/$', views.getUpazilas_jq,
        name='getUpazilas_jq'),
    url(r'^getUnions_jq/$', views.getUnions_jq, name='getUnions_jq'),
    url(r'^get_species_list_by_ltype/$', views.get_species_list_by_ltype, name='get_species_list_by_ltype'),
    url(r'^disease_stat_chart/$', views.disease_stat_chart,
        name='disease_stat_chart'),
    url(r'^disease_stat_chart_prior/$', views.disease_stat_chart_prior,
        name='disease_stat_chart_prior'),
    url(r'^disease_stat_chart_map/$', views.disease_stat_chart_map,
        name='disease_stat_chart_map'),
    url(r'^biosecurity_reports/$', views.biosecurity_reports,
        name='biosecurity_reports'),
    url(r'^aware_cat_reports/$', views.aware_cat_reports, name='aware_cat_reports'),
    url(r'^patient_aware_cat_reports/$', views.patient_aware_cat_reports, name='patient_aware_cat_reports'),
    url(r'^sick_treated_report/$', views.sick_treated_report, name='sick_treated_report'),
    url(r'^submission_count_list/$', views.submission_count_list,
        name='submission_count_list'),
    url(r'^form_summary_report/$', views.form_summary_report,
        name='form_summary_report'),
)
