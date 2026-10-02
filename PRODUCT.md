# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Field operations staff use webNexus for fuel and tank data workflows. Buyers of
the printed Tank Chart Binder use the public payment page after receiving its
URL, including in a text message.

## Product Purpose

webNexus is a Django field operations command center for fuel and tank data
workflows. Its public binder payment page lets a buyer pay the owner for a
physical Tank Chart Binder through Stripe-hosted checkout.

## Operating Context

The binder is handed to the buyer in person. The owner sends the public
`/payments/` URL, and the buyer follows the Stripe checkout link on that page.
The Stripe Dashboard remains the payment record for this initial manual-sales
workflow.

## Capabilities and Constraints

- The initial offer is one physical Tank Chart Binder for a one-time price of
  $20.
- Delivery is in person; the web page does not collect shipping information.
- Stripe hosts the actual checkout form. webNexus does not collect or store card
  information, create orders, or process payment webhooks for this version.
- Payment status is checked manually in the Stripe Dashboard.

## Evidence on Hand

- The owner supplied an active Stripe Payment Link for the binder.
- The owner has made the physical binder; no product photograph was supplied.

## Product Principles

- Keep payment collection within Stripe-hosted checkout.
- Make the item, one-time price, and payment action clear before checkout.
- Keep this initial hand-delivery workflow simple and manually verifiable.
