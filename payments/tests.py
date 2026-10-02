from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class BinderPaymentPageTests(SimpleTestCase):
    """Verify the public binder offer and trusted checkout-link behavior."""

    def test_page_links_to_the_configured_stripe_payment_link(self):
        payment_link_url = "https://buy.stripe.com/exampleLink123"

        with override_settings(STRIPE_BINDER_PAYMENT_LINK_URL=payment_link_url):
            response = self.client.get(reverse("payments:binder_payment"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tank Chart Binder")
        self.assertContains(response, "$20")
        self.assertContains(response, "Hand-delivered")
        self.assertContains(response, f'href="{payment_link_url}"')
        self.assertContains(response, "Secure checkout opens on Stripe.")

    def test_page_explains_checkout_is_unavailable_when_link_is_missing(self):
        with override_settings(STRIPE_BINDER_PAYMENT_LINK_URL=""):
            response = self.client.get(reverse("payments:binder_payment"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkout is temporarily unavailable.")
        self.assertNotContains(response, "Pay $20")

    def test_page_does_not_render_an_untrusted_payment_link(self):
        untrusted_url = "https://example.com/fake-checkout"

        with override_settings(STRIPE_BINDER_PAYMENT_LINK_URL=untrusted_url):
            response = self.client.get(reverse("payments:binder_payment"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkout is temporarily unavailable.")
        self.assertNotContains(response, untrusted_url)
