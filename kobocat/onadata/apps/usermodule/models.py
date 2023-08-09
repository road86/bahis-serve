from django.db import models
from django.contrib.auth.models import User

# Create your models here.
from django.db.models import Count




class UserModuleProfile(models.Model):
    user = models.OneToOneField(User)
    expired = models.DateTimeField()
    # The additional attributes we wish to include.
    admin = models.BooleanField(default=False)
    organisation_name = models.ForeignKey('Organizations',blank=True, null=True, on_delete=models.PROTECT)
    mobile_no = models.CharField(max_length = 100)
    role = models.ForeignKey('OrganizationRole', related_name='role_name',
                                    on_delete=models.CASCADE)

    # Override the __unicode__() method to return out something meaningful!
    def __str__(self):
        return self.user.username

    class Meta:
       app_label = 'usermodule'


class UserPasswordHistory(models.Model):
    user_id = models.IntegerField()
    password = models.CharField(max_length=150)
    # designation = models.CharField(max_length=200)
    date = models.DateTimeField()

    # Override the __unicode__() method to return out something meaningful!
    def __str__(self):
        return self.user


class UserFailedLogin(models.Model):
    user_id = models.IntegerField()
    login_attempt_time= models.DateTimeField(auto_now_add=True)


    def was_username(self):
        current_user= User.objects.get(id=self.user_id)
        return current_user;
    was_username.short_description = 'Username'



class Organizations(models.Model):
    organization = models.CharField(max_length=150)
    parent_organization = models.ForeignKey('Organizations',blank=True, null=True,related_name='parent_org', on_delete=models.PROTECT)
    address = models.TextField(null=True,blank=True)
    # Override the __unicode__() method to return out something meaningful!
    def __str__(self):
        return self.organization

    class Meta:
       app_label = 'usermodule'


class MenuItem(models.Model):
    title = models.CharField(max_length=150)
    url = models.CharField(max_length=150)
    list_class = models.CharField(max_length=150)
    icon_class = models.CharField(max_length=150)
    parent_menu = models.ForeignKey('MenuItem',blank=True, null=True, on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)
    def __str__(self):
        return self.title

    

# Role + Organization model
class OrganizationRole(models.Model):
    organization = models.ForeignKey('Organizations',related_name='role_organization_name', on_delete=models.CASCADE)
    role = models.CharField(max_length=150)
    parent_role = models.ForeignKey('OrganizationRole', blank=True, null=True,related_name='role_parent_role_name', on_delete=models.CASCADE)
    can_configure = models.BooleanField(default=False)

    class Meta:
        unique_together = ('organization', 'role',)

    def __str__(self):
        return self.role
        #return self.organization.organization + " ==> "+ self.role

# Role-Menu Permission Mapping
class MenuRoleMap(models.Model):
    role = models.ForeignKey('OrganizationRole',related_name='model_map_role', on_delete=models.CASCADE)
    menu = models.ForeignKey('MenuItem',related_name='model_map_menu', on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('role', 'menu',)
    
    def __str__(self):
        return self.role

    def __unicode__(self):
        return '%s' % (self.role)




# User-Role Permission Mapping
class UserRoleMap(models.Model):
    #user = models.ForeignKey('UserModuleProfile',related_name='usermodule_role', on_delete=models.CASCADE)
    user = models.ForeignKey('auth.User',related_name='user_role', on_delete=models.CASCADE)
    role = models.ForeignKey('OrganizationRole',related_name='map_user_role', on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('user','role',)
    
    def __str__(self):
        return self.user        


#branch
class Branch(models.Model):
    branch_name = models.CharField(max_length=150)
    organization = models.ForeignKey('Organizations', blank=True, null=True, related_name='org',
                                            on_delete=models.PROTECT)

    def __str__(self):
        return self.branch_name

    class Meta:
        app_label = 'usermodule'


#User-Branch Mapping
class UserBranch(models.Model):
    user = models.ForeignKey(User, related_name='user_branch_map', on_delete=models.CASCADE)
    branch= models.ForeignKey('Branch',blank=True, null=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.branch.branch_name

    class Meta:
        managed = False
        db_table = 'usermodule_userbranchmap'






