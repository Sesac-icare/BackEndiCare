from django.db import models

class User(models.Model):
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Child(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children')
    child_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.child_name


class PharmacyEnvelope(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='pharmacy_envelopes')
    pharmacy_name = models.CharField(max_length=255)
    prescription_number = models.CharField(max_length=50, unique=True)
    prescription_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pharmacy_name} - {self.prescription_number}"


class Pharmacy(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    tel = models.CharField(max_length=20)
    fax = models.CharField(max_length=20, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    map_info = models.TextField(blank=True)
    etc = models.TextField(blank=True)
    
    # 운영시간
    mon_start = models.CharField(max_length=4, blank=True)
    mon_end = models.CharField(max_length=4, blank=True)
    tue_start = models.CharField(max_length=4, blank=True)
    tue_end = models.CharField(max_length=4, blank=True)
    wed_start = models.CharField(max_length=4, blank=True)
    wed_end = models.CharField(max_length=4, blank=True)
    thu_start = models.CharField(max_length=4, blank=True)
    thu_end = models.CharField(max_length=4, blank=True)
    fri_start = models.CharField(max_length=4, blank=True)
    fri_end = models.CharField(max_length=4, blank=True)
    sat_start = models.CharField(max_length=4, blank=True)
    sat_end = models.CharField(max_length=4, blank=True)
    sun_start = models.CharField(max_length=4, blank=True)
    sun_end = models.CharField(max_length=4, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['name']),
        ]
