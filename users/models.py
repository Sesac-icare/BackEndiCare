from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    term_agreed = models.BooleanField(default=False)  # 개인정보 동의 필드 추가
    latitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    longitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)

    def __str__(self):
        return self.user.username

    @property
    def username(self):
        return self.user.username

# -----------------------------------------------------

# from django.contrib.auth.models import AbstractUser
# from django.db import models

# class CustomUser(AbstractUser):
#     email = models.EmailField(unique=True)
    
#     USERNAME_FIELD = 'email'
#     REQUIRED_FIELDS = ['username']