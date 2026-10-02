"""Public routes for the binder payment experience."""

from django.urls import path

from payments.views import binder_payment_page

app_name = "payments"

urlpatterns = [
    path("", binder_payment_page, name="binder_payment"),
]
