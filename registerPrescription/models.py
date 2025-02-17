from django.db import models
from django.conf import settings
from children.models import Children

class Prescription(models.Model):
    prescription_id = models.AutoField(primary_key=True)
    child = models.ForeignKey(Children, on_delete=models.CASCADE, related_name='prescriptions', verbose_name='아동')
    pharmacy_name = models.CharField(max_length=255, verbose_name='약국명')
    prescription_number = models.CharField(max_length=50, verbose_name='처방전 번호')
    prescription_date = models.DateField(verbose_name='처방일자')
    pharmacy_address = models.CharField(max_length=255, verbose_name='약국주소', blank=True)
    total_amount = models.CharField(max_length=50, verbose_name='총액', blank=True)
    duration = models.CharField(max_length=10, verbose_name='투약일수', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '처방전'
        verbose_name_plural = '처방전 목록'
        db_table = 'prescriptions'

    def __str__(self):
        return f"{self.child.child_name}의 처방전 ({self.prescription_date})"

class Medicine(models.Model):
    medicine_id = models.AutoField(primary_key=True)
    prescription = models.ForeignKey(
        Prescription, 
        on_delete=models.CASCADE, 
        related_name='medicines', 
        db_column='prescription_id'
    )
    name = models.CharField(max_length=255, verbose_name='약품명', db_column='medicine_name')
    dosage = models.CharField(max_length=50, verbose_name='복용량')
    frequency = models.IntegerField(verbose_name='투약횟수')
    duration = models.IntegerField(verbose_name='투약일수')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = '처방약'
        verbose_name_plural = '처방약 목록'
        db_table = 'medicines'

    def __str__(self):
        return f"{self.name} (복용량: {self.dosage})"