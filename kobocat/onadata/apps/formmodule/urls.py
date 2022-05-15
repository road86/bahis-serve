# -*- coding: utf-8 -*-
"""Farm module routing file

This module contains the all routing urls used in farmmodule apps

"""
from django.conf.urls import patterns, url
from onadata.apps.formmodule import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name='index'),
    url(r'^get-form/(?P<form_id>[^/]+)/$', views.get_form, name='get_form'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/instance/edit-data/(?P<data_id>"
        "\d+)$", views.edit_data, name='edit_data'),
    # ---------- API -----------

)
