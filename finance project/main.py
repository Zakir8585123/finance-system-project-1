from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from collections.abc import Iterable


class Currency(str, Enum):

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    TRY = "TRY"


@dataclass(frozen=True, slots=True)
class Money:

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        try:
            normalized = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except Exception as exc:
            raise TypeError("amount must be a finite decimal value") from exc
        if not normalized.is_finite():
            raise ValueError("amount must be finite")
        if not isinstance(self.currency, Currency):
            raise TypeError("currency must be a Currency value")
        object.__setattr__(self, "amount", normalized)

    def _require_matching_currency(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError("Money arithmetic requires another Money value")
        if self.currency is not other.currency:
            raise ValueError("cannot combine different currencies")

    def __add__(self, other: Money) -> Money:
        self._require_matching_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_matching_currency(other)
        return Money(self.amount - other.amount, self.currency)


class TransactionType(str, Enum):

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"


@dataclass(frozen=True, slots=True)
class Transaction:

    transaction_id: UUID
    transaction_type: TransactionType
    amount: Money
    occurred_at: datetime
    source_account_id: UUID | None = None
    destination_account_id: UUID | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.amount.amount <= 0:
            raise ValueError("transaction amount must be positive")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        if not self.description.strip() and self.description:
            raise ValueError("description cannot contain only whitespace")

class AbstractAccount(ABC):

    @property
    @abstractmethod
    def account_id(self) -> UUID:
        """Stable identifier for the account."""

    @abstractmethod
    def process_transaction(self, transaction: Transaction) -> None:
        """Apply a transaction according to the account's policy."""


@dataclass(slots=True)
class Account(AbstractAccount):

    owner_id: UUID
    currency: Currency
    account_id: UUID = field(default_factory=uuid4)
    _transactions: list[Transaction] = field(default_factory=list, repr=False)

    def process_transaction(self, transaction: Transaction) -> None:
        raise NotImplementedError("transaction processing is implemented in Stage 2")

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        """Read-only snapshot of the account's transaction history."""

        return tuple(self._transactions)


@dataclass(slots=True)
class Customer:

    name: str
    email: str
    customer_id: UUID = field(default_factory=uuid4)
    _account_ids: set[UUID] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("customer name is required")
        if "@" not in self.email:
            raise ValueError("email must contain '@'")

    @property
    def account_ids(self) -> frozenset[UUID]:
        return frozenset(self._account_ids)


@dataclass(slots=True)
class Bank:

    name: str
    _customers: dict[UUID, Customer] = field(default_factory=dict, repr=False)
    _accounts: dict[UUID, Account] = field(default_factory=dict, repr=False)

    @property
    def customers(self) -> tuple[Customer, ...]:
        return tuple(self._customers.values())

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(self._accounts.values())

    def register_customer(self, customer: Customer) -> None:
        if customer.customer_id in self._customers:
            raise ValueError("customer is already registered")
        self._customers[customer.customer_id] = customer

    def register_account(self, account: Account) -> None:
        if account.account_id in self._accounts:
            raise ValueError("account is already registered")
        customer = self._customers.get(account.owner_id)
        if customer is None:
            raise ValueError("account owner must be a registered customer")
        self._accounts[account.account_id] = account
        customer._account_ids.add(account.account_id)

    def transaction_history(self) -> tuple[Transaction, ...]:

        history: Iterable[Transaction] = (
            transaction
            for account in self._accounts.values()
            for transaction in account.transactions
        )
        return tuple(sorted(history, key=lambda item: item.occurred_at))