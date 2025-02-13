# drugapp/urls.py
from django.urls import path
from .views import DrugSearchAPIView

urlpatterns = [
    path("drug-info/", DrugSearchAPIView.as_view(), name="drug-search"),
]
