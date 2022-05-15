from django.conf.urls import patterns, include, url
from django.contrib import admin
from onadata.apps.usermodule import views,views_project,views_api

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^register/$', views.register, name='register'),
    url(r'^error/$', views.error_page, name='error_page'),
    url(r'^add-organization/$', views.add_organization, name='add_organization'),
    url(r'^organizations/$', views.organization_index, name='organization_index'),
    url(r'^edit-organization/(?P<org_id>\d+)/$', views.edit_organization, name='edit_organization'),
    # url(r'^organization-mapping/$', views.organization_mapping, name='organization_mapping'),
    url(r'^organization-delete/(?P<org_id>\d+)/$', views.delete_organization, name='organization_delete'),
    # url(r'^organization-delete-mapping/(?P<org_id>\d+)/$', views.delete_organization_mapping, name='delete_organization_mapping'),
    url(r'^edit/(?P<user_id>\d+)/$', views.edit_profile, name='edit_profile'),
    url(r'^delete/(?P<user_id>\d+)/$', views.delete_user, name='delete_user'),
    url(r'^reset-password/(?P<reset_user_id>\d+)/$', views.reset_password, name='reset_password'),
    url(r'^login/$', views.user_login, name='login'),
    url(r'^logout/$', views.user_logout, name='logout'),
    url(r'^change-password/$', views.change_password, name='change_password'),
    url(r'^locked-users/$', views.locked_users, name='locked_users'),
    url(r'^unlock/$', views.unlock, name='unlock'),
    url(r'^organization-access-list/$', views.organization_access_list, name='organization_access_list'),
    # menu item urls 
    url(r'^add-menu/$', views.add_menu, name='add_menu'),
    url(r'^menu-list/$', views.menu_index, name='menu_index'),
    url(r'^edit-menu/(?P<menu_id>\d+)/$', views.edit_menu, name='edit_menu'),
    url(r'^delete-menu/(?P<menu_id>\d+)/$', views.delete_menu, name='delete_menu'),

    # role items urls
    url(r'^add-role/$', views.add_role, name='add_role'),
    url(r'^roles-list/$', views.roles_index, name='roles_index'),
    url(r'^edit-role/(?P<role_id>\d+)/$', views.edit_role, name='edit_role'),
    url(r'^delete-role/(?P<role_id>\d+)/$', views.delete_role, name='delete_role'),
    
    # role menu map urls
    url(r'^add-role-menu-map/$', views.add_role_menu_map, name='add_role_menu_map'),
    url(r'^role-menu-map-list/$', views.role_menu_map_index, name='role_menu_map_index'),
    url(r'^edit-role-menu-map/(?P<item_id>\d+)/$', views.edit_role_menu_map, name='edit_role_menu_map'),
    url(r'^delete-role-menu-map/(?P<item_id>\d+)/$', views.delete_role_menu_map, name='delete_role_menu_map'),

    url(r"^(?P<username>\w+)/get/sent_datalist/$", views.sent_datalist, name='sent_datalist'),
    
    # user role map urls
    url(r'^organization-roles/$', views.organization_roles, name='organization_roles'),
    url(r'^user-role-map/(?P<org_id>\d+)/$', views.user_role_map, name='user_role_map'),
    url(r'^adjust-user-role-map/(?P<org_id>\d+)/$', views.adjust_user_role_map, name='adjust_user_role_map'),

    #new interface of user role map
    url(r'^user_role_mapping/$', views.user_role_mapping, name='user_role_mapping'),
    url(r'^getUserRoles/$', views.getUserRoles, name='getUserRoles'),

    #Branch management urls
    url(r'^branch-list/$', views.branch_list, name='branch_list'),
    url(r'^add_branch_form/$', views.add_branch_form, name='add_branch_form'),
    url(r'^edit_branch_form/(?P<branch_id>\d+)/$', views.edit_branch_form, name='edit_branch_form'),
    url(r'^update_branch_form/$', views.update_branch_form, name='update_branch_form'),
    url(r'^insert_branch_form/$', views.insert_branch_form, name='insert_branch_form'),
    url(r'^delete_branch_form/(?P<branch_id>\d+)/$', views.delete_branch_form, name='delete_branch_form'),
    url(r'^get_branch/$', views.get_branch, name='get_branch'),
    url(r'^get_user_branch/$', views.get_user_branch, name='get_user_branch'),

    # Mjivita Purpose
    url(r'^get_supervisor/$', views.get_supervisor, name='get_supervisor'),
    url(r'^acarea-list/$', views.acarea_list, name='acarea_list'),
    url(r'^add-acarea/$', views.add_acarea, name='add_acarea'),
    url(r'^edit-acarea/(?P<id>\d+)/$', views.edit_acarea, name='edit_acarea'),
    url(r'^delete_acarea/(?P<id>\d+)/$', views.delete_acarea, name='delete_acarea'),

    url(r'^tlpin-list/$', views.tlpin_list, name='tlpin_list'),
    url(r'^add-tlpin/$', views.add_tlpin, name='add_tlpin'),
    url(r'^edit-tlpin/(?P<id>\d+)/$', views.edit_tlpin, name='edit_tlpin'),
    url(r'^delete_tlpin/(?P<id>\d+)/$', views.delete_tlpin, name='delete_tlpin'),

    url(r'^sector-list/$', views.sector_list, name='sector_list'),
    url(r'^add-sector/$', views.add_sector, name='add_sector'),
    url(r'^edit-sector/(?P<id>\d+)/$', views.edit_sector, name='edit_sector'),
    url(r'^delete_sector/(?P<id>\d+)/$', views.delete_sector, name='delete_sector'),
    url(r'^map-user/(?P<user_id>\d+)/(?P<role_id>\d+)/$', views.map_user, name='map_user'),


    url(r'^user-viewable-projects/$', views_project.user_viewable_projects, name='user_viewable_projects'),
    url(r'^adjust-user-project-map/(?P<id_string>[^/]+)/(?P<form_owner_user>[^/]+)$', views_project.adjust_user_project_map, name='adjust_user_project_map'),

    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/role_form_map$',views.startpage,name='role_form_map'),
    # new project view url
    url(r'^(?P<username>\w+)/projects-views/(?P<id_string>[^/]+)/$', views_project.custom_project_window, name='custom_project_window'),
    url(r'^(?P<username>\w+)/projects-views/(?P<id_string>[^/]+)/generate_report/$', views_project.generate_pivot, name='generate_pivot'),

    # url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/view-data",
    #     'onadata.apps.viewer.views.data_view'),

    #chart related ajax query url

    url(r'^upload/csv/$', views.upload_user_csv, name='upload_csv'),
    url(r'^chartview/$', views_project.chart_view, name='chart_view'),


    #Mobile API
    url(r'^get_hh_list/$', views_api.get_hh_list, name='get_hh_list'),
    url(r'^get_schedule_list/$', views_api.get_schedule_list, name='get_schedule_list'),
    #url(r'^get_beneficiary/$', views_api.get_beneficiary, name='get_beneficiary'),
    url(r'^get_beneficiary_info/$', views_api.get_beneficiary_info, name='get_beneficiary_info'),

    url(r'^get_hh_member/$', views_api.get_hh_member, name='get_hh_member'),
    url(r'^get_user_schedule/$', views_api.get_user_schedule, name='get_user_schedule'),
    url(r'^nwvm_previous_uid/$', views_api.nwvm_previous_uid, name='nwvm_previous_uid'),
    url(r'^get_uid/$', views_api.get_uid, name='get_uid'),
    url(r'^get_user_data/$', views_api.get_user_data, name='get_user_data'),
    url(r'^get_pregnant_woman_list/$', views_api.get_pregnant_woman_list, name='get_pregnant_woman_list'),
    url(r'^check_hh_existed/$', views_api.check_hh_existed, name='check_hh_existed'),
    url(r'^generate_sche_bnt_sms/$', views_api.generate_sche_bnt_sms, name='generate_sche_bnt_sms'),
    #url(r'^parse_json/$', views_api.parse_json, name='parse_json'),
    #url(r'^get_user_schedule_test/$', views_api.get_user_schedule_test, name='get_user_schedule_test'),
    #url(r'^get_schedule_list_test/$', views_api.get_schedule_list_test, name='get_schedule_list_test'),


    #########################
    ############################
    ###########################
    url(r'^getDistricts/$', views.getDistricts, name='getDistricts'),
    url(r'^getUpazilas/$', views.getUpazilas, name='getUpazilas'),


    url(r'^geo_def_data/$', views.geo_def_list, name='geo_def_data'),
    url(r'^geo_definition/$', views.form_def, name='geo_definition'),
    url(r'^edit_form_definition/(?P<form_definition_id>\d+)/$', views.edit_form_definition, name='edit_form_definition'),
    url(r'^update_form_definition/$', views.update_form_definition, name='update_form_definition'),
    url(r'^delete_form_definition/(?P<form_definition_id>\d+)/$', views.delete_form_definition, name='delete_form_definition'),
    url(r'^geo_list/$', views.geo_list, name='geo_list'),
    url(r'^geo_form/$', views.form, name='geo_form'),
    url(r'^form_drop/$', views.form_drop, name='form_drop'),
    url(r'^tree/$', views.tree, name='tre'),
    url(r'^filtering/$', views.filtering, name='filterin'),
    url(r'^edit_form/(?P<form_id>\d+)/$', views.edit_form, name='edit_form'),
    url(r'^update_form/$', views.update_form, name='update_form'),
    url(r'^delete_form/(?P<form_id>\d+)/$', views.delete_form, name='delete_form'),
    url(r'^check_for_delete/$', views.check_for_delete, name='check_for_delete'),
    #api
   url(r"^get/user_info/$", views_api.login_verify, name='user_verify'),
   url(r'^mobile_login_new/$', views_api.mobile_login, name='mobile_login'),

                       # Catchment Area related URL
                       url(r'^add_children/$', views.add_children, name='add_children'),
                       url(r'^branch_catchment_tree/(?P<branch_id>\d+)/$', views.branch_catchment_tree_test,
                           name='branch_catchment_tree_test'),
                       url(r'^branch_catchment_data_insert/$', views.branch_catchment_data_insert,
                           name='org_catchment_data_insert'),

    )
