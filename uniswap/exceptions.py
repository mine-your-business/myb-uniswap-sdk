from typing import Any


class InvalidToken(Exception):
    """Raised when an invalid token address is used."""

    def __init__(self, address: Any) -> None:
        Exception.__init__(self, f"Invalid token address: {address}")


class InsufficientBalance(Exception):
    """Raised when the account has insufficient balance for a transaction."""

    def __init__(self, had: int, needed: int) -> None:
        Exception.__init__(self, f"Insufficient balance. Had {had}, needed {needed}")


class GasLimitExceeded(Exception):
    """Raised when a transaction's padded gas estimate is above ``maximum_gas``."""

    def __init__(self, estimated: int, maximum: int) -> None:
        self.estimated = estimated
        self.maximum = maximum
        # Message kept from 1.x so callers matching on it keep working.
        Exception.__init__(
            self, f"Gas fees too high! Estimated {estimated}, maximum {maximum}"
        )
