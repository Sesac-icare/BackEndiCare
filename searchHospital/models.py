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
