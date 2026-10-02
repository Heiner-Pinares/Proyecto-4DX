from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path

from compromisos import views, teams, correo

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard),
    path("compromisos/", include("compromisos.urls")),
    path("indicadores/", views.indicadores, name="indicadores"),
    path("reportes/correo/enviar/", correo.enviar_resumen, name="correo_enviar"),
    path("reportes/teams/", teams.enviar_recordatorio, name="teams_enviar"),
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/semanal/", views.resumen_semanal, name="resumen_semanal"),
    path("reportes/correo/", views.correo_reporte, name="correo_reporte"),
    path("exportar/<str:formato>/", views.exportar, name="exportar"),
    path("papelera/", views.papelera, name="papelera"),
]
from compromisos import accounts

urlpatterns += [
    path("usuarios/", accounts.usuarios, name="usuarios"),
    path("usuarios/<int:pk>/", accounts.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/password/", accounts.password, name="usuario_password"),
    path("administracion/", accounts.estados, name="estados"),
    path("administracion/<int:pk>/", accounts.estados, name="estado_editar"),
]
