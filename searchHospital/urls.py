from django.urls import path
from . import views

urlpatterns = [
    # 병원 관련 API
    path('hospitals/nearby/', views.nearby_hospitals, name='nearby_hospitals'),

    # 사용자 관련 API
    path('users/create/', views.create_user, name='create_user'),

    # 자녀 관련 API
    path('children/create/', views.create_child, name='create_child'),
    path('children/', views.list_children, name='list_children'),

    # 약국 봉투 관련 API
    path('pharmacy-envelopes/create/', views.create_pharmacy_envelope, name='create_pharmacy_envelope'),
    path('pharmacy-envelopes/', views.list_pharmacy_envelopes, name='list_pharmacy_envelopes'),
]
