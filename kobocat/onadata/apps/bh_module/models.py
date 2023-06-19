from django.db import models
from django.contrib.auth.models import User

class DeskVersion(models.Model):
    user = models.ForeignKey(User)
    desk_version = models.CharField(max_length=20)
    instance_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table="desk_version"


    def __str__(self):
        return self.desk_version
