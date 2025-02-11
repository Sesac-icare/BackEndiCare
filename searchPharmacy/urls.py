from django.urls import path
from . import views

urlpatterns = [
    # 사용자 관련 URL
    path('users/create/', views.create_user, name='create_user'),
    path('users/', views.list_users, name='list_users'),

    # 자녀 관련 URL
    path('children/create/', views.create_child, name='create_child'),
    path('children/', views.list_children, name='list_children'),

    # 약국 봉투 관련 URL
    path('pharmacy-envelopes/create/', views.create_pharmacy_envelope, name='create_pharmacy_envelope'),
    path('pharmacy-envelopes/', views.list_pharmacy_envelopes, name='list_pharmacy_envelopes'),
]
