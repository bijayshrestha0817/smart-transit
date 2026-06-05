"""Model-layer tests: creation, Decimal fields, and the soft-delete partial-unique
constraints on ``qr_code`` (tickets) and ``txn_ref`` (payments)."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.buses.models import Bus, Route
from apps.payments.enums import PaymentGateway, PaymentStatus, TicketStatus, WalletTxnKind
from apps.payments.models import Payment, Ticket, Wallet, WalletTransaction
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


def _ticket(passenger, trip, qr_code="qr-1", status=TicketStatus.ISSUED) -> Ticket:
    return Ticket.objects.create(
        passenger=passenger, trip=trip, qr_code=qr_code, status=status, fare=Decimal("35.00")
    )


# ── Creation + Decimal fields ────────────────────────────────────────────────
@pytest.mark.django_db
def test_ticket_creation_holds_decimal_fare(passenger, trip):
    ticket = _ticket(passenger, trip)
    ticket.refresh_from_db()
    assert ticket.fare == Decimal("35.00")
    assert isinstance(ticket.fare, Decimal)
    assert ticket.status == TicketStatus.ISSUED


@pytest.mark.django_db
def test_payment_creation_is_one_to_one_with_ticket(passenger, trip):
    ticket = _ticket(passenger, trip)
    payment = Payment.objects.create(
        ticket=ticket,
        amount=Decimal("35.00"),
        gateway=PaymentGateway.WALLET,
        txn_ref="txn-1",
    )
    assert payment.status == PaymentStatus.PENDING
    assert ticket.payment == payment
    assert isinstance(payment.amount, Decimal)


@pytest.mark.django_db
def test_wallet_and_transaction_creation(passenger):
    wallet = Wallet.objects.create(user=passenger, balance=Decimal("100.00"))
    txn = WalletTransaction.objects.create(
        wallet=wallet,
        kind=WalletTxnKind.CREDIT,
        amount=Decimal("100.00"),
        balance_after=Decimal("100.00"),
        reference="seed:1",
    )
    assert wallet.balance == Decimal("100.00")
    assert txn.balance_after == Decimal("100.00")
    assert wallet.transactions.count() == 1


# ── Partial-unique: qr_code (tickets) ────────────────────────────────────────
@pytest.mark.django_db
def test_duplicate_active_qr_code_violates_constraint(passenger, trip):
    _ticket(passenger, trip, qr_code="dup-qr")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _ticket(passenger, trip, qr_code="dup-qr")


@pytest.mark.django_db
def test_blank_qr_codes_do_not_collide(passenger, trip):
    """The placeholder empty string is excluded from the partial-unique condition, so
    multiple active rows holding qr_code="" coexist (otherwise issuance would brick)."""
    first = _ticket(passenger, trip, qr_code="")
    second = _ticket(passenger, trip, qr_code="")  # must NOT raise IntegrityError
    assert first.id != second.id
    assert Ticket.objects.filter(qr_code="").count() == 2


@pytest.mark.django_db
def test_issue_ticket_succeeds_after_preexisting_blank_qr_row(passenger, trip):
    """A pre-existing committed blank-qr ticket (e.g. an admin/import row) must not brick
    the production issue path, whose initial INSERT also writes qr_code=""."""
    from apps.payments.v1.service import TicketService, WalletService

    _ticket(passenger, trip, qr_code="")  # stray committed blank-qr row
    wallet = WalletService.get_or_create(passenger)
    WalletService.credit(wallet, Decimal("100.00"), reference="seed")

    ticket = TicketService.issue_ticket(passenger, trip, PaymentGateway.WALLET)
    assert ticket.qr_code  # a real signed token was minted
    assert ticket.status == TicketStatus.ACTIVE


@pytest.mark.django_db
def test_soft_deleted_qr_code_can_be_reused(passenger, trip):
    first = _ticket(passenger, trip, qr_code="reuse-qr")
    first.delete()  # soft delete -> tombstone, excluded from the partial-unique
    assert first.is_deleted is True
    # Same qr_code is now reusable on a fresh active row.
    second = _ticket(passenger, trip, qr_code="reuse-qr")
    assert second.id != first.id
    assert Ticket.objects.filter(qr_code="reuse-qr").count() == 1


# ── Partial-unique: txn_ref (payments) ───────────────────────────────────────
@pytest.mark.django_db
def test_duplicate_active_txn_ref_violates_constraint(passenger, trip):
    t1 = _ticket(passenger, trip, qr_code="qr-a")
    t2 = _ticket(passenger, trip, qr_code="qr-b")
    Payment.objects.create(
        ticket=t1, amount=Decimal("35.00"), gateway=PaymentGateway.WALLET, txn_ref="dup-txn"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Payment.objects.create(
                ticket=t2,
                amount=Decimal("35.00"),
                gateway=PaymentGateway.WALLET,
                txn_ref="dup-txn",
            )


@pytest.mark.django_db
def test_soft_deleted_txn_ref_can_be_reused(passenger, trip):
    t1 = _ticket(passenger, trip, qr_code="qr-c")
    t2 = _ticket(passenger, trip, qr_code="qr-d")
    p1 = Payment.objects.create(
        ticket=t1, amount=Decimal("35.00"), gateway=PaymentGateway.WALLET, txn_ref="reuse-txn"
    )
    p1.delete()  # soft delete -> tombstone
    p2 = Payment.objects.create(
        ticket=t2, amount=Decimal("35.00"), gateway=PaymentGateway.WALLET, txn_ref="reuse-txn"
    )
    assert p2.id != p1.id
    assert Payment.objects.filter(txn_ref="reuse-txn").count() == 1
