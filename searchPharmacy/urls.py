from django.urls import path
from .views import PharmacyListAPIView

urlpatterns = [
    path('pharmacies/', PharmacyListAPIView.as_view(), name='pharmacy-list'),
]
