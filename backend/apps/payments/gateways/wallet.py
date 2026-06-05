"""The wallet gateway — a fully working, synchronous in-app settlement adapter.

Unlike the external stubs, a wallet payment settles at issue time (the debit happens
inside ``TicketService.issue_ticket`` via ``PaymentService._settle_success``). There is
therefore no asynchronous checkout to start: ``start_checkout`` reports the payment's
already-terminal state instead of contacting an external provider.
"""

from apps.payments.enums import PaymentGateway

from .base import BaseGateway


class WalletGateway(BaseGateway):
    gateway = PaymentGateway.WALLET

    def start_checkout(self, payment) -> dict:
        # Wallet payments are settled inline at issue time — nothing to redirect to.
        return {
            "txn_ref": payment.txn_ref,
            "gateway": payment.gateway,
            "status": payment.status,
            "checkout_ref": None,
        }
