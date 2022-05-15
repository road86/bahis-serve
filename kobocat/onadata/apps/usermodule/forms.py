from django.contrib.auth.hashers import make_password, check_password
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory,Organizations,MenuItem
from django.contrib.auth.models import User
from django import forms
from datetime import datetime, timedelta
from onadata.apps.usermodule.models import OrganizationRole
from onadata.apps.usermodule.models import MenuRoleMap
from onadata.apps.usermodule.models import UserRoleMap
from django.utils.translation import ugettext as _, ugettext_lazy
from onadata.apps.usermodule.helpers import COUNTRIES

class UserForm(forms.ModelForm):
    password = forms.CharField(label='Create a password',widget=forms.PasswordInput(),min_length=4)
    password_repeat = forms.CharField(label='Confirm your password',widget=forms.PasswordInput())
    email = forms.EmailField(required=False)
    last_name = forms.CharField(required=False)
    username = forms.CharField(required = True,help_text='',max_length=20,widget=forms.TextInput(attrs={'pattern': '[a-z_0-9]+','title':'only lowercase letter, numbers and underscore(_) is allowed. example: user_2009'}))
    # date_joined = forms.CharField(widget=forms.HiddenInput(),initial=datetime.now()) 
    def clean_password_repeat(self):
        password1 = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password_repeat')

        if password1 and password1!=password2:
            raise forms.ValidationError('Passwords Do not match')
        return self.cleaned_data

    class Meta:
        model = User
        # fields = ('username', 'email', 'password','user_permissions','is_staff','is_active','is_superuser','date_joined','groups')
        fields = ('username', 'first_name', 'last_name', 'email', 'password') # ,'is_superuser' 'date_joined',


class UserEditForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    username = forms.CharField(help_text='',max_length=10)
    last_name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ('username','first_name', 'last_name', 'email') # ,'is_superuser','date_joined'
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(UserEditForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['readonly'] = 'true'
        

class UserProfileForm(forms.ModelForm):
    admin = forms.BooleanField(label="Make this User Admin",widget=forms.CheckboxInput(),required=False)
    organisation_name = forms.ModelChoiceField(label='Organisation Name',required=True,queryset=Organizations.objects.all())
    mobile_no = forms.CharField(label="mobile_no",required=False)
    role = forms.ModelChoiceField(label='Role Name', required=True,
                                               queryset=OrganizationRole.objects.all(),
                                               empty_label="Select an Role")

    class Meta:
        model = UserModuleProfile
        #fields = ('admin','employee_id','organisation_name','country','designation','psu')
        fields = ('admin','organisation_name','mobile_no','role')


    def __init__(self, *args, **kwargs):
        admin_check = kwargs.pop('admin_check', False)
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['organisation_name'].empty_label = None
        if not admin_check:
            del self.fields['admin']

class OrganizationForm(forms.ModelForm):
    organization = forms.CharField(label='Organization',required=True)
    address = forms.CharField(widget=forms.TextInput,required=False)
    # parent_organization = forms.ModelChoiceField(label='Parent Organization',required=True,queryset=Organizations.objects.all(),empty_label="Select an Organization")
    class Meta:
        model = Organizations
        fields = ('organization','parent_organization','address')





# Roles based on organization Form
class OrganizationRoleForm(forms.ModelForm):
    organization = forms.ModelChoiceField(label='Organization',required=True,queryset=Organizations.objects.all(),empty_label="Select an Organization")
    role = forms.CharField(label='Role',required=True)
    parent_role = forms.ModelChoiceField(label='OrganizationRole', required=False, queryset=OrganizationRole.objects.all(),
                                          empty_label="Select a parent role")
    can_configure = forms.BooleanField(label='Can Configure', required=False)

    class Meta:
        model = OrganizationRole
        fields = ('organization','role','parent_role','can_configure')


class ChangePasswordForm(forms.Form):
    username = forms.CharField(label="Username",required=True)
    old_password = forms.CharField(label="Old",required=True,widget=forms.PasswordInput(),min_length=4)
    new_password = forms.CharField(label="New",required=True,widget=forms.PasswordInput(),min_length=4)
    retype_new_password = forms.CharField(label="Retype new",required=True,widget=forms.PasswordInput())
    def clean_retype_new_password(self):
        old_password = self.cleaned_data.get('old_password')
        new_password = self.cleaned_data.get('new_password')
        retype_new_password = self.cleaned_data.get('retype_new_password')
        username = self.cleaned_data.get('username')

        if old_password and new_password == old_password:
            raise forms.ValidationError('New Password Cannot be same as old password')

        if new_password and new_password!=retype_new_password:
            raise forms.ValidationError('Passwords Do not match')

        # check password history (last 25) if it already existed before
        #get current user id
        try:
            current_user_id = User.objects.get(username=username).pk
        except User.DoesNotExist:
            raise forms.ValidationError('Username you entered is incorrect')
        # get list of last 24 password
        count_unusable_recent_password = 24
        password_list = UserPasswordHistory.objects.filter(user_id=current_user_id).order_by('-date').values('password')[:count_unusable_recent_password][::-1]

        for i in password_list:
            flag = check_password(new_password,i['password'])
            if(flag):
                raise forms.ValidationError('You cannot reuse your last '+str(count_unusable_recent_password)+ 'password as your new password')

        # UserModuleProfile.objects.filter(position='Junior Software Engineer').order_by('-id').values()[:3][::-1]
        # UserPasswordHistory.objects.filter(user_id=5).order_by('-date').values()[:2][::-1]
        return self.cleaned_data


    def __init__(self, *args, **kwargs):
        logged_in_user = kwargs.pop('logged_in_user', None)
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        if logged_in_user:
            self.fields['username'].initial = logged_in_user


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(label="New",required=True,widget=forms.PasswordInput(),min_length=4)
    retype_new_password = forms.CharField(label="Retype new",required=True,widget=forms.PasswordInput())
    def clean_retype_new_password(self):
        new_password = self.cleaned_data.get('new_password')
        retype_new_password = self.cleaned_data.get('retype_new_password')
        
        if new_password and new_password!=retype_new_password:
            raise forms.ValidationError('Passwords Do not match')

        return self.cleaned_data   
        

class MenuForm(forms.ModelForm):
    title = forms.CharField(label="Title",required=True)
    url = forms.CharField(label="Url",required=True)
    list_class = forms.CharField(label="Menu List Class")
    icon_class = forms.CharField(label="Menu Icon Class")
    parent_menu = forms.ModelChoiceField(label='Parent Menu',required=False,queryset=MenuItem.objects.all(),empty_label=None)

    class Meta:
        model = MenuItem
        fields = ('title','url','list_class','icon_class','parent_menu','sort_order')

# Roles based on organization Form
class RoleMenuMapForm(forms.ModelForm):
    class Meta:
        model = MenuRoleMap
        fields = ('role', 'menu')


# Roles based on organization Form
class UserRoleMapForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=UserModuleProfile.objects.all(), empty_label="(Nothing)")
    role = forms.ModelChoiceField(queryset=OrganizationRole.objects.all(), empty_label="(Nothing)")
    class Meta:
        model = UserRoleMap
        fields = ('user', 'role')
        # widgets = {
        #     'user': forms.widgets.CheckboxSelectMultiple(),
        #     'role': forms.widgets.CheckboxSelectMultiple(),
        # }

    # def __init__(self, *args, **kwargs):
    #     super(UserRoleMapForm, self).__init__(*args, **kwargs)
    #     self.fields['user'].widget = forms.ModelMultipleChoiceField(
    #         widget=forms.CheckboxSelectMultiple(),
    #         queryset=UserModuleProfile.objects.all()
        # )
        # self.fields['role'].widget = forms.ModelMultipleChoiceField(
        #     widget=forms.CheckboxSelectMultiple(),
        #     queryset=OrganizationRole.objects.all()
        # )

class UserRoleMapfForm(forms.Form):
    # user = forms.ModelChoiceField(queryset=UserModuleProfile.objects.all(), empty_label="(Nothing)")
    user = forms.CharField(label='user', widget=forms.HiddenInput())
    role = forms.ModelChoiceField(queryset=OrganizationRole.objects.all(), empty_label=None,widget=forms.CheckboxSelectMultiple())
    

PERM_CHOICES = (
        ('view', ugettext_lazy('Can view')),
        ('edit', ugettext_lazy('Can edit')),
        ('report', ugettext_lazy('Can submit to')),
    )
class ProjectPermissionForm(forms.Form):
    user = forms.CharField(label='user', widget=forms.HiddenInput())
    # role = forms.ModelChoiceField(queryset=OrganizationRole.objects.all(), empty_label=None,widget=forms.CheckboxSelectMultiple())
    perm_type = forms.ChoiceField(choices=PERM_CHOICES, widget=forms.CheckboxSelectMultiple())
