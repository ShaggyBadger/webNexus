# Payments

The `payments` app provides the public `/payments/` page for the physical Tank
Chart Binder. It displays the $20 one-time price and links buyers to Stripe's
hosted Payment Link checkout. The binder is handed to buyers in person, so this
page does not collect shipping details.

## Payment Boundary

- Stripe Dashboard owns the product, price, payment methods, and checkout.
- webNexus does not collect card data, call Stripe APIs, store payment/order
  records, or process webhooks in this link-only flow.
- The owner verifies payments in the Stripe Dashboard and handles hand delivery
  manually.
- Stripe API keys and webhook signing secrets are not required by this app.

## Configuration

Set `STRIPE_BINDER_PAYMENT_LINK_URL` to the public Payment Link URL in the
runtime environment. The application only renders HTTPS links hosted on
`buy.stripe.com`. Add the value to the local `.env` and server environment
outside source control; do not put credentials in this setting.

## Focused Verification

```bash
python manage.py test payments --noinput
python manage.py check
```
