from rest_framework import serializers
from .models import Prescription, Medicine

class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = ['id', 'name', 'dosage', 'quantity']

class PrescriptionSerializer(serializers.ModelSerializer):
    medicines = MedicineSerializer(many=True, read_only=True)
    
    class Meta:
        model = Prescription
        fields = ['id', 'child', 'pharmacy_name', 'prescription_number', 
                'prescription_date', 'medicines', 'created_at']
        read_only_fields = ['child']

class OCRResultSerializer(serializers.Serializer):
    약국명 = serializers.CharField(allow_null=True)
    처방전번호 = serializers.CharField(allow_null=True)
    처방일자 = serializers.CharField(allow_null=True)
    약품명 = serializers.ListField(child=serializers.CharField())
    복용량 = serializers.ListField(child=serializers.CharField())
    수량 = serializers.ListField(child=serializers.IntegerField())

class OCRRequestSerializer(serializers.Serializer):
    image = serializers.ImageField()
    child_id = serializers.IntegerField()
