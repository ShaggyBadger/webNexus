"""Render the public binder payment page and its configured Stripe link."""

from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def _get_stripe_payment_link() -> str | None:
    """Return the configured Stripe Payment Link only when its host is trusted."""
    payment_link_url = settings.STRIPE_BINDER_PAYMENT_LINK_URL
    if not payment_link_url:
        return None

    try:
        parsed_url = urlsplit(payment_link_url)
        is_trusted_link = (
            parsed_url.scheme == "https"
            and parsed_url.hostname == "buy.stripe.com"
            and parsed_url.path not in ("", "/")
            and parsed_url.username is None
            and parsed_url.password is None
            and parsed_url.port is None
        )
    except ValueError:
        return None

    return payment_link_url if is_trusted_link else None


def binder_payment_page(request: HttpRequest) -> HttpResponse:
    """
    Lets binder buyers reach Stripe-hosted payment without exposing card data to webNexus.

    Args:
        request: The incoming public page request.

    Returns:
        The binder payment page with a trusted Stripe checkout link when configured.
    """
    context = {"payment_link_url": _get_stripe_payment_link()}
    return render(request, "payments/binder_payment.html", context)
