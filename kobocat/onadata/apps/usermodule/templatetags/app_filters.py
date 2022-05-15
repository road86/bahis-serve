from django import template
import sys
from onadata.apps.usermodule.models import UserRoleMap

register = template.Library()

@register.filter(name='get_value')
def get_value(array,index):
	for arra in array:
		if int(arra.id) == int(index):
			return arra.oraganization
	return "Not Available"


@register.filter(name='get_roles')
def get_roles(user,role):
	has_role = UserRoleMap.objects.filter(user=user,role=role)
	if has_role:
		return 1
	return 0


@register.filter(name='get_checked')
def get_checked(choice,alist):
	results = map(int, alist)
	if choice in results:
		return 1
	return 0


@register.filter(name='get_checked_string')
def get_checked_string(choice,alist):
	results = map(str, alist)
	if choice in results:
		return 1
	return 0


@register.filter(name='keyvalue')
def keyvalue(dict, key):
    try:
        return dict[key]
    except KeyError:
        return ''
		
