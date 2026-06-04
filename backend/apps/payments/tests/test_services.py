"""Service-layer tests: wallet money math, ticket issue/refund, and idempotent webhooks.

Headline tests:
* a DUPLICATE webhook with the same ``txn_ref`` is a no-op (balance + ledger unchanged,
  a single state transition);
* issue-with-wallet-insufficient rolls back COMPLETELY (no ticket, no payment, no debit).
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.buses.models import Bus, Route
from apps.payments.enums import PaymentGateway, PaymentStatus, TicketStatus, WalletTxnKind
from apps.payments.exceptions import (
    GatewayNotConfiguredError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidTripForTicketError,
    PaymentFailedError,
    TicketNotRefundableError,
)
from apps.payments.models import Payment, Ticket, WalletTransaction
from apps.payments.v1.service import PaymentService, TicketService, WalletService
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

User = get_user_model()


@pytest.fixture
def passenger(db) -> User:
    return User.objects.create_user(email="rider@example.com", password="Demo1234!")


@pytest.fixture
def driver(db) -> User:
    return User.objects.create_user(
        email="driver@example.com", password="Demo1234!", role=User.Roles.DRIVER
    )


@pytest.fixture
def route(db) -> Route:
    return Route.objects.create(
        name="Ring Road", color="#1E88E5", estimated_duration=55, fare=Decimal("35.00")
    )


@pytest.fixture
def bus(db) -> Bus:
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def trip(route, driver, bus) -> Trip:
    return Trip.objects.create(bus=bus, route=route, driver=driver)


def _fund(user, amount="100.00"):
    wallet = WalletService.get_or_create(user)
    WalletService.credit(wallet, Decimal(amount), reference="seed")
    return wallet


# ── WalletService ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_credit_updates_balance_and_writes_ledger(passenger):
    wallet = WalletService.get_or_create(passenger)
    txn = WalletService.credit(wallet, Decimal("40.00"), reference="topup")
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("40.00")
    assert txn.kind == WalletTxnKind.CREDIT
    assert txn.balance_after == Decimal("40.00")


@pytest.mark.django_db
def test_debit_updates_balance_and_writes_ledger(passenger):
    wallet = _fund(passenger, "100.00")
    txn = WalletService.debit(wallet, Decimal("30.00"), reference="ride")
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("70.00")
    assert txn.kind == WalletTxnKind.DEBIT
    assert txn.balance_after == Decimal("70.00")


@pytest.mark.django_db
def test_debit_insufficient_raises_and_persists_nothing(passenger):
    wallet = _fund(passenger, "10.00")
    with pytest.raises(InsufficientBalanceError) as exc:
        WalletService.debit(wallet, Decimal("25.00"), reference="ride")
    assert exc.value.status_code == 400
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("10.00")
    # Only the seeding credit row exists — no debit row was written.
    assert wallet.transactions.filter(kind=WalletTxnKind.DEBIT).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("amount", ["0.00", "-50.00", "-0.01"])
def test_debit_non_positive_raises_and_never_credits(passenger, amount):
    """A zero/negative debit must be rejected — never silently invert into a credit."""
    wallet = _fund(passenger, "10.00")
    with pytest.raises(InvalidAmountError) as exc:
        WalletService.debit(wallet, Decimal(amount), reference="ride")
    assert exc.value.status_code == 400
    wallet.refresh_from_db()
    # Balance untouched and no debit row written — the inversion bug cannot happen.
    assert wallet.balance == Decimal("10.00")
    assert wallet.transactions.filter(kind=WalletTxnKind.DEBIT).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("amount", ["0.00", "-50.00", "-0.01"])
def test_credit_non_positive_raises_and_writes_nothing(passenger, amount):
    wallet = WalletService.get_or_create(passenger)
    with pytest.raises(InvalidAmountError):
        WalletService.credit(wallet, Decimal(amount), reference="bad")
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("0.00")
    assert wallet.transactions.count() == 0


@pytest.mark.django_db
def test_money_math_quantizes_to_two_places(passenger):
    wallet = WalletService.get_or_create(passenger)
    WalletService.credit(wallet, Decimal("10.005"), reference="a")  # half-up -> 10.01
    WalletService.credit(wallet, Decimal("0.006"), reference="b")  # half-up -> 0.01
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("10.02")
    assert wallet.balance.as_tuple().exponent == -2  # exactly 2 dp, no float drift
    # A sub-cent amount that quantizes to 0.00 is now a rejected non-positive credit.
    with pytest.raises(InvalidAmountError):
        WalletService.credit(wallet, Decimal("0.001"), reference="c")


# ── TicketService.issue_ticket ───────────────────────────────────────────────
@pytest.mark.django_db
def test_issue_with_wallet_sufficient_settles_active_and_debits(passenger, trip):
    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert ticket.status == TicketStatus.ACTIVE
    assert ticket.fare == Decimal("35.00")
    assert ticket.qr_code  # signed token present
    assert ticket.payment.status == PaymentStatus.SUCCESS
    wallet = WalletService.get_or_create(passenger)
    assert wallet.balance == Decimal("65.00")
    assert (
        wallet.transactions.filter(kind=WalletTxnKind.DEBIT, amount=Decimal("35.00")).count() == 1
    )


@pytest.mark.django_db
def test_issue_with_wallet_insufficient_rolls_back_everything(passenger, trip):
    _fund(passenger, "10.00")  # < 35.00 fare
    with pytest.raises(InsufficientBalanceError):
        TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    # Full atomic rollback: no ticket, no payment, no debit; balance untouched.
    assert Ticket.objects.count() == 0
    assert Payment.objects.count() == 0
    wallet = WalletService.get_or_create(passenger)
    assert wallet.balance == Decimal("10.00")
    assert wallet.transactions.filter(kind=WalletTxnKind.DEBIT).count() == 0


@pytest.mark.django_db
def test_issue_external_leaves_payment_pending_and_ticket_issued(passenger, trip):
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.KHALTI)
    assert ticket.status == TicketStatus.ISSUED
    assert ticket.qr_code
    assert ticket.payment.status == PaymentStatus.PENDING
    assert ticket.payment.gateway == PaymentGateway.KHALTI
    assert ticket.payment.txn_ref  # internally minted idempotency key


@pytest.mark.django_db
@pytest.mark.parametrize("fare", ["0.00", "-35.00"])
def test_issue_with_non_positive_fare_raises_and_persists_nothing(passenger, trip, fare):
    """A bad (free/negative) snapshotted fare is rejected before any ticket/payment/debit."""
    _fund(passenger, "100.00")
    # Bypass the model validator (which only fires on full_clean) to simulate a bad seed value.
    Route.objects.filter(id=trip.route_id).update(fare=Decimal(fare))
    trip.route.refresh_from_db()
    with pytest.raises(InvalidAmountError) as exc:
        TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert exc.value.status_code == 400
    assert Ticket.objects.count() == 0
    assert Payment.objects.count() == 0
    # No debit happened — balance untouched.
    assert WalletService.get_or_create(passenger).balance == Decimal("100.00")


@pytest.mark.django_db
def test_issue_on_finished_trip_raises_invalid_trip(passenger, trip):
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])
    with pytest.raises(InvalidTripForTicketError) as exc:
        TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert exc.value.status_code == 400
    assert Ticket.objects.count() == 0


# ── TicketService.refund_ticket ──────────────────────────────────────────────
@pytest.mark.django_db
def test_refund_success_credits_wallet_and_flips_statuses(passenger, trip):
    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")

    refunded = TicketService.refund_ticket(ticket, passenger)
    assert refunded.status == TicketStatus.REFUNDED
    assert refunded.payment.status == PaymentStatus.REFUNDED
    # Store credit returned -> balance back to 100.
    assert WalletService.get_or_create(passenger).balance == Decimal("100.00")
    assert (
        WalletTransaction.objects.filter(
            kind=WalletTxnKind.CREDIT, reference=f"refund:{ticket.id}"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_refund_non_success_raises_not_refundable(passenger, trip):
    # External payment stays PENDING -> not refundable.
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.ESEWA)
    with pytest.raises(TicketNotRefundableError) as exc:
        TicketService.refund_ticket(ticket, passenger)
    assert exc.value.status_code == 409


@pytest.mark.django_db
def test_refund_twice_second_raises(passenger, trip):
    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    TicketService.refund_ticket(ticket, passenger)
    with pytest.raises(TicketNotRefundableError):
        TicketService.refund_ticket(ticket, passenger)
    # Balance reflects exactly ONE refund credit, not two.
    assert WalletService.get_or_create(passenger).balance == Decimal("100.00")


@pytest.mark.django_db
def test_refund_rechecks_status_under_lock(passenger, trip, monkeypatch):
    """The SUCCESS guard must read the Payment FOR UPDATE inside the atomic block.

    A true two-thread race can't run on the in-memory sqlite test DB, so we assert the
    locking idiom directly: the row-locked read is what gates the credit, and a payment
    that flips to REFUNDED between the unlocked stale read and the locked re-read still
    raises (no double credit). This is the property the unlocked TOCTOU code lacked.
    """
    from apps.payments.enums import PaymentStatus as _PS
    from apps.payments.repository import PaymentRepository

    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")

    # Simulate a concurrent refund having already committed REFUNDED before the lock is
    # taken: the very next locked read must observe it and refuse to credit again.
    real_locked_read = PaymentRepository.by_ticket_for_update.__func__

    def flip_then_read(cls, t):
        payment = real_locked_read(cls, t)
        if payment is not None and payment.status == _PS.SUCCESS:
            Payment.objects.filter(id=payment.id).update(status=_PS.REFUNDED)
            payment.refresh_from_db()
        return payment

    monkeypatch.setattr(PaymentRepository, "by_ticket_for_update", classmethod(flip_then_read))
    with pytest.raises(TicketNotRefundableError):
        TicketService.refund_ticket(ticket, passenger)
    # No refund credit was written despite passing through refund_ticket once.
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")
    assert (
        WalletTransaction.objects.filter(
            kind=WalletTxnKind.CREDIT, reference=f"refund:{ticket.id}"
        ).count()
        == 0
    )


# ── PaymentService.process_webhook ───────────────────────────────────────────
@pytest.mark.django_db
def test_webhook_success_activates_ticket(passenger, trip):
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.KHALTI)
    txn_ref = ticket.payment.txn_ref
    payment = PaymentService.process_webhook(PaymentGateway.KHALTI, txn_ref, PaymentStatus.SUCCESS)
    assert payment.status == PaymentStatus.SUCCESS
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ACTIVE


@pytest.mark.django_db
def test_duplicate_webhook_is_a_noop(passenger, trip):
    """HEADLINE: a second webhook with the same txn_ref changes nothing."""
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.KHALTI)
    txn_ref = ticket.payment.txn_ref

    PaymentService.process_webhook(PaymentGateway.KHALTI, txn_ref, PaymentStatus.SUCCESS)
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ACTIVE
    updated_at_after_first = Payment.objects.get(txn_ref=txn_ref).updated_at

    # Duplicate delivery — must be an idempotent no-op.
    payment = PaymentService.process_webhook(PaymentGateway.KHALTI, txn_ref, PaymentStatus.SUCCESS)
    assert payment.status == PaymentStatus.SUCCESS
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ACTIVE
    # No second state transition: the row was not re-saved.
    assert Payment.objects.get(txn_ref=txn_ref).updated_at == updated_at_after_first
    # No wallet movement at all (external gateway never touches the ledger).
    assert WalletTransaction.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_wallet_settlement_does_not_double_debit(passenger, trip):
    """A wallet payment settled at issue must not be debited again by a stray webhook."""
    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")
    debits_before = WalletTransaction.objects.filter(kind=WalletTxnKind.DEBIT).count()

    PaymentService.process_webhook(
        PaymentGateway.WALLET, ticket.payment.txn_ref, PaymentStatus.SUCCESS
    )
    # Already SUCCESS -> terminal no-op: balance + debit count unchanged.
    assert WalletService.get_or_create(passenger).balance == Decimal("65.00")
    assert WalletTransaction.objects.filter(kind=WalletTxnKind.DEBIT).count() == debits_before


@pytest.mark.django_db
def test_webhook_failed_cancels_ticket(passenger, trip):
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.KHALTI)
    payment = PaymentService.process_webhook(
        PaymentGateway.KHALTI, ticket.payment.txn_ref, PaymentStatus.FAILED
    )
    assert payment.status == PaymentStatus.FAILED
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.CANCELLED


@pytest.mark.django_db
def test_webhook_unknown_txn_ref_raises_payment_failed(db):
    with pytest.raises(PaymentFailedError) as exc:
        PaymentService.process_webhook(
            PaymentGateway.KHALTI, "does-not-exist", PaymentStatus.SUCCESS
        )
    assert exc.value.status_code == 400
    assert exc.value.detail.code == "payment_failed"


# ── PaymentService.checkout ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_checkout_external_raises_gateway_not_configured(passenger, trip):
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.KHALTI)
    with pytest.raises(GatewayNotConfiguredError) as exc:
        PaymentService.checkout(ticket, passenger)
    assert exc.value.status_code == 400
    assert exc.value.detail.code == "gateway_not_configured"


@pytest.mark.django_db
def test_checkout_wallet_reports_terminal_state(passenger, trip):
    _fund(passenger, "100.00")
    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    result = PaymentService.checkout(ticket, passenger)
    assert result["gateway"] == PaymentGateway.WALLET
    assert result["status"] == PaymentStatus.SUCCESS
    assert result["checkout_ref"] is None
