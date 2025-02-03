from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    term_agreed = models.BooleanField(default=False)  # 개인정보 동의 필드 추가

    def __str__(self):
        return self.user.username
