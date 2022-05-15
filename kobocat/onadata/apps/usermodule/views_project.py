import json
from django.http import (HttpResponseRedirect, HttpResponse,HttpResponseBadRequest,HttpResponseForbidden)
from django.shortcuts import render,render_to_response, get_object_or_404
from django.template import RequestContext,loader
from django.db import connection
from onadata.apps.main.forms import QuickConverter,QuickConverterFile,QuickConverterURL
from onadata.apps.usermodule.forms import ProjectPermissionForm

from django.contrib.auth.models import User
from onadata.apps.logger.models import Instance, XForm #, Attachment
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from onadata.libs.utils.user_auth import set_profile_data

from onadata.apps.usermodule.views import get_recursive_organization_children
from onadata.apps.usermodule.models import UserModuleProfile, Organizations
from django.contrib.auth.decorators import login_required, user_passes_test
from guardian.shortcuts import assign_perm, remove_perm, get_users_with_perms
from django.forms.formsets import formset_factory

from onadata.apps.main.models import UserProfile, MetaData
from onadata.libs.utils.user_auth import has_permission, has_edit_permission
from django.core.urlresolvers import reverse
from onadata.apps.logger.views import download_jsonform
from onadata.apps.viewer.models.export import Export
from onadata.libs.utils.export_tools import (
    generate_export,
    should_create_new_export,
    kml_export_data,
    newset_export_for)
from django.db.models import Q

def get_permissions(user_list,xform):
    """
    Based on usermodule users list and xform,
    gets each users view, edit or submit permission on
    xform and creates a initial list which can be used 
    to initialize the formset for assigning/removing form 
    permissions.
    """
    initial_list = []
    for usermodule_user in user_list:
        perm_list = []
        if usermodule_user.user.has_perm('view_xform', xform):
            perm_list.append('view')
        if usermodule_user.user.has_perm('change_xform', xform):
            perm_list.append('edit')
        if usermodule_user.user.has_perm('report_xform', xform):
            perm_list.append('report')	
        initial_list.append({'user': usermodule_user.user.id,'perm_type': perm_list,'username':usermodule_user.user.username })
    return initial_list


def get_own_and_partner_orgs_usermodule_users(request):
    """
    Based on currently logged in user, shows the 
    usermodule users who belong to the organization of 
    currently logged in user or his organization's 
    partner organization(s). Returns all usermodule users 
    if current user is a django superuser.
    """
    all_organizations = []
    user_list = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
        user_list = UserModuleProfile.objects.all()
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name,[])
        user_list = UserModuleProfile.objects.filter(organisation_name__in=all_organizations)
    return user_list


@login_required
def adjust_user_project_map(request, id_string, form_owner_user):
    """
    Adjusts the view, edit and submit 
    permission of a project/form to the
    usermodule users of currently logged in
    user's organization and its partner 
    organization.
    N.B. When edit permission is assigned
    view permission is also assigned.
    """
    data = {}
    user_list = get_own_and_partner_orgs_usermodule_users(request)
    xform = get_object_or_404(XForm,user__username__iexact=form_owner_user,id_string__exact=id_string)
    initial_list = get_permissions(user_list,xform)
    PermisssionFormSet = formset_factory(ProjectPermissionForm,max_num=len(user_list))
    permisssion_form_set = PermisssionFormSet(initial=initial_list)
    data.update({
        'xform':xform,
        'permisssion_form_set':permisssion_form_set,
    })
    if request.method == 'POST':
        permisssion_form_set = PermisssionFormSet(data=request.POST)
        for idx,user_role_form in enumerate(permisssion_form_set):
            u_id = request.POST['form-'+str(idx)+'-user']
            mist = initial_list[idx]['perm_type']
            current_user = User.objects.get(pk=u_id)
            results = map(str, request.POST.getlist('perm-'+str(idx+1)))
            for result in results:
            	if result == 'view' and not current_user.has_perm('view_xform', xform):
                    assign_perm('view_xform', current_user, xform)
                elif result == 'report' and not current_user.has_perm('report_xform', xform):
            		assign_perm('report_xform', current_user, xform)
            	elif result == 'edit' and not current_user.has_perm('change_xform', xform):	
            		assign_perm('change_xform', current_user, xform)
            		if not current_user.has_perm('view_xform', xform):
            			assign_perm('view_xform', current_user, xform)
            
            deleter = list(set(['edit', 'view', 'report']) - set(results))
            for delete_item in deleter:
                if delete_item == 'view' and current_user.has_perm('view_xform', xform) and not current_user.has_perm('change_xform', xform):
                    remove_perm('view_xform', current_user, xform)
                elif delete_item == 'report' and current_user.has_perm('report_xform', xform):
	                remove_perm('report_xform', current_user, xform)
                elif delete_item == 'edit' and current_user.has_perm('change_xform', xform):	
                    remove_perm('change_xform', current_user, xform)
            message = "Permissions Saved"
            initial_list = get_permissions(user_list,xform)
            permisssion_form_set = PermisssionFormSet(initial=initial_list)
            data.update({
            	'message':message,
		        'xform':xform,
		        'permisssion_form_set':permisssion_form_set,
		    })
    return render(request, "usermodule/user_project_map.html", data)


