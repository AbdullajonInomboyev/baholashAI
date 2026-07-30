from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("chiqish/", views.logout_view, name="logout"),
    path("rol/<str:code>/", views.switch_role, name="switch_role"),
]
