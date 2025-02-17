from django.contrib import admin
from .models import Prescription, Medicine

class MedicineInline(admin.TabularInline):
    model = Medicine
    extra = 0

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['child', 'pharmacy_name', 'prescription_number', 
                   'prescription_date', 'created_at']
    list_filter = ['prescription_date', 'created_at', 'pharmacy_name']
    search_fields = ['prescription_number', 'pharmacy_name', 'child__name']
    inlines = [MedicineInline]

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name', 'dosage', 'frequency', 'duration', 'prescription']
    list_filter = ['created_at']
    search_fields = ['name']