def get_viewable_projects(request):
    """
    Returns the list of projects/forms 
    which are created or shared to the currently
    logged in user.
    """
    content_user = get_object_or_404(User, username__iexact=request.user.username)
    form = QuickConverter()
    data = {'form': form}
    content_user = request.user
    all_forms = content_user.xforms.count()
    xforms = XForm.objects.filter(user=content_user)\
        .select_related('user', 'instances')
    user_xforms = xforms
    xfct = ContentType.objects.get(app_label='logger', model='xform')
    xfs = content_user.userobjectpermission_set.filter(content_type=xfct)
    shared_forms_pks = list(set([xf.object_pk for xf in xfs]))
    forms_shared_with = XForm.objects.filter(
        pk__in=shared_forms_pks).exclude(user=content_user)\
        .select_related('user')
    published_or_shared = XForm.objects.filter(
        pk__in=shared_forms_pks).select_related('user')
    xforms_list = [
        {
            'id': 'published',
            'xforms': user_xforms,
            'title': _(u"Published Forms"),
            'small': _("Export, map, and view submissions.")
        },
        {
            'id': 'shared',
            'xforms': forms_shared_with,
            'title': _(u"Shared Forms"),
            'small': _("List of forms shared with you.")
        },
        {
            'id': 'published_or_shared',
            'xforms': published_or_shared,
            'title': _(u"Published Forms"),
            'small': _("Export, map, and view submissions.")
        }
    ]
    
    new_list = []
    for xform_list in xforms_list:
    	if xform_list['xforms'] not in new_list:
    		new_list.extend(xform_list['xforms'])
    xforms_list = list(set(new_list))

    return xforms_list

def user_viewable_projects(request):
    """
    Shows the list of projects/forms 
    which are created or shared to the currently
    logged in user. By clicking on a
    project/form item page is redirected
    to that projects form view, edit and submit
    permission adjustment screen.
    """
    data = {}
    xforms_list = get_viewable_projects(request)
    data.update({
        'xforms_list': xforms_list,
    })
    return render(request, "usermodule/viewable_projects.html", data)


@login_required
def generate_pivot(request, username, id_string, **kwargs):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    data = {
        'owner': owner,
        'xform': xform
    }
    return render(request,'pivot_table.html',data);


