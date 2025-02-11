from django.db import models
from users.models import User
from django.conf import settings
# from children.models import Children

class Children(models.Model):
    child_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    child_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'children' 

class Prescription(models.Model):
    child = models.ForeignKey(Children, on_delete=models.CASCADE, related_name='prescriptions', verbose_name='아동')
    pharmacy_name = models.CharField(max_length=255, verbose_name='약국명')
    prescription_number = models.CharField(max_length=50, unique=True, verbose_name='처방전 번호')
    prescription_date = models.DateField(verbose_name='처방일자')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '처방전'
        verbose_name_plural = '처방전 목록'
        db_table = 'prescriptions'

    def __str__(self):
        return f"{self.child.name}의 처방전 ({self.prescription_date})"

class Medicine(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='medicines', db_column='envelope_id')
    name = models.CharField(max_length=255, verbose_name='약품명', db_column='medicine_name')
    dosage = models.CharField(max_length=50, verbose_name='복용량')
    quantity = models.IntegerField(verbose_name='수량')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = '처방약'
        verbose_name_plural = '처방약 목록'
        db_table = 'medicines'

    def __str__(self):
        return f"{self.name} (복용량: {self.dosage}, 수량: {self.quantity})"

class PharmacyEnvelope(models.Model):
    envelope_id = models.AutoField(primary_key=True)
    child = models.ForeignKey(Children, on_delete=models.CASCADE)
    pharmacy_name = models.CharField(max_length=255)
    prescription_number = models.CharField(max_length=50, unique=True)
    prescription_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pharmacy_envelopes'

from django.db import models
from django.conf import settings

# class Children(models.Model):
#     child_id = models.AutoField(primary_key=True)
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     child_name = models.CharField(max_length=100)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         db_table = 'children' 