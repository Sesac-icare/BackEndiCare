from django.urls import path
from .views import OpenPharmacyListAPIView, NearbyPharmacyListAPIView

urlpatterns = [
    path('open/', OpenPharmacyListAPIView.as_view(), name='open-pharmacy-list'),
    path('nearby/', NearbyPharmacyListAPIView.as_view(), name='nearby-pharmacy-list'),
]
