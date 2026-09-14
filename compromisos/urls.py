from django.urls import path

from . import views

urlpatterns = [
    path("", views.listado, name="listado"),
    path("nuevo/", views.editar, name="nuevo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/celda/", views.celda, name="celda"),
    path("<int:pk>/<str:accion>/", views.accion, name="accion"),
]
