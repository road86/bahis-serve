from django.conf import settings
from django.contrib.sites.models import Site
from onadata.apps.usermodule.models import MenuItem, UserModuleProfile
from onadata.apps.usermodule.models import MenuRoleMap, UserRoleMap
from onadata.apps.usermodule.views import __db_fetch_single_value
import sys


# print "Branch Exist =="+ str(settings.IS_EXIST_BRANCH)
# EXIST_BRANCH = settings.IS_EXIST_BRANCH
def site_name(request):
    site_id = getattr(settings, 'SITE_ID', None)
    try:
        site = Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        site_name = 'example.org'
    else:
        site_name = site.name
    return {'SITE_NAME': site_name}


def additional_menu_items(request):
    user = request.user._wrapped if hasattr(request.user, '_wrapped') else request.user
    menu_items = []
    sub_menu_items = []
    if not request.user.id == None:
        current_user = UserModuleProfile.objects.filter(user=request.user)
        if current_user:
            current_user = current_user[0]
            # print "Current user =="+str(request.user)
            if request.user.is_superuser:
                menu_items = MenuItem.objects.exclude(parent_menu__isnull=False)
                sub_menu_items = MenuItem.objects.exclude(parent_menu__isnull=True)
                if settings.IS_EXIST_BRANCH == False:
                    menu_items = menu_items.exclude(url__exact='/usermodule/branch-list/')
                    sub_menu_items = sub_menu_items.exclude(url__exact='/usermodule/branch-list/')
            else:
                admin_menu = 0
                roles_list = UserRoleMap.objects.filter(user=request.user).values('role')
                for role in roles_list:
                    alist = MenuRoleMap.objects.filter(role=role['role']).values('menu')
                    mist = []
                    for i in alist:
                        mist.append(i['menu'])
                    role_menu_list = MenuItem.objects.filter(pk__in=mist).exclude(parent_menu__isnull=False)
                    role_submenu_list = MenuItem.objects.filter(pk__in=mist).exclude(parent_menu__isnull=True)
                    if settings.IS_EXIST_BRANCH == False:
                        role_menu_list = role_menu_list.exclude(url__exact='/usermodule/branch-list/')
                        role_submenu_list = role_submenu_list.exclude(url__exact='/usermodule/branch-list/')
                    menu_items.extend(role_menu_list)
                    sub_menu_items.extend(role_submenu_list)
        else:
            menu_items = MenuItem.objects.exclude(parent_menu__isnull=False)
            sub_menu_items = MenuItem.objects.exclude(parent_menu__isnull=True)
            if settings.IS_EXIST_BRANCH == False:
                menu_items = menu_items.exclude(url__exact='/usermodule/branch-list/')
                sub_menu_items = sub_menu_items.exclude(url__exact='/usermodule/branch-list/')

    # print("MENU")
    # print(menu_items)
    # print("SUBMENU")
    # print(sub_menu_items)
    menu_items = list(set(menu_items))
    menu_items = sorted(menu_items, key=lambda x: x.sort_order)
    sub_menu_items = list(set(sub_menu_items))
    sub_menu_items = sorted(set(sub_menu_items), key=lambda x: x.sort_order)

    return {'main_menu_items': menu_items, 'sub_menu_items': list(sub_menu_items)}


def can_configure(request):
    user = request.user._wrapped if hasattr(request.user, '_wrapped') else request.user
    if not request.user.id == None:
        can_conf = __db_fetch_single_value("""
        select can_configure from core.usermodule_organizationrole uo where id = (select role_id from core.usermodule_userrolemap uu where user_id = %s limit 1)
        """ % request.user.id)
        return {'can_conf': can_conf}
    else:
        return {'can_conf': False}


def is_admin(request):
    admin_menu = 0
    user = request.user._wrapped if hasattr(request.user, '_wrapped') else request.user
    if not user.is_anonymous():
        current_user = UserModuleProfile.objects.filter(user=user)
        if current_user:
            current_user = current_user[0]
            if current_user.admin:
                admin_menu = 1
            else:
                admin_menu = 0
        else:
            admin_menu = 1
    return {'admin_menu': admin_menu}


def care_viewer(request):
    admin_menu = 0
    care_usa = 0
    care_bd = 0
    care_np = 0
    kobo_priv = 0
    user = request.user._wrapped if hasattr(request.user, '_wrapped') else request.user

    # print user.username
    if not user.is_anonymous():
        current_user = UserModuleProfile.objects.filter(user=user).first()
        if current_user:
            organization = current_user.organisation_name.organization
            # current_user = current_user[0]
            if organization == 'CARE Nepal':
                care_np = 1
            if organization == 'CARE Bangladesh':
                care_bd = 1
        else:
            care_usa = 1
            kobo_priv = 1
    return {'care_np': care_np,
            'care_bd': care_bd,
            'care_usa': care_usa,
            'kobo_priv': kobo_priv}
