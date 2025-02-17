from django.urls import path
from .views import HospitalSearchView, OpenHospitalSearchView, NearbyPharmacyView

urlpatterns = [
    # 병원 검색 API
    path('search/', HospitalSearchView.as_view(), name='hospital-search'),
    path('open/', OpenHospitalSearchView.as_view(), name='open-hospital-search'),
    path('nearby-pharmacies/', NearbyPharmacyView.as_view(), name='nearby-pharmacies'),
]
