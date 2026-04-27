"""
Demo scratch module — intentionally littered with markers so the scanner has
something realistic to surface during demos.

Not imported by anything. Safe to delete once the LLM pass replaces the
regex-only scanner.
"""
from typing import List


class PaymentProcessor:
    # HACK: hardcoded retry count — should come from config
    MAX_RETRIES = 3

    def __init__(self, gateway):
        self.gateway = gateway

    def process(self, payment):
        # TODO: add idempotency key so retries don't double-charge
        for attempt in range(self.MAX_RETRIES):
            result = self.gateway.charge(payment)
            if result.ok:
                return result
        return None


def calculate_total(items: List) -> float:
    # FIXME: crashes when items is empty (sum() returns 0 but we hit AttributeError below)
    total = 0
    for item in items:
        total += item.price
    return total


def send_notification(user, message: str) -> None:
    # FIXME: breaks when the user has no email — needs to fall back to in-app
    smtp.send(user.email, message)


# XXX: this whole module should be split into payment/, notification/, util/
def legacy_helper(x):
    # TODO(piram): rewrite this once the new auth flow lands
    return x * 2