def custom_project_window(request, username, id_string,**kwargs):
    """
    Replaces the default kobo project window.
    Creates a one page solution with one page view.
    """
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, id_string__exact=id_string, user=owner)
    if not has_permission(xform, owner, request):
        return HttpResponseForbidden(_(u'Not shared.'))

    user_list = get_own_and_partner_orgs_usermodule_users(request)
    username_list = [str(custom_user.user.username) for custom_user in user_list ]
    username_list.append(str(request.user.username))
    # data grid view part
    data = {
        'owner': owner,
        'xform': xform,
        'form_map_url': '/'+owner.username+'/forms/'+xform.id_string+'/map',
        'user_list': username_list
    }

    # start: export part
    export_type = 'xls'
    
    if export_type == Export.GDOC_EXPORT:
        redirect_url = reverse(
            export_list,
            kwargs={
                'username': username, 'id_string': id_string,
                'export_type': export_type})
        token = _get_google_token(request, redirect_url)
        if isinstance(token, HttpResponse):
            return token

    default_fields_query = "select default_fields from export_default_parent where id_string = '" + id_string + "'"
    cursor = connection.cursor()
    cursor.execute(default_fields_query)
    default_fields_data = cursor.fetchone()

    dictlist = []
    if default_fields_data is not None:
        sorted_keys = sorted(list(default_fields_data[0].keys()))
        print type(sorted_keys)
        for value in sorted_keys:
            dictlist.append(str(default_fields_data[0][value]))
    print "Here --1"
    
    if export_type == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform=xform):
            return HttpResponseForbidden(_(u'No XLS Template set.'))
    # Get meta and token
    export_token = request.GET.get('token')
    export_meta = request.GET.get('meta')
    options = {
        'meta': export_meta,
        'token': export_token,
    }

    export_type_zip = 'zip'
    if export_type_zip == Export.GDOC_EXPORT:
        redirect_url = reverse(
            export_list,
            kwargs={
                'username': username, 'id_string': id_string,
                'export_type': export_type_zip})
        token = _get_google_token(request, redirect_url)
        if isinstance(token, HttpResponse):
            return token
    print "Here --12"
    if export_type_zip == Export.EXTERNAL_EXPORT:
        # check for template before trying to generate a report
        if not MetaData.external_export(xform=xform):
            return HttpResponseForbidden(_(u'No XLS Template set.'))
    #code is commented to stop auto export generation
    # if should_create_new_export(xform, export_type):
    #     try:
    #         create_async_export(
    #             xform, export_type, query=None, force_xlsx=True,
    #             options=options)
    #     except Export.ExportTypeError:
    #         return HttpResponseBadRequest(
    #             _("%s is not a valid export type" % export_type))

    metadata = MetaData.objects.filter(xform=xform,
                                       data_type="external_export")\
        .values('id', 'data_value')

    for m in metadata:
        m['data_value'] = m.get('data_value').split('|')[0]

    #tab_selection = '#' + request.GET.get('tab_selection','grid')
    tab_selection = '#' + request.GET.get('tab_selection','data_table')
#    print tab_selection
    data.update({
        'username': owner.username,
         'xform': xform,
        'export_type': export_type,
        'export_type_zip': export_type_zip,
        'export_type_name': Export.EXPORT_TYPE_DICT[export_type],
        'export_type_name_zip': Export.EXPORT_TYPE_DICT[export_type_zip],
        'exports': Export.objects.filter(Q(xform=xform, export_type='xls')|Q(xform=xform, export_type='csv')).order_by('-created_on'),
        'exports_zip': Export.objects.filter(xform=xform, export_type='zip').order_by('-created_on'),
        'metas': metadata,
        'tab_selection': tab_selection,
	'default_fields_data': dictlist
    })
    # end: export part
    print "Here --13"
    # start: image gallery part
    # instances = Instance.objects.filter(xform=xform).values('id')
    # instances_list = [instance['id'] for instance in instances]
    # attachments = Attachment.objects.filter(instance__in=instances_list,mimetype__icontains='image').values('media_file')
    # image_list = []
    # for i in attachments:
    #     image = {}
    #     image['url'] = request.build_absolute_uri('/media/'+i['media_file'])
    #     image['title'] = i['media_file'][i['media_file'].rfind('/')+1:]
    #     image_list.append(image)
    # data.update({
    #     'image_list': image_list,
    # })
    # end: image gallery part
    return render(request, "usermodule/custom_project_window.html", data)

#chart related functions
def chart_view(request):
    reportData = {}
    if request.is_ajax():
        
        cur_form_id = request.POST.get('form_id',11)
        time_interval = request.POST.get('int_time',7)

        results = []
        c = connection.cursor()
        try:
            c.execute("BEGIN")
            c.callproc("get_form_chart_data",(cur_form_id,'filter',time_interval))
            results = c.fetchone()
            c.execute("COMMIT")
        finally:
            c.close()
        output = json.dumps(results)
        return HttpResponse(output,content_type='application/json'); 
    return HttpResponse("No Ajax request..")
