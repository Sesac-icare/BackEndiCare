from django.db import models


class User(models.Model):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Child(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="children")
    child_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.child_name


class PharmacyEnvelope(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="pharmacy_envelopes")
    pharmacy_name = models.CharField(max_length=255)
    prescription_number = models.CharField(max_length=50, unique=True)
    prescription_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pharmacy_name} - {self.prescription_number}"


class Hospital(models.Model):
    ykiho = models.CharField(max_length=100, unique=True)  # 병원 고유 ID
    name = models.CharField(max_length=200)  # 병원명
    address = models.CharField(max_length=500)  # 주소
    phone = models.CharField(max_length=20)  # 전화번호
    department = models.CharField(max_length=1000)  # 진료과목
    latitude = models.FloatField()  # 위도
    longitude = models.FloatField()  # 경도
    
    # 진료시간 정보
    weekday_hours = models.JSONField(null=True)  # 평일 진료시간
    saturday_hours = models.JSONField(null=True)  # 토요일 진료시간
    sunday_hours = models.JSONField(null=True)  # 일요일 진료시간
    
    # 접수시간 정보
    reception_hours = models.JSONField(null=True)  # 접수시간
    
    # 점심시간
    lunch_time = models.JSONField(null=True)
    
    holiday_closed = models.BooleanField(default=True)  # 공휴일 휴무 여부
    
    # 휴무일 정보 추가
    holiday_info = models.JSONField(null=True)  # 공휴일 세부 정보
    sunday_closed = models.BooleanField(default=True)  # 일요일 휴무 여부
    
    hospital_type = models.CharField(max_length=50, null=True)  # 원래 크기로 복구
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return self.name
