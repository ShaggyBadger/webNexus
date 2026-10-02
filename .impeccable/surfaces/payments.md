---
version: 1
slug: "payments"
primary_target: "payments"
related_targets: []
---

# Payments Surface Brief

## Scope and mode

Public `/payments/` page for a buyer arriving from a text link. Mode: Operate —
the visitor needs to identify the binder and proceed to payment.

## Audience, task, content, and constraints

The visitor is buying one physical Tank Chart Binder. Show its name and the
confirmed one-time $20 price. Delivery is in person, so do not request shipping
details. A single button opens the owner-configured Stripe Payment Link. Do not
collect card data in webNexus or imply that payment is recorded by webNexus.

## Direction contract

**THESIS:** State the exact item and price, then make the path to Stripe checkout
the page's only primary action. Refuse a catalog, cart, or custom payment form.

**OWN-WORLD:** Inherit the existing webNexus Base Camp interface: charcoal
surfaces, clear light text, restrained olive/amber action color, and the site's
existing typography and shared page chrome.

**STORY:** The visitor recognizes the binder and its price, understands that
checkout continues securely on Stripe, and follows one obvious payment action.

**FIRST VIEWPORT:** Keep the item name, `$20`, a short hand-delivery note, and a
large touch-ready `Pay $20` button together in a compact, centered content
region that works on a phone and desktop.

**FORM:** One-product detail and one checkout link, as specified by the owner.
Seed key: not applicable; this is a narrow, user-specified extension of the
existing visual system, not an open concept direction.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance
