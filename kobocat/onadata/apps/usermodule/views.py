import time

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

import decimal
# Create your views here.
from django.db import (IntegrityError,transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.usermodule.forms import UserForm, UserProfileForm, ChangePasswordForm, UserEditForm, OrganizationForm, ResetPasswordForm
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin, Organizations,UserBranch

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

import csv
EXIST_BRANCH = settings.IS_EXIST_BRANCH

def admin_check(user):
    current_user = UserModuleProfile.objects.filter(user=user)
    if current_user:
        current_user = current_user[0]
    else:
        return True    
    return current_user.admin


def index(request):
    q = """
        select
            auth_user.id,
            username,
            email,
            (
            select
                organization
            from
                core.usermodule_organizations
            where
                id = organisation_name_id) as organization,
            usermodule_organizationrole.role
        from
            instance.auth_user
        left join core.usermodule_usermoduleprofile on
            usermodule_usermoduleprofile.user_id = auth_user.id
        left join core.usermodule_userrolemap on
            usermodule_userrolemap.user_id = usermodule_usermoduleprofile.user_id
        left join core.usermodule_organizationrole on
            usermodule_organizationrole.id = usermodule_userrolemap.role_id
        where
            usermodule_usermoduleprofile.organisation_name_id in (with recursive
         rec_d (id, organization) as (
            select
                uo.id, uo.organization
            from
                core.usermodule_organizations uo
            where
                id = (
                select
                    organisation_name_id
                from
                    core.usermodule_usermoduleprofile
                where
                    user_id = %s)
        union all
            select
                uo2.id, uo2.organization
            from
                rec_d, core.usermodule_organizations uo2
            where
                uo2.parent_organization_id = rec_d.id ),
         rec_a (id, organization, parent_organization_id) as (
            select
                uo.id, uo.organization, uo.parent_organization_id
            from
                core.usermodule_organizations uo
            where
                id = (
                select
                    organisation_name_id
                from
                    core.usermodule_usermoduleprofile
                where
                    user_id = %s)
        union all
            select
                uo2.id, uo2.organization, uo2.parent_organization_id
            from
                rec_a, core.usermodule_organizations uo2
            where
                uo2.id = rec_a.parent_organization_id )
            select
                id
            from
                rec_a
        union
            select
                id
            from
                rec_d)
        """ % (request.user.id, request.user.id)
    users = __db_fetch_values_dict(q)
    #print users
    template = loader.get_template('usermodule/index.html')
    context = RequestContext(request, {
        'users': users
    })

    return HttpResponse(template.render(context))


def get_organization_by_user(user):
    org_id_list = []
    current_user = UserModuleProfile.objects.filter(user_id=user.id)
    if current_user:
        current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name,[])
        org_id_list = [org.pk for org in all_organizations]
    return org_id_list


# must pass an empty organization_list initally otherwise produces bug.
def get_recursive_organization_children(organization,organization_list=[]):
    organization_list.append(organization)
    observables = Organizations.objects.filter(parent_organization = organization)
    for org in observables:
        if org not in organization_list:
            organization_list = list((set(get_recursive_organization_children(org,organization_list))))
    return list(set(organization_list))



@login_required
def organization_index(request):
    context = RequestContext(request)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name, [])
        all_organizations.remove(current_user.organisation_name)
    message = ""
    alert = ""
    org_del_message = request.GET.get('org_del_message')
    org_del_message2 = request.GET.get('org_del_message2')
    return render(request,
        'usermodule/organization_list.html',
        {'all_organizations': all_organizations, "message": message, "alert": alert,
         'org_del_message': org_del_message, 'org_del_message2': org_del_message2,
         })


@login_required
def add_organization(request):
    # Like before, get the request's context.
    context = RequestContext(request)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=all_organizations,
                                                                                     empty_label="Select a Organization",
                                                                                     required=False)
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name, [])
        org_id_list = [org.pk for org in all_organizations]
        # org_id_list = list(set(org_id_list))
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(
            queryset=Organizations.objects.filter(pk__in=org_id_list), empty_label="Select a Parent Organization")
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_organization = False
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        organization_form = OrganizationForm(data=request.POST)
        if organization_form.is_valid():
            organization_form.save()
            is_added_organization = True
            messages.success(request,
                             '<i class="fa fa-check-circle"></i> New Organization has been added successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/organizations/')
        else:
            #print organization_form.errors
            return render(request,
                'usermodule/add_organization.html',
                {'all_organizations': all_organizations, 'organization_form': organization_form,
                 'is_added_organization': is_added_organization})
    else:
        organization_form = OrganizationForm()
        # Render the template depending on the context.
        return render(request,
            'usermodule/add_organization.html',
            {'all_organizations': all_organizations, 'organization_form': organization_form,
             'is_added_organization': is_added_organization})


@login_required
def edit_organization(request, org_id):
    context = RequestContext(request)
    edited = False
    organization = get_object_or_404(Organizations, id=org_id)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.filter(~Q(id=organization.pk))
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=all_organizations,
                                                                                     empty_label="Select a Organization",
                                                                                     required=False)
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name, [])
        org_id_list = [org.pk for org in all_organizations]
        org_id_list.remove(organization.pk)
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(
            queryset=Organizations.objects.filter(pk__in=org_id_list), empty_label="Select a Parent Organization")

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        organization_form = OrganizationForm(data=request.POST, instance=organization)
        if organization_form.is_valid():
            print organization_form
            organization_form.save()
            edited = True
            messages.success(request,
                             '<i class="fa fa-check-circle"></i> Organization has been updated successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/organizations/')
        else:
            print organization_form.errors
            return render(request,
                'usermodule/edit_organization.html',
                {'org_id': org_id, 'organization_form': organization_form, 'edited': edited})
            # Not a HTTP POST, so we render our form using two ModelForm instances.
            # These forms will be blank, ready for user input.
    else:
        organization_form = OrganizationForm(instance=organization)
    return render(request,
        'usermodule/edit_organization.html',
        {'org_id': org_id, 'organization_form': organization_form, 'edited': edited})


@login_required
def delete_organization(request, org_id):
    context = RequestContext(request)
    org = Organizations.objects.get(pk=org_id)
    try:
        org.delete()
        messages.success(request,
                         '<i class="fa fa-check-circle"></i> Organization has been deleted successfully!',
                         extra_tags='alert-success crop-both-side')
    except ProtectedError:
        org_del_message = """User(s) are assigned to this organization,
        please delete those users or assign them a different organization
        before deleting this organization"""

        org_del_message2 = """Or, This Organization may be parent of
        one or more organization(s), Change their parent to some other organization."""

        return HttpResponseRedirect(
            '/usermodule/organizations/?org_del_message=' + org_del_message + "&org_del_message2=" + org_del_message2)
    return HttpResponseRedirect('/usermodule/organizations/')


@login_required
def organization_access_list(request):
    param_user_id = request.POST['id']
    response_data = []
    observer = get_object_or_404(Organizations, id=param_user_id)
    all_organizations = get_recursive_organization_children(observer,[])
    for org in all_organizations:
        data = {}
        data["observer"] = observer.organization
        data["observable"] = org.organization
        response_data.append(data)
    return HttpResponse(json.dumps(response_data), content_type="application/json")





@login_required
def delete_user(request, user_id):
    context = RequestContext(request)
    user = User.objects.get(pk=user_id)
    try:
        # deletes the user from both user and rango
        user.delete()
        messages.success(request, '<i class="fa fa-check-circle"></i> This user has been deleted successfully!',
                         extra_tags='alert-success crop-both-side')

    except:
        print "I am unable to delete the user"
        messages.error(request, '<i class="fa fa-exclamation-triangle"></i> This user Cannot be deleted!',
                       extra_tags='alert-danger crop-both-side')

    return HttpResponseRedirect('/usermodule/')


def change_password(request):
    context = RequestContext(request)
    if request.GET.get('userid'):
        edit_user = get_object_or_404(User, pk = request.GET.get('userid')) 
        logged_in_user = edit_user.username
        change_password_form = ChangePasswordForm(logged_in_user=logged_in_user)
    else:
        change_password_form = ChangePasswordForm()
    # change_password_form = ChangePasswordForm()
    # Take the user back to the homepage.
    if request.method == 'POST':
        # expiry_months_delta: password change after how many months
        expiry_months_delta = 3
        # Date representing the next expiry date
        next_expiry_date = (datetime.today() + timedelta(expiry_months_delta*365/12))

        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        change_password_form = ChangePasswordForm(data=request.POST)
        username = request.POST['username']
        old_password = request.POST['old_password']
        new_password = request.POST['new_password']
        current_user = authenticate(username=username, password=old_password)
        if change_password_form.is_valid() and current_user is not None:
            """ current user is authenticated and also new password
             is available so change the password and redirect to
             home page with notification to user """
            encrypted_password = make_password(new_password)
            current_user.password = encrypted_password
            current_user.save()

            passwordHistory = UserPasswordHistory(user_id = current_user.id,date = datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            profile = get_object_or_404(UserModuleProfile, user_id=current_user.id)
            profile.expired = next_expiry_date
            profile.save()
            login(request,current_user)
            return HttpResponseRedirect('/usermodule/')
            # else:
                #     return HttpResponse('changed your own password buddy')
                # return HttpResponse( (datetime.now()+ timedelta(days=30)) )
        else:
            return render_to_response(
                    'usermodule/change_password.html',
                    {'change_password_form': change_password_form,'invalid':True},
                    context)

    return render_to_response(
                'usermodule/change_password.html',
                {'change_password_form': change_password_form},
                context)

@login_required
def reset_password(request,reset_user_id):
    context = RequestContext(request)
    reset_password_form = ResetPasswordForm()
    reset_user = get_object_or_404(User, pk=reset_user_id)
    reset_user_profile = get_object_or_404(UserModuleProfile,user=reset_user)
    if request.method == 'POST':
        # expiry_months_delta: password change after how many months
        expiry_months_delta = 3
        # Date representing the next expiry date
        next_expiry_date = (datetime.today() + timedelta(expiry_months_delta*365/12))

        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        reset_password_form = ResetPasswordForm(data=request.POST)
        
        if reset_password_form.is_valid() and reset_user is not None:
            """ current user is authenticated and also new password
             is available so change the password and redirect to
             home page with notification to user """
            encrypted_password = make_password(request.POST['new_password'])
            reset_user.password = encrypted_password
            reset_user.save()

            passwordHistory = UserPasswordHistory(user_id = reset_user.id,date = datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            reset_user_profile.expired = next_expiry_date
            reset_user_profile.save()
            messages.success(request, '<i class="fa fa-check-circle"></i> Your password has been updated successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')
        else:
            return render(request,
                    'usermodule/reset_password.html',
                    {'reset_user':reset_user,'reset_password_form': reset_password_form,'id':reset_user_id,'invalid':True})

    return render(request,
                'usermodule/reset_password.html',
                {'reset_password_form': reset_password_form,
                'reset_user':reset_user,'id':reset_user_id,
                })


def user_login(request):
    # Like before, obtain the context for the user's request.
    context = RequestContext(request)
    logger = logging.getLogger(__name__)
    if request.GET.get('next'):
        print request.GET.get('next')
        redirect_url = request.GET.get('next')
    else:
        redirect_url = '/'
    # If the request is a HTTP POST, try to pull out the relevant information.
    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        username = request.POST['username']
        password = request.POST['password']

        # Use Django's machinery to attempt to see if the username/password
        # combination is valid - a User object is returned if it is.
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
                return HttpResponse("Your account is locked for multiple invalid logins, contact admin to unlock")

            # Is the account active? It could have been disabled.
            if user.is_active:
                if hasattr(user, 'usermoduleprofile'):
                    current_user = user.usermoduleprofile
                    #if date.today() > current_user.expired.date():
                        #return HttpResponseRedirect('/usermodule/change-password')
                login(request, user)
                UserFailedLogin.objects.filter(user_id=user.id).delete()
                return HttpResponseRedirect(redirect_url)
            else:
                # An inactive account was used - no logging in!
                # return HttpResponse("Your User account is disabled.")
                return error_page(request,"Your User account is disabled")
        else:
            # Bad login details were provided. So we c an't log the user in.
            # try:
            #     attempted_user_id = User.objects.get(username=username).pk
            # except User.DoesNotExist:
            #     return HttpResponse("Invalid login details supplied when login attempted.")
            # UserFailedLogin(user_id = attempted_user_id).save()
            # print "Invalid login details: {0}, {1}".format(username, password)
            # return HttpResponse("Invalid login details supplied.")
            #return error_page(request,"Invalid login details supplied")
            return render(request, 'usermodule/login.html',
                          {'data': "Invalid login details supplied", 'redirect_url': redirect_url})

    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.
    else:
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render(request,'usermodule/login.html', {'redirect_url':redirect_url})


@login_required
def locked_users(request):
    # Since we know the user is logged in, we can now just log them out.
    current_user = request.user
    users = []
    message = ''
    max_failed_login_attempts = 5

    user = UserModuleProfile.objects.filter(user_id=current_user.id)
    admin = False
    if user:
        admin = user[0].admin

    if current_user.is_superuser or admin:
        failed_logins = UserFailedLogin.objects.all().values('user_id').annotate(total=Count('user_id')).order_by('user_id')
        for f_login in failed_logins:
            if f_login['total'] > max_failed_login_attempts:
                user = UserModuleProfile.objects.filter(user_id=f_login['user_id'])[0]
                users.append(user)
    else:
        return HttpResponseRedirect("/usermodule/")
    if not users:
        message = "All the user accounts are unlocked"

    # Take the user back to the homepage.
    template = loader.get_template('usermodule/locked_users.html')
    context = RequestContext(request, {
            'users': users,
            'message':message
        })
    return HttpResponse(template.render(context))


@login_required
def unlock(request):
    param_user_id = request.POST['id']
    current_user = request.user
    response_data = {}
    
    user = UserModuleProfile.objects.filter(user_id=current_user.id)
    admin = False
    if user:
        admin = user[0].admin

    if current_user.is_superuser or admin:
        UserFailedLogin.objects.filter(user_id=param_user_id).delete()
        response_data['message'] = 'User unlocked'
    else:
        response_data['message'] = 'You are not authorized to unlock'

    return HttpResponse(json.dumps(response_data), content_type="application/json")


@login_required
def user_logout(request):
    # Since we know the user is logged in, we can now just log them out.
    logout(request)
    # Take the user back to the homepage.
    return HttpResponseRedirect('/login/')


# =======================================================================================
@login_required
def add_menu(request):
    context = RequestContext(request)
    all_menu = MenuItem.objects.all()
    if EXIST_BRANCH == False:
        all_menu = all_menu.exclude(url__exact='/usermodule/branch-list/')
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_menu = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        menu_form = MenuForm(data=request.POST)
        # If the two forms are valid...
        if menu_form.is_valid():
            menu =menu_form.save()
            menu.save()
            is_added_menu = True
        else:
            print menu_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
        return HttpResponseRedirect('/usermodule/menu-list/')
    else:
        menu_form = MenuForm()
    
    # Render the template depending on the context.
        return render(request,
            'usermodule/add_menu.html',
            {'all_menu':all_menu,'menu_form': menu_form,
            'is_added_menu': is_added_menu})


@login_required
def menu_index(request):
    context = RequestContext(request)
    all_menu = MenuItem.objects.all().order_by("sort_order")
    if EXIST_BRANCH == False:
        all_menu = all_menu.exclude(url__exact='/usermodule/branch-list/')

    return render(request,
            'usermodule/menu_list.html',
            {'all_menu':all_menu})


@login_required
def edit_menu(request,menu_id):
    context = RequestContext(request)
    edited = False
    menu = get_object_or_404(MenuItem, id=menu_id)
    
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        menu_form = MenuForm(data=request.POST,instance=menu)
        
        # If the two forms are valid...
        if menu_form.is_valid():
            edited_user = menu_form.save(commit=False);
            edited_user.save()
            edited = True
            return HttpResponseRedirect('/usermodule/menu-list')
        else:
            print menu_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        menu_form = MenuForm(instance=menu)

    return render(request,
            'usermodule/edit_menu.html',
            {'id':menu_id, 'menu_form': menu_form,
            'edited': edited})


@login_required
def delete_menu(request,menu_id):
    context = RequestContext(request)
    menu = MenuItem.objects.get(pk = menu_id)
    # deletes the user from both user and rango
    menu.delete()
    return HttpResponseRedirect('/usermodule/menu-list')


# =========================================================
# Roles based on Organization CRUD
@login_required
def add_role(request):
    context = RequestContext(request)
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_role = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        role_form = OrganizationRoleForm(data=request.POST)
        print role_form
        # If the two forms are valid...
        if role_form.is_valid():
            role_form.save()
            new_role_id = __db_fetch_single_value("""
            select max(id) from core.usermodule_organizationrole
            """)
            main_module_id = __db_fetch_single_value("""
            select id from core.module_definition md where node_parent is null order by id asc limit 1
            """)
            __db_commit_query("""
            insert into core.modulerolemap (role_id,module_id,created_at,created_by) values (%s,%s,now(),%s)
            """ % (new_role_id,main_module_id,request.user.id))
            is_added_role = True
        else:
            print role_form.errors
            return render(request,
                          'usermodule/add_role.html',
                          {'role_form': role_form,
                           'is_added_role': is_added_role})

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
        messages.success(request, '<i class="fa fa-check-circle"></i> New role has been added successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/roles-list/')
    else:
        if request.user.is_superuser:
            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.all(),empty_label="Select a Organization")
            OrganizationRoleForm.base_fields['parent_role'] = forms.ModelChoiceField(
                queryset=OrganizationRole.objects.all(), empty_label="Select a Parent role")
            role_form = OrganizationRoleForm()
        else:
            org_id_list = get_organization_by_user(request.user)
            #OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list),empty_label="Select a Organization")
            #OrganizationRoleForm.base_fields['parent_role'] = forms.ModelChoiceField(
                #queryset=OrganizationRole.objects.all(), empty_label="Select a Parent role")

            role_form = OrganizationRoleForm()
    # Render the template depending on the context.
        return render(request,
            'usermodule/add_role.html',
            {'role_form': role_form,
            'is_added_role': is_added_role})


@login_required
def roles_index(request):
    context = RequestContext(request)
    # filter orgs based on logged in user
    if request.user.is_superuser:
        all_roles = OrganizationRole.objects.all().order_by("organization")
    else:
        user = get_object_or_404(UserModuleProfile, user=request.user)
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name, [])
        org_id_list = [org.pk for org in all_organizations]
        all_roles = OrganizationRole.objects.filter(organization__in= org_id_list)
    return render(request,
            'usermodule/roles_list.html',
            {'all_roles':all_roles})


@login_required
def edit_role(request, role_id):
    context = RequestContext(request)
    edited = False
    role = get_object_or_404(OrganizationRole, id=role_id)
    if request.method == 'POST':
        role_form = OrganizationRoleForm(data=request.POST,instance=role)
        if role_form.is_valid():
            role_form.save()
            edited = True
            messages.success(request, '<i class="fa fa-check-circle"></i> This role has been edited successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/roles-list')
        else:
            print role_form.errors
    else:
        if request.user.is_superuser:
            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.all(),empty_label="Select a Organization")
            OrganizationRoleForm.base_fields['parent_role'] = forms.ModelChoiceField(
                queryset=OrganizationRole.objects.all(), empty_label="Select a Parent role")
        else:
            org_id_list = get_organization_by_user(request.user)
            #OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list),empty_label="Select a Organization")
            #OrganizationRoleForm.base_fields['parent_role'] = forms.ModelChoiceField(
               # queryset=OrganizationRole.objects.all(), empty_label="Select a Parent role")
        role_form = OrganizationRoleForm(instance=role,initial = {'organization': role.organization,'role': role.role,'parent_role':role.parent_role })
        # role_form = OrganizationRoleForm(instance=role)
    return render(request,
            'usermodule/edit_role.html',
            {'id':role_id, 'role_form': role_form,
            'edited': edited})


@login_required
def delete_role(request,role_id):
    context = RequestContext(request)
    role = OrganizationRole.objects.get(pk = role_id)
    # deletes the user from both user and rango
    role.delete()
    messages.success(request, '<i class="fa fa-check-circle"></i> This role has been deleted successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponseRedirect('/usermodule/roles-list')


# =========================================================
@login_required
def role_menu_map_index(request):
    context = RequestContext(request)
    insertList = []
    menu_dict = {}
    # filter orgs based on logged in user
    if request.method == 'POST':
        new_menu = request.POST.getlist('menu_id')
        print new_menu
        for val in new_menu:
            splitVal = val.split("__")
            instance = MenuRoleMap(role_id=splitVal[0], menu_id=splitVal[1])
            insertList.append(instance)

        MenuRoleMap.objects.all().delete()
        MenuRoleMap.objects.bulk_create(insertList)
        messages.success(request, '<i class="fa fa-check-circle"></i> Access List has been updated successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/role-menu-map-list/')
    else:
        if request.user.is_superuser:
            menu_items = MenuItem.objects.all()
            if EXIST_BRANCH == False:
                menu_items = menu_items.exclude(url__exact='/usermodule/branch-list/')
            roles = OrganizationRole.objects.all()
            for role in roles:
                org_menu_list = MenuRoleMap.objects.filter(role=role.id).values_list('menu_id', flat=True)
                menu_dict[role.id] = org_menu_list
        else:
            menu_items = MenuItem.objects.all()
            if EXIST_BRANCH == False:
                menu_items = menu_items.exclude(url__exact='/usermodule/branch-list/')
            current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
            if current_user:
                current_user = current_user[0]
            all_organizations = get_recursive_organization_children(current_user.organisation_name, [])
            org_id_list = [org.pk for org in all_organizations]
            roles = OrganizationRole.objects.filter(organization__in= org_id_list)
            for role in roles:
                org_menu_list = MenuRoleMap.objects.filter(role = role.id).values_list('menu_id', flat=True)
                menu_dict[role.id] = org_menu_list

        return render(request,
            'usermodule/roles_menu_map_list.html',
            {'menu_items':menu_items, 'menu_dict':menu_dict,'roles':roles})


# Roles based on Organization CRUD
@login_required
def add_role_menu_map(request):
    context = RequestContext(request)
    is_added_role = False
    if request.method == 'POST':
        role_form = RoleMenuMapForm(data=request.POST)
        if role_form.is_valid():
            role_form.save()
            is_added_role = True
            messages.success(request, '<i class="fa fa-check-circle"></i> New access has been added successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/role-menu-map-list/')
        else:
            print role_form.errors
        return HttpResponseRedirect('/usermodule/role-menu-map-list/')
    else:
        if request.user.is_superuser:
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.all().order_by("organization"),empty_label="Select a Organization Role")
            
        else:
            org_id_list = get_organization_by_user(request.user)
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.filter(organization__in=org_id_list).order_by("organization"),empty_label="Select a Organization Role")
        role_form = RoleMenuMapForm()
        return render(request,
            'usermodule/add_role_menu_map.html',
            {'role_form': role_form,
            'is_added_role': is_added_role})


@login_required
def edit_role_menu_map(request, item_id):
    context = RequestContext(request)
    edited = False
    role_menu_map = get_object_or_404(MenuRoleMap, id=item_id)
    if request.method == 'POST':
        role_form = RoleMenuMapForm(data=request.POST,instance=role_menu_map)
        if role_form.is_valid():
            role_form.save()
            edited = True
            messages.success(request, '<i class="fa fa-check-circle"></i> This access has been edit successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/role-menu-map-list/')
        else:
            print role_form.errors
    else:
        if request.user.is_superuser:
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.all(),empty_label="Select a Organization Role")
        else:
            org_id_list = get_organization_by_user(request.user)
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.filter(organization__in=org_id_list),empty_label="Select a Organization Role")
        role_form = RoleMenuMapForm(instance=role_menu_map,initial = {'role': role_menu_map.role,'menu': role_menu_map.menu })
    return render(request,
            'usermodule/edit_role_menu_map.html',
            {'id':item_id, 'role_form': role_form,
            'edited': edited})


