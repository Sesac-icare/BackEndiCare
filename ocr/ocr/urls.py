from django.urls import path
from .views import ocr_process
from .views import ocr_api
from . import views

urlpatterns = [
    path("process/", ocr_process, name="ocr_process"),
    path("api/ocr/", ocr_api, name = "ocr_api"),
    path('api/users/create/', views.create_user, name='create_user'),
]
