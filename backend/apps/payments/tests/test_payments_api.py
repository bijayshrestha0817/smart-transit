"""REST + RBAC tests for the payments API: tickets, wallet, checkout, webhook.

Role auth uses ``client.force_authenticate(user=...)``. Body assertions read the rendered
``{data, meta, errors}`` envelope. The webhook is ``AllowAny`` (gateway server, no cookie).
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.buses.models import Bus, Route
from apps.payments.enums import PaymentGateway, PaymentStatus, TicketStatus
from apps.payments.models import Payment, Ticket, WalletTransaction
from apps.payments.v1.service import WalletService
from apps.trips.models import Trip

User = get_user_model()

PASSWORD = "StrongPass123!"
TICKETS_URL = "/api/v1/tickets/"
WALLET_URL = "/api/v1/wallet/"
WALLET_TXNS_URL = "/api/v1/wallet/transactions/"
CHECKOUT_URL = "/api/v1/payments/checkout/"


def webhook_url(gateway):
    return f"/api/v1/payments/webhook/{gateway}/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com", password=PASSWORD, role=User.Roles.ADMIN, is_verified=True
    )


@pytest.fixture
def passenger(db):
    return User.objects.create_user(email="rider@example.com", password=PASSWORD, is_verified=True)


@pytest.fixture
def other_passenger(db):
    return User.objects.create_user(email="rider2@example.com", password=PASSWORD, is_verified=True)


@pytest.fixture
def driver(db):
    return User.objects.create_user(
        email="driver@example.com", password=PASSWORD, role=User.Roles.DRIVER, is_verified=True
    )


@pytest.fixture
def route(db):
    return Route.objects.create(
        name="Ring Road", color="#1E88E5", estimated_duration=55, fare=Decimal("35.00")
    )


@pytest.fixture
def bus(db):
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def trip(route, driver, bus):
    return Trip.objects.create(bus=bus, route=route, driver=driver)


def _fund(user, amount="100.00"):
    wallet = WalletService.get_or_create(user)
    WalletService.credit(wallet, Decimal(amount), reference="seed")
    return wallet


# ── Issue + list ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_passenger_can_issue_wallet_ticket(client, passenger, trip):
    _fund(passenger, "100.00")
    client.force_authenticate(user=passenger)
    resp = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == TicketStatus.ACTIVE
    assert data["fare"] == "35.00"
    assert data["qr_code"]
    assert data["payment_status"] == PaymentStatus.SUCCESS


@pytest.mark.django_db
def test_passenger_issue_insufficient_returns_400_and_persists_nothing(client, passenger, trip):
    _fund(passenger, "10.00")
    client.force_authenticate(user=passenger)
    resp = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "insufficient_balance"
    assert Ticket.objects.count() == 0
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_passenger_lists_only_own_tickets(client, passenger, other_passenger, trip):
    _fund(passenger, "100.00")
    client.force_authenticate(user=passenger)
    mine = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    ).json()["data"]["id"]

    # Another passenger's ticket must not appear in this list.
    other_ticket = Ticket.objects.create(
        passenger=other_passenger, trip=trip, qr_code="other-qr", fare=Decimal("35.00")
    )

    resp = client.get(TICKETS_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["meta"]["pagination"]["page_size"] == 20
    ids = {t["id"] for t in envelope["data"]}
    assert mine in ids
    assert other_ticket.id not in ids


@pytest.mark.django_db
def test_passenger_list_filters_by_status(client, passenger, trip):
    _fund(passenger, "100.00")
    client.force_authenticate(user=passenger)
    active_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    ).json()["data"]["id"]
    # A pending (external) ticket too.
    client.post(TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.KHALTI}, format="json")

    resp = client.get(TICKETS_URL, {"status": TicketStatus.ACTIVE})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()["data"]}
    assert ids == {active_id}


@pytest.mark.django_db
def test_issue_requires_auth(client, trip):
    assert (
        client.post(
            TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
        ).status_code
        == 401
    )


@pytest.mark.django_db
def test_issue_forbidden_for_driver_and_admin(client, driver, admin, trip):
    client.force_authenticate(user=driver)
    assert (
        client.post(
            TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
        ).status_code
        == 403
    )
    client.force_authenticate(user=admin)
    assert (
        client.post(
            TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
        ).status_code
        == 403
    )


# ── Retrieve / RBAC ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_passenger_can_retrieve_own_ticket(client, passenger, trip):
    _fund(passenger, "100.00")
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    ).json()["data"]["id"]
    resp = client.get(f"{TICKETS_URL}{ticket_id}/")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == ticket_id


@pytest.mark.django_db
def test_passenger_cannot_read_another_passengers_ticket(client, passenger, other_passenger, trip):
    other_ticket = Ticket.objects.create(
        passenger=other_passenger, trip=trip, qr_code="other-qr", fare=Decimal("35.00")
    )
    client.force_authenticate(user=passenger)
    # Scoped queryset -> 404 (never leaks the foreign ticket).
    assert client.get(f"{TICKETS_URL}{other_ticket.id}/").status_code == 404


# ── Refund ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_refund_flow_credits_wallet_end_to_end(client, passenger, trip):
    _fund(passenger, "100.00")
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.WALLET}, format="json"
    ).json()["data"]["id"]
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")

    resp = client.post(f"{TICKETS_URL}{ticket_id}/refund/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == TicketStatus.REFUNDED
    assert WalletService.get_or_create(passenger).balance == Decimal("100.00")


@pytest.mark.django_db
def test_refund_non_success_returns_409(client, passenger, trip):
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.KHALTI}, format="json"
    ).json()["data"]["id"]
    resp = client.post(f"{TICKETS_URL}{ticket_id}/refund/", {}, format="json")
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "ticket_not_refundable"


# ── Wallet ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_wallet_balance_endpoint(client, passenger):
    _fund(passenger, "75.50")
    client.force_authenticate(user=passenger)
    resp = client.get(WALLET_URL)
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == "75.50"


@pytest.mark.django_db
def test_wallet_transactions_ledger(client, passenger):
    _fund(passenger, "50.00")
    client.force_authenticate(user=passenger)
    resp = client.get(WALLET_TXNS_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["meta"]["pagination"]["page_size"] == 20
    assert len(envelope["data"]) == 1
    assert envelope["data"][0]["kind"] == "credit"


@pytest.mark.django_db
def test_wallet_forbidden_for_driver(client, driver):
    client.force_authenticate(user=driver)
    assert client.get(WALLET_URL).status_code == 403


@pytest.mark.django_db
def test_wallet_requires_auth(client):
    assert client.get(WALLET_URL).status_code == 401


# ── Checkout ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_checkout_external_returns_gateway_not_configured(client, passenger, trip):
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.KHALTI}, format="json"
    ).json()["data"]["id"]
    resp = client.post(CHECKOUT_URL, {"ticket": ticket_id}, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "gateway_not_configured"


@pytest.mark.django_db
def test_checkout_foreign_ticket_returns_404(client, passenger, other_passenger, trip):
    foreign = Ticket.objects.create(
        passenger=other_passenger, trip=trip, qr_code="foreign-qr", fare=Decimal("35.00")
    )
    client.force_authenticate(user=passenger)
    assert client.post(CHECKOUT_URL, {"ticket": foreign.id}, format="json").status_code == 404


# ── Webhook (AllowAny, idempotent) ───────────────────────────────────────────
@pytest.mark.django_db
def test_webhook_is_allowany_and_activates_ticket(client, passenger, trip):
    # Issue an external ticket as the passenger, then confirm via an UNAUTHENTICATED webhook.
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.KHALTI}, format="json"
    ).json()["data"]["id"]
    txn_ref = Payment.objects.get(ticket_id=ticket_id).txn_ref

    anon = APIClient()  # no cookie -> AllowAny
    resp = anon.post(
        webhook_url(PaymentGateway.KHALTI),
        {"txn_ref": txn_ref, "status": PaymentStatus.SUCCESS},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["ticket_status"] == TicketStatus.ACTIVE
    assert Ticket.objects.get(id=ticket_id).status == TicketStatus.ACTIVE


@pytest.mark.django_db
def test_duplicate_webhook_via_api_is_noop(client, passenger, trip):
    client.force_authenticate(user=passenger)
    ticket_id = client.post(
        TICKETS_URL, {"trip": trip.id, "gateway": PaymentGateway.ESEWA}, format="json"
    ).json()["data"]["id"]
    txn_ref = Payment.objects.get(ticket_id=ticket_id).txn_ref

    anon = APIClient()
    payload = {"txn_ref": txn_ref, "status": PaymentStatus.SUCCESS}
    first = anon.post(webhook_url(PaymentGateway.ESEWA), payload, format="json")
    assert first.status_code == 200
    second = anon.post(webhook_url(PaymentGateway.ESEWA), payload, format="json")
    assert second.status_code == 200  # idempotent no-op, still 200

    assert Ticket.objects.get(id=ticket_id).status == TicketStatus.ACTIVE
    # No wallet movement for an external gateway, even across duplicate deliveries.
    assert WalletTransaction.objects.count() == 0


@pytest.mark.django_db
def test_webhook_unknown_gateway_returns_400(client):
    anon = APIClient()
    resp = anon.post(
        webhook_url("paypal"),
        {"txn_ref": "x", "status": PaymentStatus.SUCCESS},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_webhook_unknown_txn_ref_returns_400_payment_failed(client):
    anon = APIClient()
    resp = anon.post(
        webhook_url(PaymentGateway.KHALTI),
        {"txn_ref": "nope", "status": PaymentStatus.SUCCESS},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "payment_failed"
