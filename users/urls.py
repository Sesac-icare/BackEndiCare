from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, 
    UserInfoView, UserDeleteView, UserLocationView, UpdateLocationView
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", UserInfoView.as_view(), name="user-info"),
    path("delete/", UserDeleteView.as_view(), name="user-delete"),
    path("location/", UserLocationView.as_view(), name="user-location"),
    path("update-location/", UpdateLocationView.as_view(), name="update-location"),
]


# -----------------------------------------------------------------------

# from django.urls import path
# from .views import RegisterView, LoginView

# urlpatterns = [
#     path('register/', RegisterView.as_view(), name='register'),
#     path('login/', LoginView.as_view(), name='login'),
# ]
