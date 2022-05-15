from django.contrib import admin
from django.db.models import Count
from onadata.apps.usermodule.models import UserModuleProfile,UserPasswordHistory,UserFailedLogin


class UserFailedLoginAdmin(admin.ModelAdmin):
    list_display = ['was_username', 'login_attempt_time']
    ordering = ['user_id','login_attempt_time']
    # query_dict = UserFailedLogin.objects.values('user_id').annotate(dcount=Count('user_id'))
    # list_display = ('dcount',)
    #
    # def dcount(self, obj):
    #    return obj.dcount
    #
    # def get_queryset(self, request):
    #    # qs = UserFailedLogin.objects.values('user_id').annotate(dcount=Count('user_id'))
    #    qs = UserFailedLogin.objects.annotate(dcount=Count('user_id'))
    #    return qs
    #
    # def dcount(self, inst):
    #     return inst.dcount
    # dcount.short_description  = 'Attempts'


# Register your models here.
admin.site.register(UserFailedLogin,UserFailedLoginAdmin)
# admin.site.register(UserModuleProfile)
# admin.site.register(UserModuleProfile)