@login_required
def delete_role_menu_map(request, item_id):
    context = RequestContext(request)
    del_map_item = MenuRoleMap.objects.get(pk = item_id)
    del_map_item.delete()
    messages.success(request, '<i class="fa fa-check-circle"></i> This access has been deleted successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponseRedirect('/usermodule/role-menu-map-list')


# =========================================================
@login_required
def organization_roles(request):
    context = RequestContext(request)
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
    else:    
        org_id_list = get_organization_by_user(request.user)
        all_organizations = Organizations.objects.filter(pk__in=org_id_list)
    message = None
    if len(all_organizations) == 0:    
        message = "You do not have any Organizations under your supervision."
    return render(request,
            'usermodule/organization_roles.html',
            {'all_organizations':all_organizations,"message":message})


@login_required
def user_role_map(request, org_id=None):
    context = RequestContext(request)
    edited = False
    roles = OrganizationRole.objects.filter(organization=org_id)
    users = UserModuleProfile.objects.filter(organisation_name=org_id)
    message = None
    if len(roles) == 0 or len(users) == 0:    
        message = "Your organization must have atleast one user and one role before assignment."
    return render(request,
            'usermodule/user_role_map.html',
            {'id':org_id,
            'users' : users,
            'roles' : roles,
            'message':message,
            'edited': edited})


@login_required
def adjust_user_role_map(request, org_id=None):
    context = RequestContext(request)
    is_added = False
    roles = OrganizationRole.objects.filter(organization=org_id)
    users = UserModuleProfile.objects.filter(organisation_name=org_id)
    initial_list = []
    for user_item in users:
        alist = UserRoleMap.objects.filter(user=user_item.user_id).values('role')
        mist = []
        for i in alist:
            mist.append( i['role'])
        initial_list.append({'user': user_item.user_id,'role':mist,'username': user_item.user.username})

    UserRoleMapfForm.base_fields['role'] = forms.ModelChoiceField(queryset=roles,empty_label=None)
    PermisssionFormSet = formset_factory(UserRoleMapfForm,max_num=len(users))
    new_formset = PermisssionFormSet(initial=initial_list)
    
    if request.method == 'POST':
        new_formset = PermisssionFormSet(data=request.POST)
        for idx,user_role_form in enumerate(new_formset):
            # user_role_form = UserRoleMapfForm(data=request.POST)
            u_id = request.POST['form-'+str(idx)+'-user']
            mist = initial_list[idx]['role']
            current_user = User.objects.get(pk=u_id)
            results = map(int, request.POST.getlist('role-'+str(idx+1)))
            deleter = list(set(mist) - set(results))
            for role_id in results:
                roley = OrganizationRole.objects.get(pk=role_id)
                try:
                    UserRoleMap.objects.get(user=current_user,role=roley)
                except ObjectDoesNotExist as e:
                    UserRoleMap(user=current_user,role=roley).save()
            for dely in deleter:
                loly = OrganizationRole.objects.get(pk=dely)
                ob = UserRoleMap.objects.get(user=current_user,role=loly).delete()
        messages.success(request, '<i class="fa fa-check-circle"></i> Organization Roles have been adjusted successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/user-role-map/'+org_id)
    
    return render(request,
            'usermodule/add_user_role_map.html',
            {
            'id':org_id,
            # 'formset':formset,
            'new_formset':new_formset,
            'roles':roles,
            # 'users':users,
            })


def error_page(request,message = None):
    context = RequestContext(request)
    if not message:    
        message = "Something went wrong"
    return render(request,
            'usermodule/error_404.html',
            {'message':message,
            })

@csrf_exempt
#@login_required
def sent_datalist(request,username):
    content_user = get_object_or_404(User, username__iexact=str(username))
    print content_user.username
    cursor = connection.cursor()
    json_data_response = []
    #instance_data_json = {}
    try:
        passing_data  = [content_user.id]
        cursor.execute("BEGIN")
        cursor.callproc('get_submitted_data',passing_data)
        tmp_db_value = cursor.fetchall()
        cursor.execute("COMMIT")
	print (tmp_db_value)
        if tmp_db_value is not None:
            for every in tmp_db_value:
                instance_data_json = {}
                #event_type = switch_event_type_label(str(every[1]))
                instance_data_json['hh_id'] = str(every[0])
                instance_data_json['h_man'] = str(every[1])
                instance_data_json['uuid'] = str(every[2])
                instance_data_json['xform_id'] = every[4]
                instance_data_json['date_created'] = str(every[3])
                json_data_response.append(instance_data_json)

           # print json_data_response
        submission_status = 0
    except Exception, e:
        print "db insert error"
        print str(e)
        submission_status = 1
        # Rollback in case there is any error
        connection.rollback()
    finally:
        cursor.close()
        return_value = {
            'submission_status':submission_status,
        }
    return HttpResponse(json.dumps(json_data_response))


##################################################
##################################################
##################################################






@login_required
def register(request):
    # Like before, get the request's context.
    context = RequestContext(request)
    admin_check = UserModuleProfile.objects.filter(user=request.user)

    if request.user.is_superuser:
        admin_check = True
    elif admin_check:
        admin_check = admin_check[0].admin
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False
    # print(FaoDesignations.objects.all())
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST, admin_check=admin_check)
        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            form_bool = request.POST.get("admin", "xxx")
            if form_bool == "xxx":
                form_bool_value = False
            else:
                form_bool_value = True

            # encrypted password is saved so that it can be saved in password history table
            encrypted_password = make_password(user.password)
            user.password = encrypted_password
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            # profile.organisation_name = request.POST.get("organisation_name", "-1")
            profile.user = user
            expiry_months_delta = 3
            # Date representing the next expiry date
            next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
            profile.expired = next_expiry_date
            profile.admin = form_bool_value
            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            # if 'picture' in request.FILES:
            #     profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # kobo main/models/UserProfile
            main_user_profile = UserProfile(user=user)
            main_user_profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

            # insert password into password history
            passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            #User  role map save   ##FOR MJIVITA
            roley = OrganizationRole.objects.get(pk=profile.role_id)
            UserRoleMap(user=user, role=roley).save()

            #If the selected role has parent then map  ##FOR MJIVITA
            if request.POST.get('supervisor'):
                __db_commit_query("INSERT INTO public.user_supervisor_map(id, user_id, supervisor_id)VALUES (DEFAULT, "+str(user.id)+","+str(request.POST.get('supervisor'))+")")

            #User batch :: APPlicable for only FD
            if request.POST.get('batch'):
                __db_commit_query(
                    "INSERT INTO public.user_batch_map(id, user_id, batch_id)VALUES (DEFAULT, " + str(
                        user.id) + "," + str(request.POST.get('batch')) + ")")

            # insert user branch  mapping in usermodule_userbranchmap table
            branch = request.POST.getlist('branch_name')
            for tmp in branch:
                user_branch = UserBranch(user_id=user.id, branch_id=int(tmp))
                user_branch.save()

            messages.success(request, '<i class="fa fa-check-circle"></i> New User has been registered successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            #print user_form.errors, profile_form.errors
            return render(request,
                'usermodule/register.html',
                {'user_form': user_form, 'profile_form': profile_form, 'registered': registered,'EXIST_BRANCH' : EXIST_BRANCH})


            # profile_form = UserProfileForm(admin_check=admin_check)

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:

        user_form = UserForm()
        # get request users org and the orgs he can see then pass it to model choice field
        org_id_list = get_organization_by_user(request.user)
        # org id list is not available for superuser's like kobo
        if not org_id_list:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(
                queryset=Organizations.objects.all(), empty_label="Select a Organization")
        else:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(
                queryset=Organizations.objects.filter(pk__in=org_id_list), empty_label="Select a Organization")
        profile_form = UserProfileForm(admin_check=admin_check)
    # Render the template depending on the context.
    return render_to_response(
        'usermodule/register.html',
        {'user_form': user_form, 'profile_form': profile_form, 'registered': registered,'EXIST_BRANCH' : EXIST_BRANCH},
        context)


def get_supervisor(request):
    role_id = int(request.POST.get('role_id'))
    role = OrganizationRole.objects.filter(pk=role_id ).first()
    supervisors_list = []
    parent = None
    batch_list = []
    if role.role == 'FD':
        batch_list = __db_fetch_values_dict("select * from batch")
    if role.parent_role is not None:
        parent =  role.parent_role.role
        #supervisors = UserModuleProfile.objects.filter(role_id =role.parent_role_id)
        #print supervisors
        supervisors = UserModuleProfile.objects.filter(role_id =role.parent_role_id)
        queryset = User.objects.filter(id__in=supervisors.values('user_id'))
        for temp in queryset:
            data_dict = {}
            data_dict['id'] = temp.id
            data_dict['name'] = temp.first_name + ' ' + temp.last_name
            supervisors_list.append(data_dict.copy())
            data_dict.clear()
    data = {
        'parent_role' : parent,
        'supervisors' : supervisors_list,
        'batchlist' : batch_list
    }
    print data
    return HttpResponse(json.dumps(data))

@login_required
def edit_profile(request,user_id):
    context = RequestContext(request)
    edited = False
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserModuleProfile, user_id=user_id)
    user_branch =[]
    user_branch = get_branch_info(user_id)
    user_branch_number = len(user_branch)
    admin_check = UserModuleProfile.objects.filter(user=request.user)
    if request.user.is_superuser:
        admin_check = True
    elif admin_check:
        admin_check = admin_check[0].admin
    print admin_check
    #Get Supervisor
    supervisor_id=None
    cursor = connection.cursor()
    cursor.execute("select supervisor_id from user_supervisor_map where user_id = "+str(user_id)+" limit 1")
    fetchVal = cursor.fetchone()
    if fetchVal:
        supervisor_id = fetchVal[0]
    cursor.close()

    # Get Supervisor
    batch_id = None
    #try:
    #    cursor = connection.cursor()
    #    cursor.execute("select batch_id from user_batch_map where user_id = " + str(user_id) + " limit 1")
    #    fetchVal = cursor.fetchone()
    #    if fetchVal:
    #        batch_id = fetchVal[0]
    #except Exception as ex:
    #    batch_id = None
    #finally:
    #    cursor.close()
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserEditForm(data=request.POST, instance=user, user=request.user)
        profile_form = UserProfileForm(data=request.POST,instance=profile,  admin_check=admin_check)
        #profile_form = UserProfileForm({'role': profile.role_id ,'organisation_name' : profile.organisation_name})
        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            edited_user = user_form.save(commit=False);
            # password_new = request.POST['password']
            # if password_new:
            #     edited_user.set_password(password_new)
            edited_user.save()
            form_bool = request.POST.get("admin", "xxx")
            if form_bool == "xxx":
                form_bool_value = False
            else:
                form_bool_value = True
            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            # profile.organisation_name = request.POST.get("organisation_name", "-1")
            # profile.admin = request.POST.get("admin", "False")
            profile.user = edited_user
            profile.admin = form_bool_value
            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            # if 'picture' in request.FILES:
            #     profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # change User branch mapping in userbranchmap table

            branch = request.POST.getlist('branch_name')
            for tmp in branch:
                user_branch = UserBranch.objects.filter(user_id=user.id,branch_id=int(tmp)).first()
                if user_branch is None:
                    profile_org = UserBranch(user_id=user.id, branch_id=int(tmp))
                    profile_org.save()

            # for changing previous data which is not selected now
            user_branches = UserBranch.objects.filter(user_id=user.id)
            for temp in user_branches:
                if str(temp.branch_id) not in branch:
                    temp.delete()

            # User  role map save   ##FOR MJIVITA
            roley = OrganizationRole.objects.get(pk=profile.role_id)
            ob = UserRoleMap.objects.get(user=user).delete()
            UserRoleMap(user=user, role=roley).save()

            # If the selected role has parent then map  ##FOR MJIVITA
            #__db_commit_query("delete from user_supervisor_map where user_id = "+str(user.id))
            #if request.POST.get('supervisor'):
            #    __db_commit_query(
            #        "INSERT INTO public.user_supervisor_map(id, user_id, supervisor_id)VALUES (DEFAULT, " + str(
            #            user_id) + "," + str(request.POST.get('supervisor')) + ")")

            # User batch :: APPlicable for only FD
            #if request.POST.get('batch'):
            #    print "batch id is::::::::::::::::::::::;"+str(request.POST.get('batch'))
            #    cursor = connection.cursor()
            #    cursor.execute("select id from user_batch_map where user_id = "+str(user_id)+ " limit 1")
            #    fetchVal = cursor.fetchone()
            #    if fetchVal:
            #        __db_commit_query(
            #            "update user_batch_map set batch_id = " + str(request.POST.get('batch')) + "  where user_id = " + str(user_id))
            #    else:
            #        __db_commit_query(
            #            "INSERT INTO public.user_batch_map(id, user_id, batch_id)VALUES (DEFAULT, " + str(
            #                user.id) + "," + str(request.POST.get('batch')) + ")")

            #    cursor.close()



            # Update our variable to tell the template registration was successful.
            edited = True
            messages.success(request, '<i class="fa fa-check-circle"></i> User profile has been updated successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            #profile_form = UserProfileForm(admin_check=admin_check)
            print user_form.errors, profile_form.errors
            #print profile_form
            return render(request,
                          'usermodule/edit_user.html',
                          {'id': user_id, 'user_form': user_form, 'profile_form': profile_form, 'edited': edited,'user_branches' : user_branch,'user_branch_number' : user_branch_number,'EXIST_BRANCH' : EXIST_BRANCH,'supervisor_id' : supervisor_id,'batch_id' : batch_id})


    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserEditForm(instance=user, user=request.user)
        org_id_list = get_organization_by_user(request.user)
        if not org_id_list:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(
                queryset=Organizations.objects.all(), empty_label="Select a Organization")
        else:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(
                queryset=Organizations.objects.filter(pk__in=org_id_list)
                , empty_label="Select a Organization")
        profile_form = UserProfileForm(instance=profile, admin_check=admin_check)
        #profile_form = UserProfileForm({'role': profile.role_id, 'organisation_name': profile.organisation_name})
        return render(request,
            'usermodule/edit_user.html',
        {'id': user_id, 'user_form': user_form, 'profile_form': profile_form, 'edited': edited,'user_branches' : user_branch,'user_branch_number' : user_branch_number,'EXIST_BRANCH' : EXIST_BRANCH,'supervisor_id' : supervisor_id,'batch_id' : batch_id})



def getDistricts(request):
    division = request.POST.get('div')
    district_query = "select value,name from geo_cluster where loc_type = 2 and parent = " + str(division)
    district_data = json.dumps(__db_fetch_values_dict(district_query))
    return HttpResponse(district_data)


def getUpazilas(request):
    district = request.POST.get('dist')
    upazila_query = "select value,name from geo_cluster where loc_type = 3 and parent = " + str(district)
    upazila_data = json.dumps(__db_fetch_values_dict(upazila_query))
    return HttpResponse(upazila_data)


def __db_fetch_values(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchall()
    cursor.close()
    return fetchVal


def __db_fetch_single_value(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    return fetchVal[0]


def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal


def __db_commit_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    cursor.close()


def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]


def decimal_date_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj
    raise TypeError


def user_role_mapping(request):
    start = datetime.now()

    if request.POST:
        current_val = json.loads(request.POST.get('current_val'))
        for each in current_val:
            if each['value'] == 1:
                store = str(each['id']).split('_')
                role = store[0]
                user_id = store[1]
                add_query = "INSERT INTO core.usermodule_userrolemap(user_id, role_id)VALUES((select id from usermodule_usermoduleprofile where user_id = "+str(user_id)+"), (select id from usermodule_organizationrole where role = '"+str(role)+"'))"
                __db_commit_query(add_query)
            elif each['value'] == 0:
                store = str(each['id']).split('_')
                role = store[0]
                user_id = store[1]
                delete_query = "delete from usermodule_userrolemap where user_id = (select id from usermodule_usermoduleprofile where user_id = "+str(user_id)+") and role_id = (select id from usermodule_organizationrole where role = '"+str(role)+"')"
                __db_commit_query(delete_query)

    query = "with t as( select(select user_id from usermodule_usermoduleprofile where id = m.user_id)user_id,role_id from usermodule_userrolemap m), t1 as ( select user_id,role, 1 as status from t,usermodule_organizationrole r where t.role_id = r.id ), t2 as ( select auth_user.id user_id,role from auth_user,usermodule_organizationrole ), all_false as ( select user_id,role from t2 except select user_id,role from t1 ),all_false1 as ( select *,0 as status from all_false ), final_res as ( select * from t1 union all select * from all_false1 ) select user_id,(select username from auth_user where id = user_id)username,(select first_name || ' ' ||last_name from auth_user where id = user_id) fullname,(select \"position\" from usermodule_usermoduleprofile where user_id = final_res.user_id) designation,role,status from final_res"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    if not df.empty:
        df = df.pivot_table(index=['user_id','username', 'fullname', 'designation'], columns='role', values='status').reset_index()
        columns = json.dumps(df.columns.tolist())
        data = json.dumps(df.to_dict(orient='records'))
    else:
        return error_page(request, "No Data Available")

    organization_query = "select id,organization from usermodule_organizations"
    df = pandas.DataFrame()
    df = pandas.read_sql(organization_query,connection)
    org_id = df.id.tolist()
    org_name = df.organization.tolist()
    organization = zip(org_id,org_name)
    print(datetime.now()-start)
    return render(request, "usermodule/user_role_mapping.html", {'data': data,'columns':columns,'organization':organization})



# ******Branch Management ******************#

@login_required
def branch_list(request):
    if EXIST_BRANCH == False:
        return error_page(request, "Page not found!")
    query = "select id,branch_name,(select organization from usermodule_organizations where id = organization_id) organization_name,coalesce(address,'') address,coalesce(branch_code,'') branch_code from usermodule_branch"
    branch_list = json.dumps(__db_fetch_values_dict(query))
    return render(request, 'usermodule/branch_list.html', {
       'branch_list': branch_list
    })


@login_required
def add_branch_form(request):
    if EXIST_BRANCH == False:
        return error_page(request, "Page not found!")
    query = "select id,organization from usermodule_organizations"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization_id = df.id.tolist()
    organization_name = df.organization.tolist()
    organization = zip(organization_id, organization_name)
    return render(request, 'usermodule/add_branch_form.html',
                 { 'organization': organization})

@login_required
def insert_branch_form(request):
   if request.POST:
       branch_name = request.POST.get('branch_name')
       organization_id = request.POST.get('organization_id')
       branch_code = request.POST.get('branch_code')
       address = request.POST.get('address')
       insert_query = "INSERT INTO core.usermodule_branch(branch_name, organization_id, branch_code, address) VALUES('"+str(branch_name)+"', "+str(organization_id)+", '"+str(branch_code)+"', '"+str(address)+"')"
       __db_commit_query(insert_query)
   return HttpResponseRedirect("/usermodule/branch-list/")


@login_required
def edit_branch_form(request, branch_id):
    if EXIST_BRANCH == False:
        return error_page(request, "Page not found!")
    query = "select id,branch_name,organization_id,(select organization from usermodule_organizations where id = organization_id) organization_name,coalesce(address,'') address,coalesce(branch_code,'') branch_code from usermodule_branch where id=" + str(branch_id)
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    data = {}
    data['branch_id'] = branch_id
    data['branch_name'] = df.branch_name.tolist()[0]
    set_organization_id = df.organization_id.tolist()[0]
    data['address'] = df.address.tolist()[0]
    data['branch_code'] = df.branch_code.tolist()[0]
    query = "select id,organization from usermodule_organizations"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization_id = df.id.tolist()
    organization_name = df.organization.tolist()
    organization = zip(organization_id, organization_name)
    return render(request, 'usermodule/edit_branch_form.html',
                 {'data': json.dumps(data),'set_organization_id':set_organization_id,'organization':organization})

@login_required
def update_branch_form(request):
   if request.POST:
       branch_id = request.POST.get('branch_id')
       branch_name = request.POST.get('branch_name')
       organization_id = request.POST.get('organization_id')
       branch_code = request.POST.get('branch_code')
       address = request.POST.get('address')
       update_query = "UPDATE usermodule_branch SET branch_name='"+str(branch_name)+"', organization_id="+str(organization_id)+", address='"+str(address)+"', branch_code = '"+str(branch_code)+"' WHERE id=" + str(branch_id)
       __db_commit_query(update_query)
   return HttpResponseRedirect("/usermodule/branch-list/")

@login_required
def delete_branch_form(request, branch_id):
   delete_query = "delete from usermodule_branch where id = " + str(branch_id) + ""
   __db_commit_query(delete_query)
   return HttpResponseRedirect("/usermodule/branch-list/")


@csrf_exempt
def get_branch(request):
    org = request.POST.get('org_id')
    dataset = []
    if org:
        q = "select * from usermodule_branch where organization_id = "+str(org)
        dataset = __db_fetch_values_dict(q)

    return render(request, 'usermodule/branch_table.html',
                  {'dataset': dataset}, status=200)


@csrf_exempt
def get_user_branch(request):
    org = request.POST.get('org_id')
    user_id = request.POST.get('user_id')
    dataset = []
    user_data = []
    data_list = []
    if org:
        q = "select * from usermodule_branch where organization_id = "+str(org)
        data_list = __db_fetch_values_dict(q)
        user_q = "select * from usermodule_userbranchmap where user_id = "+str(user_id)
        user_data = __db_fetch_values_dict(user_q)
    for data in data_list:
        data_dict = {}
        checked = ""
        data_dict['branch_name'] = data['branch_name']
        data_dict['branch_code'] = data['branch_code']
        data_dict['address'] = data['address']
        data_dict['id'] = data['id']
        for tmp in user_data:
            if tmp['branch_id'] == data['id']:
                checked = 'checked'
        data_dict['checked'] = checked
        dataset.append(data_dict.copy())
        data_dict.clear()
    #print dataset

    return render(request, 'usermodule/branch_table.html',
                  {'dataset': dataset}, status=200)



def get_branch_info(user_id):
    q = "select branch_id as id , (select branch_name from usermodule_branch where id = usermodule_userbranchmap.branch_id limit 1) as name from usermodule_userbranchmap where user_id = "+str(user_id)
    dataset = []
    data_list = __db_fetch_values_dict(q)
    for data in data_list:
        data_dict = {}
        data_dict['name'] = data['name']
        data_dict['id'] = data['id']
        dataset.append(data_dict.copy())
        data_dict.clear()
    return dataset


@login_required
def geo_def_list(request):
    geo_def_query = "with t as (select * from geo_definition) select t.id ,t.node_name , (select node_name from geo_definition where id = t.node_parent) as node_parent_name from t"
    geo_def_data = json.dumps(__db_fetch_values_dict(geo_def_query))
    return render(request,'usermodule/geo_def_list.html',{
      'geo_def_data':geo_def_data
    })

@login_required
def form_def(request):
    if request.POST:
        parent_id = request.POST.get('node_parent')
        print(parent_id)
        node_name = request.POST.get('node_name')
        if parent_id != '0':
            query = "INSERT INTO geo_definition(node_name, node_parent)VALUES ('" + str(node_name) + "' , " + str(parent_id) + ")"
        else:
            query = "INSERT INTO geo_definition(node_name)VALUES ('" + str(node_name) + "' )"
        __db_commit_query(query)
        return HttpResponseRedirect('/usermodule/geo_def_data/')

    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_id = check.id.tolist()
    node_val = check.node_name.tolist()
    node = zip(node_id,node_val)

    return render(request, "usermodule/form_definition.html", {"node": node})


@login_required
def edit_form_definition(request, form_definition_id):
    query = "select * from geo_definition where id = "+str(form_definition_id)
    df = pandas.read_sql(query,connection)
    node_name = df.node_name.tolist()[0]
    node_parent_id = df.node_parent.tolist()[0]

    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_id = check.id.tolist()
    node_val = check.node_name.tolist()
    node = zip(node_id, node_val)


    return render(request, "usermodule/edit_form_definition.html", {"node": node,
                                                                    'node_parent_id': node_parent_id,
                                                                    'node_name': node_name,
                                                                    "form_definition_id": form_definition_id})


@login_required
def update_form_definition(request):
    if request.POST:
        form_definition_id = request.POST.get('form_definition_id')
        parent_id = request.POST.get('node_parent')
        node_name = request.POST.get('node_name')
        if parent_id != '0':
            query = "UPDATE core.geo_definition SET node_name='"+str(node_name)+"', node_parent="+str(parent_id)+" WHERE id="+str(form_definition_id)
        else:
            query = "UPDATE core.geo_definition SET node_name='" + str(node_name) + "' WHERE id=" + str(form_definition_id)
        __db_commit_query(query)
    return HttpResponseRedirect("/usermodule/geo_def_data/")


@login_required
def delete_form_definition(request, form_definition_id):
    list_of_form_definition = []
    form_definition_calculation(list_of_form_definition, form_definition_id)
    print(list_of_form_definition)
    return HttpResponseRedirect("/usermodule/geo_def_data/")


def form_definition_calculation(list_of_form_definition, form_definition_id):
    list_of_form_definition.append(int(form_definition_id))
    query = "select * from geo_definition where node_parent=" + str(form_definition_id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    query = "select * from geo_data where field_type_id=" + str(form_definition_id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    form_id = df.id.tolist()
    # for each in form_id:
    #     delete_from_catchment_area = "delete from usermodule_catchment_area where geoid = " + str(each) + ""
    #     __db_commit_query(delete_from_catchment_area)
    delete_query = "delete from geo_definition where id =" + str(int(form_definition_id)) + ""
    __db_commit_query(delete_query)
    delete_query = "delete from geo_data where field_type_id =" + str(int(form_definition_id)) + ""
    __db_commit_query(delete_query)
    for each in id:
        form_definition_calculation(list_of_form_definition, each)


@login_required
def geo_list(request):
    if 'page_length' in request.GET:
        page_length = request.GET['page_length']
    else:
        page_length = 10

    if 'page_no' in request.GET:
        page_no = request.GET['page_no']
    else:
        page_no = 1

    tc = __db_fetch_single_value("""
    select count(*) from core.geo_data
    """)
    query = """
    select gd.id,field_name,gdf.node_name as field_type,geocode 
	from core.geo_data gd
	left join core.geo_definition gdf
	on gdf.id = gd.field_type_id 
	order by gd.updated_date desc
	limit %s offset (%s * (%s -1))
    """ % (page_length, page_length, page_no)
    range_last = tc / int(page_length)
    page_start = int(page_no) - 3
    if page_start < 1:
        page_start = 1
    page_end = page_start + 6
    if page_end >= range_last + 1:
        page_end = range_last + 1

    record_end = int(page_no) * int(page_length)
    if record_end > tc:
        record_end = tc
    geo_def_data = __db_fetch_values(query)
    return render(request,'usermodule/geo_list.html',{
        'geo_def_data': geo_def_data,
        'page_no': page_no,
        'page_length': page_length,
        'range': range(page_start, page_end + 1),
        'range_last': range_last + 1,
        'tc': tc,
        'record_start': int(page_no) * int(page_length) - (int(page_length) - 1),
        'record_end': record_end
    })


@login_required
@transaction.atomic
def form(request):
    global parent
    if request.POST:
        if request.FILES:
            myfile = request.FILES['geojsonfile']
            url = "onadata/media/uploaded_files/"
            userName = request.user #"Jubair"
            fs = FileSystemStorage(location=url)
            myfile.name = str(datetime.now()) + "_" + str(userName) + "_" + str(myfile.name)
            filename = fs.save(myfile.name, myfile)
            full_file_path = "onadata/media/uploaded_files/" + myfile.name
            file = open(full_file_path, 'r')
            json_content = file.read()
            file.close()
        else:
            json_content = '{}'
            full_file_path = 'cd'
        parent = int(request.POST.get("parent_id"))
        if parent != -1:
            query = "INSERT INTO geo_data(field_name, field_parent_id,field_type_id,geocode,geojson,uploaded_file_path) VALUES('" + str(
                request.POST.get('field_name')) + "'," + str(
                request.POST.get('field_parent_' + str(parent) + '')) + "," + str(
                request.POST.get('field_type')) + ",'" + str(request.POST.get('geocode')) + "','" + str(
                json_content) + "','" + str(full_file_path) + "')"
        else:
            query = "INSERT INTO geo_data(field_name, field_type_id,geocode,geojson,uploaded_file_path) VALUES('" + str(
                request.POST.get('field_name')) + "'," + str(request.POST.get('field_type')) + "," + str(
                request.POST.get('geocode')) + ",'" + str(json_content) + "','" + str(full_file_path) + "')"
        __db_commit_query(query)
        if len(str(request.POST.get('geocode'))) == 11:
            parent_code = str(request.POST.get('geocode'))[:-3]
        else:
            parent_code = str(request.POST.get('geocode'))[:-2]

        __db_commit_query("""
        INSERT INTO core.geo_cluster
        (value, "name", loc_type, parent, longitude, latitude, updated_at)
        VALUES(%s, '%s', %s, %s, NOW())
        """ % (str(request.POST.get('geocode')), str(request.POST.get('field_name')), request.POST.get('field_type'),
               parent_code))
        return HttpResponseRedirect("/usermodule/geo_list/")
    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_val = check.node_name.tolist()
    node_id = check.id.tolist()
    node = json.dumps({"node_val": node_val, "node_id": node_id})
    list = zip(node_id, node_val)

    # division geocode fetch
    division_geocode_query = "select geocode from geo_data where field_parent_id  is null"
    df = pandas.DataFrame()
    df = pandas.read_sql(division_geocode_query,connection)
    division_geocode =  df.geocode.tolist()
    return render(request, 'usermodule/form.html', {'node': list,'division_geocode':json.dumps(division_geocode)})

@login_required
def form_drop(request):
    if request.POST:
        df = pandas.DataFrame()
        fb = str(request.POST.get('field_type'))
        field_name_query = "select * from geo_data where field_type_id = " + str(request.POST.get('field_type')) + ""
        df = pandas.read_sql(field_name_query, connection)
        field_name = df.field_name.tolist()
        field_id = df.id.tolist()
        field_type_name_query = "select * from geo_definition where id = " + str(request.POST.get('field_type')) + ""
        df = pandas.read_sql(field_type_name_query, connection)
        field_type_name = df.node_name.tolist()
    field_name = json.dumps({'field_name': field_name, 'field_id': field_id, 'field_type_name': field_type_name})
    return HttpResponse(field_name)

@login_required
def filtering(request):
    if request.POST:
        df = pandas.DataFrame()
        field_name_query = "select * from geo_data where field_type_id = " + str(
            request.POST.get('field_type_id')) + " and field_parent_id = " + str(
            request.POST.get('field_parent_id')) + ""
        df = pandas.read_sql(field_name_query, connection)
        field_name = df.field_name.tolist()
        geocode = df.geocode.tolist()
        field_id = df.id.tolist()
        field_type_query = "select * from geo_definition where id=" + str(request.POST.get('field_type_id')) + ""
        df = pandas.read_sql(field_type_query, connection)
        field_type = df.node_name.tolist()
    field_name = json.dumps({'field_name': field_name, 'field_id': field_id, 'field_type': field_type,'geocode':geocode})
    return HttpResponse(field_name)

@csrf_exempt
@login_required
def tree(request):
    id = int(request.POST.get('objet'))
    # print(id)
    list = []
    tree_construct(id, list)
    response_record = {}
    if len(list):
        for i in range(len(list) - 1):
            response_record[list[i]] = list[i + 1]
        response_record[list[len(list) - 1]] = id
        parent = list[len(list) - 1]
    else:
        parent = -1
    return HttpResponse(json.dumps({'response_record': response_record,'parent_id':parent}))

def tree_construct(id, list):
    query = "select * from geo_definition where id = " + str(id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    parent = df.node_parent.tolist()
    if parent[0] is None:
        return
    else:
        tree_construct(parent[0], list)
    list.append(parent[0])
    return

def calculate_parents(list_of_id_of_parents,list_of_name_of_parents, field_parent_id):
    query="select * from geo_data where id="+str(field_parent_id)+""
    df = pandas.DataFrame()
    df = pandas.read_sql(query,connection)
    id = df.id.tolist()[0]
    field_name = df.field_name.tolist()[0]
    field_parent_id = df.field_parent_id.tolist()[0]
    list_of_id_of_parents.append(id)
    list_of_name_of_parents.append(field_name)
    if field_parent_id is not None:
        calculate_parents(list_of_id_of_parents,list_of_name_of_parents,field_parent_id)

@login_required
def edit_form(request,form_id):
    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_val = check.node_name.tolist()
    node_id = check.id.tolist()
    node = json.dumps({"node_val": node_val, "node_id": node_id})
    list = zip(node_id, node_val)
    query_specific = "select field_name,field_parent_id,field_type_id,(select node_name from geo_definition where id = field_type_id ) as field_type,geocode,uploaded_file_path from geo_data where id =" + str(
        form_id) + ""
    check = pandas.read_sql(query_specific, connection)
    field_parent_id = check.field_parent_id.tolist()[0]
    field_name = check.field_name.tolist()[0]
    field_type = check.field_type.tolist()[0]
    geocode = check.geocode.tolist()[0]
    field_type_id = check.field_type_id.tolist()[0]
    uploaded_file_path = check.uploaded_file_path.tolist()[0]
    list_of_id_of_parents = []
    list_of_name_of_parents = []
    if field_parent_id is not None:
        calculate_parents(list_of_id_of_parents, list_of_name_of_parents, field_parent_id)
    list_of_both = json.dumps(
        {'list_of_id_of_parents': list_of_id_of_parents, 'list_of_name_of_parents': list_of_name_of_parents})

    if field_parent_id is not None:
        field_name_query = "select geocode from geo_data where field_type_id = " + str(
            field_type_id) + " and field_parent_id = " + str(field_parent_id) + ""
    else:
        field_name_query = "select geocode from geo_data where field_type_id = " + str(
            field_type_id) + " and field_parent_id  is null"
    df = pandas.read_sql(field_name_query, connection)
    all_geocode = df.geocode.tolist()

    # Dependency Check
    # First if it exists in usermodule_catchment_area
    # query_user = "select * from public.usermodule_catchment_area where geoid =" + str(form_id)
    # df_user = pandas.DataFrame()
    # df_user = pandas.read_sql(query_user, connection)

    # if it exists in organization_catchment_area
    # query_org = "select * from public.organization_catchment_area where geoid =" + str(form_id)
    # df_org = pandas.DataFrame()
    # df_org = pandas.read_sql(query_org, connection)

    # if it has any children
    query_child = "select * from core.geo_data where field_parent_id =" + str(form_id)
    df_child = pandas.DataFrame()
    df_child = pandas.read_sql(query_child, connection)

    # if df_user.empty and df_org.empty and df_child.empty and parent_dependency_check_user(form_id) and parent_dependency_check_org(form_id):
    if df_child.empty:
        dependency = 0
    else:
        dependency = 1

    return render(request, 'usermodule/edit_form.html', {'node': list,
                                                         'form_id': form_id,
                                                         'field_parent_id': field_parent_id,
                                                         'field_name': field_name,
                                                         'field_type': field_type,
                                                         'geocode': geocode,
                                                         'uploaded_file_path': uploaded_file_path,
                                                         'field_type_id': field_type_id,
                                                         'list_of_both': list_of_both,
                                                         'dependency': dependency,
                                                         'all_geocode': json.dumps(all_geocode)
                                                         })

@login_required
def update_form(request):
    if request.POST:
        if request.FILES:
            myfile = request.FILES['geojsonfile']
            url = "onadata/media/uploaded_files/"
            userName = request.user  # "Jubair"
            fs = FileSystemStorage(location=url)
            myfile.name = str(datetime.now()) + "_" + str(userName) + "_" + str(myfile.name)
            filename = fs.save(myfile.name, myfile)
            full_file_path = "onadata/media/uploaded_files/" + myfile.name
            file = open(full_file_path, 'r')
            json_content = file.read()
            file.close()
        else:
            query = "select geojson,uploaded_file_path from geo_data where id = "+str(request.POST.get("form_id"))
            df = pandas.DataFrame()
            df = pandas.read_sql(query,connection)
            if df.empty:
                json_content = '{}'
                full_file_path = 'cd'
            else:
                json_content = json.dumps(df.geojson.tolist()[0])
                full_file_path = df.uploaded_file_path.tolist()[0]
        parent = int(request.POST.get("parent_id"))
        old_geo_code = __db_fetch_single_value("""
                select geocode from core.geo_data where id = %s
                """ % request.POST.get("form_id"))
        if parent != -1:
            query = "UPDATE core.geo_data SET field_name='"+ str(request.POST.get('field_name'))+"', field_parent_id="+str(request.POST.get('field_parent_' + str(parent) + '')) +", field_type_id="+ str(request.POST.get('field_type'))+", geocode='"+ str(request.POST.get('geocode'))+"', geojson='"+ str(json_content)+"', uploaded_file_path='"+str(full_file_path)+"' WHERE id="+str(request.POST.get("form_id"))
        else:
            query = "UPDATE core.geo_data SET field_name='"+ str(request.POST.get('field_name'))+"', field_type_id="+ str(request.POST.get('field_type'))+", geocode='"+ str(request.POST.get('geocode'))+"', geojson='"+ str(json_content)+"', uploaded_file_path='"+str(full_file_path)+"' WHERE id="+str(request.POST.get("form_id"))+""
        __db_commit_query(query)

        if len(str(request.POST.get('geocode'))) == 11:
            parent_code = str(request.POST.get('geocode'))[:-3]
        else:
            parent_code = str(request.POST.get('geocode'))[:-2]

    __db_commit_query("""
    update core.geo_cluster set name = '%s', value = %s, parent = %s where value = %s
    """ % (str(request.POST.get('field_name')), str(request.POST.get('geocode')), parent_code, old_geo_code))

    return HttpResponseRedirect("/usermodule/geo_list/")

@login_required
def delete_form(request,form_id):
    # Dependency Check
    # First if it exists in usermodule_catchment_area
    # query_user = "select * from public.usermodule_catchment_area where geoid =" + str(form_id)
    # df_user = pandas.DataFrame()
    # df_user = pandas.read_sql(query_user, connection)

    # if it exists in organization_catchment_area
    # query_org = "select * from public.organization_catchment_area where geoid =" + str(form_id)
    # df_org = pandas.DataFrame()
    # df_org = pandas.read_sql(query_org, connection)

    # if it has any children
    query_child = "select * from core.geo_data where field_parent_id =" + str(form_id)
    df_child = pandas.DataFrame()
    df_child = pandas.read_sql(query_child, connection)

    # if df_user.empty and df_org.empty and df_child.empty:
    if df_child.empty:
        delete_child(int(form_id))
    return HttpResponseRedirect("/usermodule/geo_list/")


def delete_child(form_id):
    query = "select * from geo_data where field_parent_id = "+str(form_id)+""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    query = "select * from geo_data where id = " + str(form_id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    uploaded_file_path = df.uploaded_file_path.tolist()
    if len(uploaded_file_path) and uploaded_file_path[0] != "cd":
        os.remove(uploaded_file_path[0])
    delete_query = "delete from geo_data where id = "+str(form_id)+""
    __db_commit_query(delete_query)
    # delete_from_catchment_area = "delete from usermodule_catchment_area where geoid = "+str(form_id)+""
    # __db_commit_query(delete_from_catchment_area)
    for each in id:
        delete_child(each)


@csrf_exempt
@login_required
def check_for_delete(request):
    id = request.POST.get('id')
    # Dependency Check
    # First if it exists in usermodule_catchment_area
    # query_user = "select (select username from auth_user where id = user_id) from public.usermodule_catchment_area where geoid =" + str(id)
    # df_user = pandas.DataFrame()
    # df_user = pandas.read_sql(query_user, connection)

    # if it exists in organization_catchment_area
    # query_org = "select (select organization from usermodule_organizations where id = org_id) from public.organization_catchment_area where geoid =" + str(id)
    # df_org = pandas.DataFrame()
    # df_org = pandas.read_sql(query_org, connection)

    # if it has any children
    query_child = "select * from core.geo_data where field_parent_id =" + str(id)
    df_child = pandas.DataFrame()
    df_child = pandas.read_sql(query_child, connection)

    extra_info= ""
    # if df_user.empty and df_org.empty and df_child.empty and parent_dependency_check_user(id) and parent_dependency_check_org(id):
    if df_child.empty:
        dependency = 0
    # elif not df_user.empty:
    #     extra_info =df_user.username.tolist()[0]
    #     dependency = 1
    # elif not df_org.empty:
    #     extra_info = df_org.organization.tolist()[0]
    #     dependency = 2
    else:
        dependency = 3
    return HttpResponse(json.dumps({'dependency':dependency,'extra_info':extra_info}))


def parent_dependency_check_user(geoid):
    query = "with recursive t as( select id,field_name,field_parent_id from geo_data where id =  " + str(geoid) + " union all select geo_data.id,geo_data.field_name,geo_data.field_parent_id from geo_data,t where t.field_parent_id = geo_data.id) select id,field_name,field_parent_id from t order by id"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    parent_list = df.id.tolist()

    query = "select distinct geoid from usermodule_catchment_area"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    geo_list = df.geoid.tolist()

    for each in parent_list:
        if each in geo_list:
            return False
    return True


def parent_dependency_check_org(geoid):
    query = "with recursive t as( select id,field_name,field_parent_id from geo_data where id =  " + str(
        geoid) + " union all select geo_data.id,geo_data.field_name,geo_data.field_parent_id from geo_data,t where t.field_parent_id = geo_data.id) select id,field_name,field_parent_id from t order by id"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    parent_list = df.id.tolist()

    query = "select distinct geoid from organization_catchment_area"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    geo_list = df.geoid.tolist()

    for each in parent_list:
        if each in geo_list:
            return False
    return True




# *******************                                      *******************#
                    # ACArea, TL PIN, Sector Management#
                            # MJIVITA PLUS#
# *******************                                      ******************#
@csrf_exempt
@login_required
def acarea_list(request):
    query = "select id,(select field_name from geo_data where id = union_id) union_name,coalesce(ac_area_name,'') ac_area_name,coalesce(ac_area_code,'') ac_area_code from ac_area"
    acarea_list = json.dumps(__db_fetch_values_dict(query))
    return render(request, 'usermodule/acarea_list.html', {
       'acarea_list': acarea_list
    })



@csrf_exempt
@login_required
def add_acarea(request):
    q = "select id,field_name from geo_data where field_type_id =28"
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    union_id = df.id.tolist()
    union_name = df.field_name.tolist()
    union_list = zip(union_id, union_name)
    if request.POST:
        acarea_name = request.POST.get('acarea_name')
        union_id = request.POST.get('union_id')
        acarea_code = request.POST.get('acarea_code')
        insert_query = "INSERT INTO public.ac_area(ac_area_name, union_id, ac_area_code) VALUES('" + str(
            acarea_name) + "', " + str(union_id) + ", '" + str(acarea_code) + "')"
        __db_commit_query(insert_query)
        return HttpResponseRedirect("/usermodule/acarea-list/")

    return render(request, 'usermodule/add_acarea.html',
                 { 'union_list': union_list})




@login_required
def edit_acarea(request, id):
    q = "select id,union_id,coalesce(ac_area_name,'') ac_area_name,coalesce(ac_area_code,'') ac_area_code from ac_area where id=" + str(id)
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    data = {}
    data['id'] = id
    data['ac_area_name'] = df.ac_area_name.tolist()[0]
    data['union_id'] = df.union_id.tolist()[0]
    data['ac_area_code'] = df.ac_area_code.tolist()[0]
    q = "select id,field_name from geo_data where field_type_id =28"
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    union_id = df.id.tolist()
    union_name = df.field_name.tolist()
    union_list = zip(union_id, union_name)
    if request.POST:
        acarea_id = request.POST.get('acarea_id')
        acarea_name = request.POST.get('acarea_name')
        union_id = request.POST.get('union_id')
        acarea_code = request.POST.get('acarea_code')
        q = "UPDATE ac_area SET ac_area_name='" + str(acarea_name) + "', union_id=" + str(
            union_id) + ",  ac_area_code = '" + str(
            acarea_code) + "' WHERE id=" + str(acarea_id)
        __db_commit_query(q)
        return HttpResponseRedirect("/usermodule/acarea-list/")
    return render(request, 'usermodule/edit_acarea.html',
                 {'data': data,'union_list':union_list})


@csrf_exempt
@login_required
def tlpin_list(request):
    q = "select id,(select ac_area_name from ac_area where id = ac_area_id) acarea_name,coalesce(tlpin_code,'') tlpin_code from tlpin"
    tlpin_list = json.dumps(__db_fetch_values_dict(q))
    return render(request, 'usermodule/tlpin_list.html', {
       'tlpin_list': tlpin_list
    })



@csrf_exempt
@login_required
def add_tlpin(request):
    q = "select id,ac_area_name from ac_area "
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    acarea_id = df.id.tolist()
    acarea_name = df.ac_area_name.tolist()
    acarea_list = zip(acarea_id, acarea_name)
    if request.POST:
        tlpin_code = request.POST.get('tlpin_code')
        acarea_id = request.POST.get('acarea_id')
        insert_query = "INSERT INTO public.tlpin(tlpin_code, ac_area_id,created_date,created_by) VALUES('" + str(
            tlpin_code) + "', " + str(acarea_id) + ", NOW(),'" + str(request.user.id) + "')"
        __db_commit_query(insert_query)
        return HttpResponseRedirect("/usermodule/tlpin-list/")

    return render(request, 'usermodule/add_tlpin.html',
                 { 'acarea_list': acarea_list})




@login_required
def edit_tlpin(request, id):
    q = "select id,ac_area_id,coalesce(tlpin_code,'') tlpin_code from tlpin where id=" + str(id)
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    data = {}
    data['id'] = id
    data['acarea_id'] = df.ac_area_id.tolist()[0]
    data['tlpin_code'] = df.tlpin_code.tolist()[0]
    q = "select id,ac_area_name from ac_area "
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    acarea_id = df.id.tolist()
    acarea_name = df.ac_area_name.tolist()
    acarea_list = zip(acarea_id, acarea_name)
    if request.POST:
        tlpin_id = request.POST.get('tlpin_id')
        tlpin_code = request.POST.get('tlpin_code')
        acarea_id = request.POST.get('acarea_id')
        q = "UPDATE tlpin SET tlpin_code='" + str(tlpin_code) + "', ac_area_id=" + str(
            acarea_id) + ",  updated_date = NOW(), Updated_by = '" + str(
            request.user.id) + "' WHERE id=" + str(tlpin_id)
        __db_commit_query(q)
        return HttpResponseRedirect("/usermodule/tlpin-list/")
    return render(request, 'usermodule/edit_tlpin.html',
                 {'data': data,'acarea_list':acarea_list})



@login_required
def delete_tlpin(request, id):
   delete_query = "delete from tlpin where id = " + str(id) + ""
   try:
        __db_commit_query(delete_query)
        return HttpResponse("ok")
   except:
       response = HttpResponse(json.dumps({'message': 'error'}),
                               content_type='application/json')
       response.status_code = 500
       return response



@login_required
def delete_sector(request, id):
   delete_query = "delete from sector where id = " + str(id) + ""
   try:
        __db_commit_query(delete_query)
        return HttpResponse("ok")
   except:
       response = HttpResponse(json.dumps({'message': 'error'}),
                               content_type='application/json')
       response.status_code = 500
       return response



@login_required
def delete_acarea(request, id):
   delete_query = "delete from ac_area where id = " + str(id) + ""
   try:
        __db_commit_query(delete_query)
        return HttpResponse("ok")
   except:
       response = HttpResponse(json.dumps({'message': 'error'}),
                               content_type='application/json')
       response.status_code = 500
       return response



@csrf_exempt
@login_required
def sector_list(request):
    q = "select id,(select tlpin_code from tlpin where id = tlpin_id) tlpin_code,coalesce(sector_code,'') sector_code from sector"
    sector_list = json.dumps(__db_fetch_values_dict(q))
    return render(request, 'usermodule/sector_list.html', {
       'sector_list': sector_list
    })



@csrf_exempt
@login_required
def add_sector(request):
    q = "select id,tlpin_code from tlpin "
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    tlpin_id = df.id.tolist()
    tlpin_code = df.tlpin_code.tolist()
    tlpin_list = zip(tlpin_id, tlpin_code)
    if request.POST:
        sector_code = request.POST.get('sector_code')
        tlpin_id = request.POST.get('tlpin_id')
        insert_query = "INSERT INTO public.sector(sector_code, tlpin_id,created_date,created_by) VALUES('" + str(
            sector_code) + "', " + str(tlpin_id) + ", NOW(),'" + str(request.user.id) + "')"
        __db_commit_query(insert_query)
        return HttpResponseRedirect("/usermodule/sector-list/")

    return render(request, 'usermodule/add_sector.html',
                 { 'tlpin_list': tlpin_list})




@login_required
def edit_sector(request, id):
    q = "select id,tlpin_id,coalesce(sector_code,'') sector_code from sector where id=" + str(id)
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    data = {}
    data['id'] = id
    data['tlpin_id'] = df.tlpin_id.tolist()[0]
    data['sector_code'] = df.sector_code.tolist()[0]
    q = "select id,tlpin_code from tlpin "
    df = pandas.DataFrame()
    df = pandas.read_sql(q, connection)
    tlpin_id = df.id.tolist()
    tlpin_code = df.tlpin_code.tolist()
    tlpin_list = zip(tlpin_id, tlpin_code)
    if request.POST:
        sector_id = request.POST.get('sector_id')
        sector_code = request.POST.get('sector_code')
        tlpin_id = request.POST.get('tlpin_id')
        q = "UPDATE sector SET sector_code='" + str(sector_code) + "', tlpin_id=" + str(
            tlpin_id) + ",  updated_date = NOW(), Updated_by = '" + str(
            request.user.id) + "' WHERE id=" + str(sector_id)
        __db_commit_query(q)
        return HttpResponseRedirect("/usermodule/sector-list/")
    return render(request, 'usermodule/edit_sector.html',
                 {'data': data,'tlpin_list':tlpin_list})



@login_required
def map_user(request,user_id,role_id):
    role_name = __db_fetch_single_value("select role from usermodule_organizationrole where id = "+str(role_id))
    user = get_object_or_404(User, id=user_id)
    data_list = get_data_list(role_id,user_id)
    data = {
        'name' : user.first_name + ' '+user.last_name,'username' :user.username,'role' : role_name,'userid' :user.id
    }

    if request.POST:
        new_list = request.POST.getlist('entity')
        userid = request.POST.get('userid')
        try:
            # FD :: Sector
            if role_id == '12':
                d_q = "delete from user_sector where user_id = " + str(userid)
                __db_commit_query(d_q)
                for temp in new_list:
                    i_q = "INSERT INTO public.user_sector(user_id, sector_id)VALUES ("+str(userid)+", "+str(temp)+");"
                    __db_commit_query(i_q)
            # TLI :: TLPIN
            if role_id == '11':
                d_q = "delete from user_tlpin where user_id = " + str(userid)
                __db_commit_query(d_q)
                for temp in new_list:
                    i_q = "INSERT INTO public.user_tlpin(user_id, tlpin_id)VALUES (" + str(userid) + ", " + str(
                        temp) + ");"
                    __db_commit_query(i_q)

            # AC :: ac_area
            if role_id == '10':
                d_q = "delete from user_acarea where user_id = " + str(userid)
                __db_commit_query(d_q)
                for temp in new_list:
                    i_q = "INSERT INTO public.user_acarea(user_id, acarea_id)VALUES (" + str(userid) + ", " + str(
                        temp) + ");"
                    __db_commit_query(i_q)

            messages.success(request, '<i class="fa fa-check-circle"></i> Successfully assigned!',
                             extra_tags='alert-success crop-both-side')
            return redirect("/usermodule/map-user/" + user_id + "/" + role_id)
        except:
            print "I am unable to complete the action."
            messages.error(request, '<i class="fa fa-exclamation-triangle"></i> Action cannot be cpmpleted!',
                           extra_tags='alert-danger crop-both-side')
            return redirect("/usermodule/map-user/"+user_id+"/"+role_id)
    return render(request, 'usermodule/map_user.html',{'data' : data,'dataset' :data_list})


def get_data_list(role_id,user_id):
    data = []
    # FD :: Sector
    if role_id == '12':
        q = "with sector_list as( (select id from sector where NOT(id = any(select sector_id from user_sector))) union ( select sector_id::integer id from user_sector where user_id = "+str(user_id)+") ) select id, sector_code as entity_name from sector where id = any(select id from sector_list)"
        e_q = "select sector_id::integer entity_id from user_sector where user_id = "+str(user_id)
    # TLI :: TLPIN
    if role_id == '11':
        q = "with tlpin_list as( (select id from tlpin where NOT(id = any(select tlpin_id from user_tlpin))) union ( select tlpin_id::integer id from user_tlpin where user_id = "+str(user_id)+") ) select id, tlpin_code as entity_name from tlpin where id = any(select id from tlpin_list)"
        e_q = "select tlpin_id::integer entity_id from user_tlpin where user_id = " + str(user_id)
    # AC :: ac_area
    if role_id == '10':
        q = "with acarea_list as( (select id from ac_area where NOT(id = any(select acarea_id from user_acarea))) union ( select acarea_id::integer id from user_acarea where user_id = "+str(user_id)+") ) select id, ac_area_name as entity_name from ac_area where id = any(select id from acarea_list)"
        e_q = "select acarea_id::integer entity_id from user_acarea where user_id = " + str(user_id)
    e_data = __db_fetch_values_dict(e_q)
    e_list = []
    for tmp in e_data:
        e_list.append(tmp['entity_id'])

    data_list = __db_fetch_values_dict(q)
    for temp in data_list:
        data_dict = {}
        data_dict['id'] = temp['id']
        data_dict['entity_name'] = temp['entity_name']
        data.append(data_dict.copy())
        data_dict.clear()

    dataset = {
        'existed_id' : e_list,'total_ids' : data
    }
    return dataset

'''
    ROLEWISE FORM MAP
'''

def single_query(query):
    """function for  query where result is single"""

    fetchVal = data_connection(query)
    strType = map(str, fetchVal[0])
    ans = strType[0]
    return ans


def data_connection(queryr):
    try:
        cursor = connection.cursor()
        cursor.execute(queryr)
        fetchVal = cursor.fetchall()
        # Commit the changes to the database_
        connection.commit()
        # Close communication with the PostgreSQL database
        cursor.close()
        return fetchVal
    except (Exception) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()


def get_role():
    query = "SELECT r.id, organization_id, role, organization FROM core.usermodule_organizationrole r, core.usermodule_organizations o where r.organization_id=o.id";
    fetchVal = __db_fetch_values(query)
    role_data = []
    for eachval in fetchVal:
        temp = list(eachval)
        role_data.append(temp)
    return role_data


def get_role_permission(id_string):
    query = "select id, xform_id, role_id, can_view, can_submit, can_edit, can_delete, can_setting from core.rolewiseform where xform_id = %d" % (
        id_string)

    permission_data = []
    fetchVal = __db_fetch_values(query)

    for eachval in fetchVal:
        temp = list(eachval)
        permission_data.append(temp)
    return permission_data


def checking_change_permission(view_list, edit_list, submit_list, delete_list, role_list, permission_list):
    """ """
    changed_role = {}
    print view_list
    # checking if permission of role has changed from its previous condition if changed then true else it will be false
    for p in permission_list:
        if str(p[2]) in view_list and p[3] == 0:
            print "view1"
            changed_role[p[2]] = True
        elif str(p[2]) in submit_list and p[4] == 0:
            print "submit1"
            changed_role[p[2]] = True
        elif str(p[2]) in edit_list and p[5] == 0:
            print "edit1"
            changed_role[p[2]] = True
        elif str(p[2]) in delete_list and p[6] == 0:
            print "delete1"
            changed_role[p[2]] = True
        elif str(p[2]) not in view_list and p[3] == 1:
            print str(p[2]) + " view2"
            changed_role[p[2]] = True
        elif str(p[2]) not in submit_list and p[4] == 1:
            print "submit2"
            changed_role[p[2]] = True
        elif str(p[2]) not in edit_list and p[5] == 1:
            print "edit2"
            changed_role[p[2]] = True
        elif str(p[2]) not in delete_list and p[6] == 1:
            print "delete2"
            changed_role[p[2]] = True
        else:
            changed_role[p[2]] = False
    return changed_role


def edit_table(query):
    try:
        print query
        # create a new cursor
        cur = connection.cursor()
        # execute the UPDATE  statement
        cur.execute(query)
        # get the number of updated rows
        vendor_id = cur.fetchone()[0]
        print vendor_id
        # Commit the changes to the database_
        connection.commit()
        # Close communication with the PostgreSQL database
        cur.close()
    except (Exception) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()


@login_required
@csrf_exempt
def startpage(request, username, id_string):
    query = "select id from logger_xform where id_string = '%s'" % (id_string)
    form_id = int(__db_fetch_single_value(query))
    if request.method == 'POST':
        # id_string = request.POST.get('id_string');
        # query = "select id from logger_xform where id_string = '%s'" % (id_string)
        # form_id = int(single_query(query))
        view_list = request.POST.getlist('view_id[]');
        edit_list = request.POST.getlist('edit_id[]');
        submit_list = request.POST.getlist('submit_id[]');
        delete_list = request.POST.getlist('delete_id[]');
        role_list = get_role()
        permission_role = get_role_permission(form_id)
        print "enter 1"
        changed_role = checking_change_permission(view_list, edit_list, submit_list, delete_list, role_list,
                                                  permission_role)
        print "enter 2"
        for r in role_list:
            view_flag = edit_flag = delete_flag = submit_flag = 0
            if r[0] in changed_role and changed_role[r[0]] == True:
                if str(r[0]) in view_list:
                    view_flag = 1
                if str(r[0]) in edit_list:
                    edit_flag = 1
                if str(r[0]) in submit_list:
                    submit_flag = 1
                if str(r[0]) in delete_list:
                    delete_flag = 1
                query = "UPDATE core.rolewiseform SET can_view = %d, can_submit =  %d, can_edit= %d , can_delete=%d where xform_id = %d and role_id=%d" % (
                    view_flag, submit_flag, edit_flag, delete_flag, form_id, r[0])
                __db_commit_query(query)
            else:
                if str(r[0]) in view_list + edit_list + submit_list + delete_list and r[0] not in changed_role:
                    if str(r[0]) in view_list:
                        view_flag = 1
                    if str(r[0]) in edit_list:
                        edit_flag = 1
                    if str(r[0]) in submit_list:
                        submit_flag = 1
                    if str(r[0]) in delete_list:
                        delete_flag = 1
                    query = "INSERT INTO core.rolewiseform ( xform_id, role_id, can_view, can_submit, can_edit, can_delete, can_setting) VALUES (%d, %d, %d, %d, %d, %d, 0) RETURNING id;" % (
                        form_id, r[0], view_flag, submit_flag, edit_flag, delete_flag)
                    __db_commit_query(query)
        messages.success(request, '<i class="fa fa-check-circle"></i> Roles has been updated successfully!',
                         extra_tags='alert-success crop-both-side')

    context = {
        'role_list': get_role(),
        'permission_data': get_role_permission(form_id),
        'id_string': id_string
    }
    return render(request, 'usermodule/startpage.html', context)


def upload_user_csv(request):
    data = {}

    # if not GET, then proceed
    if "POST" == request.method:
        csv_file = request.FILES["csv_file"]
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File is not CSV type')
            return HttpResponseRedirect("/usermodule/upload/csv")
        # if file is too large, return
        if csv_file.multiple_chunks():
            messages.error(request, "Uploaded file is too big (%.2f MB)." % (csv_file.size / (1000 * 1000),))
            return HttpResponseRedirect(reverse("usermodule:upload_csv"))

        file_data = csv_file.read().decode("utf-8")

        lines = file_data.split("\n")
        # loop over the lines and save them in db. If error , store as string and then display

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="user_reject_list.csv"'
        writer = csv.writer(response)
        writer.writerow(str(lines[0]).split(",") + ['Error'])
        print len(lines)
        for line in lines[1:]:

            fields = str(line).split(",")
            if len(fields) < 10:
                return response
            submitted_data = {}
            submitted_data['username'] = str(fields[0]).replace('"','')
            #print fields[1]
            submitted_data['first_name'] = str(fields[1]).replace('"','')
            submitted_data['last_name'] = str(fields[2]).replace('"','')
            submitted_data['email'] = str(fields[3]).replace('"','')
            submitted_data['password'] = str(fields[4]).replace('"','')
            submitted_data['password_repeat'] = str(fields[5]).replace('"','')
            submitted_data['mobile_no'] = str(fields[7])
            organization = str(fields[6])
            # org = Organizations.objects.filter(id=int(organization)).first()
            #
            # if org is not None:
            submitted_data['organisation_name'] = int(organization)
            submitted_data['role'] = str(fields[8])
            submitted_data['supervisor'] = str(fields[9])


            error_string = create_user(submitted_data)
            writer.writerow(fields + [error_string])
        return response
        # pass

    return render(request, "usermodule/user_creation.html", data)


def create_user (submitted_data):
    try:
        user_form = UserForm(data=submitted_data)
        profile_form = UserProfileForm(data=submitted_data, admin_check=admin_check)
        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()




            # encrypted password is saved so that it can be saved in password history table
            encrypted_password = make_password(user.password)
            user.password = encrypted_password
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            # profile.organisation_name = request.POST.get("organisation_name", "-1")
            profile.user = user
            expiry_months_delta = 3
            # Date representing the next expiry date
            next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
            profile.expired = next_expiry_date
            profile.admin = False
            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            # if 'picture' in request.FILES:
            #     profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # kobo main/models/UserProfile
            main_user_profile = UserProfile(user=user)
            main_user_profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

            # insert password into password history
            passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            # User  role map save   ##FOR MJIVITA
            roley = OrganizationRole.objects.get(pk=profile.role_id)
            UserRoleMap(user=user, role=roley).save()

            # If the selected role has parent then map  ##FOR MJIVITA
            if submitted_data['supervisor'] !='':
                __db_commit_query(
                    "INSERT INTO public.user_supervisor_map(id, user_id, supervisor_id)VALUES (DEFAULT, " + str(
                        user.id) + "," + str(submitted_data['supervisor']) + ")")

            # # insert user branch  mapping in usermodule_userbranchmap table
            # branch = request.POST.getlist('branch_name')
            # for tmp in branch:
            #     user_branch = UserBranch(user_id=user.id, branch_id=int(tmp))
            #     user_branch.save()
            return ''
        else:
            error_string = ','.join(user_form.error_class.as_text(v) for k, v in user_form.errors.items())

            error_string += ','.join(
                profile_form.error_class.as_text(v) for k, v in profile_form.errors.items())
            print user_form.errors
            return error_string

    except Exception as e:
        logging.getLogger("error_logger").error(user_form.errors.as_json())
        print "checking"
        print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
        return ''


def user_role_mapping(request):
    start = datetime.now()

    if request.POST:
        current_val = json.loads(request.POST.get('current_val'))
        for each in current_val:
            if each['value'] == 1:
                store = str(each['id']).split('_')
                role = store[0]
                user_id = store[1]
                add_query = "INSERT INTO core.usermodule_userrolemap(user_id, role_id)VALUES((select id from usermodule_usermoduleprofile where user_id = "+str(user_id)+"), (select id from usermodule_organizationrole where role = '"+str(role)+"'))"
                __db_commit_query(add_query)
            elif each['value'] == 0:
                store = str(each['id']).split('_')
                role = store[0]
                user_id = store[1]
                delete_query = "delete from usermodule_userrolemap where user_id = (select id from usermodule_usermoduleprofile where user_id = "+str(user_id)+") and role_id = (select id from usermodule_organizationrole where role = '"+str(role)+"')"
                __db_commit_query(delete_query)

    query = "with t as( select(select user_id from usermodule_usermoduleprofile where id = m.user_id)user_id,role_id from usermodule_userrolemap m), t1 as ( select user_id,role, 1 as status from t,usermodule_organizationrole r where t.role_id = r.id ), t2 as ( select auth_user.id user_id,role from auth_user,usermodule_organizationrole ), all_false as ( select user_id,role from t2 except select user_id,role from t1 ),all_false1 as ( select *,0 as status from all_false ), final_res as ( select * from t1 union all select * from all_false1 ) select user_id,(select username from auth_user where id = user_id)username,(select first_name || ' ' ||last_name from auth_user where id = user_id) fullname,role,status from final_res"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    if not df.empty:
        df = df.pivot_table(index=['user_id','username', 'fullname'], columns='role', values='status').reset_index()
        columns = json.dumps(df.columns.tolist())
        data = json.dumps(df.to_dict(orient='records'))
    else:
        return error_page(request, "No Data Available")

    organization_query = "select id,organization from usermodule_organizations "
    df = pandas.DataFrame()
    df = pandas.read_sql(organization_query,connection)
    org_id = df.id.tolist()
    org_name = df.organization.tolist()
    organization = zip(org_id,org_name)
    print(datetime.now()-start)
    return render(request, "usermodule/user_role_mapping.html", {'data': data,'columns':columns,'organization':organization})



@csrf_exempt
def getUserRoles(request):
    organization = request.POST.get('organization')
    branch = ""
    if branch == ""  and organization == "":
        filter_query = ""
    else:  filter_query = " where "
    if branch !="":
        filter_query += " branch_id = "+str(branch)
    elif organization !="":
        filter_query += " organization_id = "+str(organization)

    

    query = "WITH t AS(SELECT(SELECT user_id FROM usermodule_usermoduleprofile WHERE id = m.user_id)user_id, role_id FROM usermodule_userrolemap m ), t1 AS (SELECT user_id, ROLE, 1 AS status FROM t, usermodule_organizationrole r WHERE t.role_id = r.id), t2 AS (SELECT auth_user.id user_id, ROLE FROM auth_user, usermodule_organizationrole "+str(filter_query)+"), all_false AS (SELECT user_id, ROLE FROM t2 EXCEPT SELECT user_id, ROLE FROM t1), all_false1 AS (SELECT *, 0 AS status FROM all_false), final_res AS (SELECT * FROM t1 UNION ALL SELECT * FROM all_false1) SELECT user_id, (SELECT username FROM auth_user WHERE id = user_id) username, (SELECT first_name || ' ' || last_name FROM auth_user WHERE id = user_id) fullname, ROLE, status FROM final_res"

    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    if not df.empty:
        df = df.pivot_table(index=['user_id', 'username', 'fullname'], columns='role',
                        values='status').reset_index()
        data = json.dumps(df.to_dict(orient='records'))
        columns = json.dumps(df.columns.tolist())
    else:
        data = []
        columns = []
    print(data)
    print (columns)
    return HttpResponse(json.dumps({'data':data,'columns':columns}))

#--------------------Branch Catchment Area ----------------------------

@csrf_exempt
@login_required
def add_children(request):
    id = request.POST.get('id')
    query = "select value,name from geo_cluster where parent = " + str(id) + ""
    all = __db_fetch_values(query)

    list_of_dictionary = []
    for child in all:
        id_ch, name = child[0],child[1]
        query = "select value from geo_cluster where parent =" + str(id_ch) + "limit 1"
        value = __db_fetch_values(query)
        if value:
            true = True
        else:
            true = False
        temp = {"id": id_ch, "text": name, "hasChildren": true, "children": []}
        list_of_dictionary.append(temp)

    return HttpResponse(json.dumps({'id': id, 'list_of_dictionary': list_of_dictionary}))


def get_branch_check_nodes(branch_id):
    query = "select * from branch_catchment_area where branch_id = " + str(branch_id)+" and deleted_at is null"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    check_nodes = df.geoid.tolist()
    return check_nodes


def get_check_nodes( user_id):
    query = "select * from usermodule_catchment_area where user_id = "+str(user_id)+""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    check_nodes = df.geoid.tolist()
    return check_nodes


@login_required
def branch_catchment_tree_test(request, branch_id):
    query = "select * from geo_cluster where parent=-1"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    code = df.value.tolist()
    name = df.name.tolist()
    all = zip(code,name)
    list_of_dictionary = []
    start  = time.time()

    for code,name in all:
        query = "select value from geo_cluster where parent =" + str(code)+ " limit 1"
        df = pandas.read_sql(query, connection)
        if len(df.value.tolist()):
            true = True
        else:
            true = False
        temp = {"id": code, "text": name,"hasChildren":true, "children": []}
        list_of_dictionary.append(temp)
    print list_of_dictionary
    datasource = json.dumps({'list_of_dictionary': list_of_dictionary})

    check_nodes = get_branch_check_nodes(branch_id)
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
    query = "select * from usermodule_branch where id=" + str(branch_id)
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization = df.branch_name.tolist()[0]

    query = "with recursive t as( select value, name, parent from geo_cluster where value in ( select geoid from branch_catchment_area where branch_id = "+str(branch_id)+" and deleted_at is null) union all select geo_cluster.value, geo_cluster.name, geo_cluster.parent from geo_cluster, t where t.parent = geo_cluster.value ) select distinct value, name, parent from t order by value"
    df = pandas.DataFrame()
    df = pandas.read_sql(query,connection)
    parent_list =  df.value.tolist()

    return render(request, "usermodule/branch_catchment_tree_test.html", {'datasource': datasource
        , 'organization_name': organization
        , 'check_nodes': check_nodes,'branch_id':branch_id,'json_content': json_content_dictionary,'parent_list':parent_list})


@login_required
def branch_catchment_data_insert(request):
    result_set = request.POST.get('result_set').split(',')
    branch_id = int(request.POST.get('branch_id'))
    delete_prev_branch_catchment_record(branch_id)
    result_set = list(set(result_set))

    for each in result_set:
        if each:
            query = "INSERT INTO branch_catchment_area (branch_id, geoid,created_at,created_by,updated_at,updated_by) VALUES(" + str(branch_id) + ", " + str(
                each) + ",now(),"+str(request.user.id)+",now(),"+str(request.user.id)+")"
            #database(query)
            __db_commit_query(query)
            # sql = 'refresh materialized view vwunion_mat; refresh materialized view vwbranchcoverage_mat;refresh materialized view vwbranchunioncoverage;'
            # database(sql)
    return HttpResponseRedirect('/usermodule/branch-list/')


def delete_prev_branch_catchment_record(branch_id):
    query = "update branch_catchment_area set deleted_at =now() where branch_id = " + str(branch_id)+" "
    #database(query)
    __db_commit_query(query)

