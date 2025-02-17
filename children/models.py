from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

class Children(models.Model):
    child_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    child_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'children'
        unique_together = ['user', 'child_name']

    def __str__(self):
        return self.child_name 