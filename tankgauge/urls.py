from django.urls import path
from . import views

app_name = "tankgauge"

urlpatterns = [
    path("", views.delivery_form, name="delivery_form"),
    path("delivery-submit/", views.delivery_submit, name="delivery_submit"),
]
