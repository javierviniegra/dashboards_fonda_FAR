from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from dashboards import views

admin.site.site_header = "Dashboards Fonda"
admin.site.site_title = "Dashboards Fonda"
admin.site.index_title = "Administración"

urlpatterns = [
    path("", views.home, name="home"),
    path("tablero/<slug:pestana>/", views.tablero, name="tablero"),
    path("ayuda/", views.ayuda, name="ayuda"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("admin/", admin.site.urls),
]
