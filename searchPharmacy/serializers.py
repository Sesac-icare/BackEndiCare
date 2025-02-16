from rest_framework import serializers
from .models import Pharmacy
from datetime import datetime

class PharmacySerializer(serializers.ModelSerializer):
    distance = serializers.FloatField()
    operating_hours = serializers.SerializerMethodField()
    current_status = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacy
        fields = ['name', 'address', 'tel', 'distance', 'operating_hours', 'current_status']

    def get_operating_hours(self, obj):
        return {
            "월": self.format_time(obj.mon_start, obj.mon_end),
            "화": self.format_time(obj.tue_start, obj.tue_end),
            "수": self.format_time(obj.wed_start, obj.wed_end),
            "목": self.format_time(obj.thu_start, obj.thu_end),
            "금": self.format_time(obj.fri_start, obj.fri_end),
            "토": self.format_time(obj.sat_start, obj.sat_end),
            "일": self.format_time(obj.sun_start, obj.sun_end),
        }

    def get_current_status(self, obj):
        now = datetime.now()
        weekday = now.weekday()
        current_time = now.strftime('%H%M')

        time_mapping = {
            0: (obj.mon_start, obj.mon_end),
            1: (obj.tue_start, obj.tue_end),
            2: (obj.wed_start, obj.wed_end),
            3: (obj.thu_start, obj.thu_end),
            4: (obj.fri_start, obj.fri_end),
            5: (obj.sat_start, obj.sat_end),
            6: (obj.sun_start, obj.sun_end),
        }

        start_time, end_time = time_mapping[weekday]
        
        if not (start_time and end_time):
            return "정보없음"

        if start_time <= current_time <= end_time:
            return f"영업중 ({self.format_time(start_time, end_time)})"
        else:
            return f"영업종료 ({self.format_time(start_time, end_time)})"

    def format_time(self, start, end):
        if not (start and end):
            return "정보없음"
        return f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]}" 