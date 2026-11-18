"""Billing provider abstraction. Stripe in production; a deterministic fake in dev/test.

Only invoices are used (no stored cards, no bank details in v1). Every Stripe write carries an
idempotency key derived from our fee id, so retries never double-bill.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from compback_core.config import Settings, get_settings


@dataclass(frozen=True)
class InvoiceResult:
    invoice_id: str
    hosted_url: str | None
    customer_id: str


class BillingProvider(Protocol):
    def create_invoice(
        self,
        *,
        fee_id: str,
        customer_id: str | None,
        email: str,
        org_name: str,
        description: str,
        amount: Decimal,
    ) -> InvoiceResult: ...

    def parse_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...


class WebhookSignatureError(Exception):
    pass


def to_cents(amount: Decimal) -> int:
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ValueError("amount has fractional cents")
    return int(cents)


class StripeBilling:
    def __init__(self, api_key: str, webhook_secret: str) -> None:
        import stripe  # noqa: PLC0415 - optional, prod only

        self._stripe = stripe
        self._client = stripe.StripeClient(api_key)
        self._secret = webhook_secret

    def create_invoice(
        self,
        *,
        fee_id: str,
        customer_id: str | None,
        email: str,
        org_name: str,
        description: str,
        amount: Decimal,
    ) -> InvoiceResult:
        v1 = self._client.v1
        if customer_id is None:
            customer = v1.customers.create(
                params={"email": email, "name": org_name},
                options={"idempotency_key": f"cust-{fee_id}"},
            )
            customer_id = customer.id
        v1.invoice_items.create(
            params={
                "customer": customer_id,
                "amount": to_cents(amount),
                "currency": "usd",
                "description": description,
                "metadata": {"fee_id": fee_id},
            },
            options={"idempotency_key": f"item-{fee_id}"},
        )
        invoice = v1.invoices.create(
            params={
                "customer": customer_id,
                "collection_method": "send_invoice",
                "days_until_due": 30,
                "pending_invoice_items_behavior": "include",
                "metadata": {"fee_id": fee_id},
                "description": description,
            },
            options={"idempotency_key": f"inv-{fee_id}"},
        )
        finalized = v1.invoices.finalize_invoice(invoice.id)
        return InvoiceResult(str(finalized.id), finalized.hosted_invoice_url, customer_id)

    def parse_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        try:
            event = self._client.construct_event(payload, signature, self._secret)
        except (ValueError, self._stripe.SignatureVerificationError) as exc:
            raise WebhookSignatureError(str(exc)) from exc
        return dict(event.to_dict())


class FakeBilling:
    """Dev/test only. Webhooks are accepted when the signature equals the configured secret."""

    def __init__(self, secret: str = "whsec_test") -> None:  # noqa: S107 - test-only fake
        self._secret = secret

    def create_invoice(
        self,
        *,
        fee_id: str,
        customer_id: str | None,
        email: str,
        org_name: str,
        description: str,
        amount: Decimal,
    ) -> InvoiceResult:
        to_cents(amount)
        return InvoiceResult(
            f"in_fake_{fee_id}",
            f"https://example.invalid/invoice/{fee_id}",
            customer_id or f"cus_fake_{fee_id}",
        )

    def parse_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        import json  # noqa: PLC0415

        if signature != self._secret:
            raise WebhookSignatureError("bad signature")
        return dict(json.loads(payload))


def billing_from_settings(settings: Settings | None = None) -> BillingProvider:
    settings = settings or get_settings()
    if settings.billing_provider == "stripe":
        if settings.stripe_api_key is None or settings.stripe_webhook_secret is None:
            raise RuntimeError("Stripe keys are not configured")
        return StripeBilling(
            settings.stripe_api_key.get_secret_value(),
            settings.stripe_webhook_secret.get_secret_value(),
        )
    return FakeBilling()
