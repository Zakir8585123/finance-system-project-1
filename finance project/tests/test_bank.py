
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from your_module import (
    Currency,
    Money,
    Transaction,
    TransactionType,
    Account,
    Customer,
    Bank,
)

class TestMoney:

    def test_create_money(self):
        money = Money(Decimal("100.50"), Currency.USD)

        assert money.amount == Decimal("100.50")
        assert money.currency == Currency.USD

    def test_normalize_amount(self):
        money = Money(100, Currency.USD)

        assert money.amount == Decimal("100")

    def test_reject_non_finite_amount(self):
        with pytest.raises(ValueError):
            Money(Decimal("NaN"), Currency.USD)

        with pytest.raises(ValueError):
            Money(Decimal("Infinity"), Currency.USD)

    def test_reject_invalid_currency(self):
        with pytest.raises(TypeError):
            Money(100, "USD")

    def test_add_money(self):
        first = Money(Decimal("100"), Currency.USD)
        second = Money(Decimal("50"), Currency.USD)

        result = first + second

        assert result.amount == Decimal("150")
        assert result.currency == Currency.USD

    def test_subtract_money(self):
        first = Money(Decimal("100"), Currency.USD)
        second = Money(Decimal("30"), Currency.USD)

        result = first - second

        assert result.amount == Decimal("70")

    def test_reject_different_currencies(self):
        usd = Money(100, Currency.USD)
        eur = Money(100, Currency.EUR)

        with pytest.raises(ValueError):
            usd + eur

        with pytest.raises(ValueError):
            usd - eur

    def test_reject_non_money_arithmetic(self):
        money = Money(100, Currency.USD)

        with pytest.raises(TypeError):
            money + 100

class TestTransaction:

    def create_transaction(self, **kwargs):
        defaults = {
            "transaction_id": uuid4(),
            "transaction_type": TransactionType.DEPOSIT,
            "amount": Money(100, Currency.USD),
            "occurred_at": datetime.now(timezone.utc),
        }

        defaults.update(kwargs)
        return Transaction(**defaults)

    def test_create_transaction(self):
        transaction = self.create_transaction()

        assert transaction.amount.amount == Decimal("100")
        assert transaction.transaction_type == TransactionType.DEPOSIT

    def test_reject_zero_amount(self):
        with pytest.raises(ValueError):
            self.create_transaction(
                amount=Money(0, Currency.USD)
            )

    def test_reject_negative_amount(self):
        with pytest.raises(ValueError):
            self.create_transaction(
                amount=Money(-100, Currency.USD)
            )

    def test_reject_naive_datetime(self):
        with pytest.raises(ValueError):
            self.create_transaction(
                occurred_at=datetime.now()
            )

    def test_accept_timezone_aware_datetime(self):
        transaction = self.create_transaction(
            occurred_at=datetime.now(timezone.utc)
        )

        assert transaction.occurred_at.tzinfo is not None

    def test_reject_whitespace_description(self):
        with pytest.raises(ValueError):
            self.create_transaction(description="   ")

class TestAccount:

    def test_create_account(self):
        owner_id = uuid4()

        account = Account(
            owner_id=owner_id,
            currency=Currency.USD,
        )

        assert account.owner_id == owner_id
        assert account.currency == Currency.USD
        assert account.account_id is not None

    def test_account_has_unique_id(self):
        owner_id = uuid4()

        account1 = Account(owner_id, Currency.USD)
        account2 = Account(owner_id, Currency.USD)

        assert account1.account_id != account2.account_id

    def test_transactions_initially_empty(self):
        account = Account(uuid4(), Currency.USD)

        assert account.transactions == ()

    def test_transactions_returns_snapshot(self):
        account = Account(uuid4(), Currency.USD)

        snapshot = account.transactions

        assert isinstance(snapshot, tuple)

        account._transactions.append(
            Transaction(
                transaction_id=uuid4(),
                transaction_type=TransactionType.DEPOSIT,
                amount=Money(100, Currency.USD),
                occurred_at=datetime.now(timezone.utc),
            )
        )

        assert snapshot == ()
        assert len(account.transactions) == 1

class TestCustomer:

    def test_create_customer(self):
        customer = Customer(
            name="John Smith",
            email="john@example.com",
        )

        assert customer.name == "John Smith"
        assert customer.email == "john@example.com"
        assert customer.customer_id is not None

    def test_reject_empty_name(self):
        with pytest.raises(ValueError):
            Customer(name="", email="john@example.com")

    def test_reject_whitespace_name(self):
        with pytest.raises(ValueError):
            Customer(name="   ", email="john@example.com")

    def test_reject_invalid_email(self):
        with pytest.raises(ValueError):
            Customer(name="John", email="invalid-email")

    def test_account_ids_initially_empty(self):
        customer = Customer("John", "john@example.com")

        assert customer.account_ids == frozenset()

    def test_account_ids_are_immutable_snapshot(self):
        customer = Customer("John", "john@example.com")

        snapshot = customer.account_ids

        customer._account_ids.add(uuid4())

        assert snapshot == frozenset()
        assert len(customer.account_ids) == 1

class TestBank:

    def setup_method(self):
        self.bank = Bank("Test Bank")

        self.customer = Customer(
            name="John Smith",
            email="john@example.com",
        )

        self.bank.register_customer(self.customer)

    def test_register_customer(self):
        assert self.customer in self.bank.customers

    def test_reject_duplicate_customer(self):
        with pytest.raises(ValueError):
            self.bank.register_customer(self.customer)

    def test_register_account(self):
        account = Account(
            owner_id=self.customer.customer_id,
            currency=Currency.USD,
        )

        self.bank.register_account(account)

        assert account in self.bank.accounts
        assert account.account_id in self.customer.account_ids

    def test_reject_duplicate_account(self):
        account = Account(
            owner_id=self.customer.customer_id,
            currency=Currency.USD,
        )

        self.bank.register_account(account)

        with pytest.raises(ValueError):
            self.bank.register_account(account)

    def test_reject_account_with_unregistered_owner(self):
        account = Account(
            owner_id=uuid4(),
            currency=Currency.USD,
        )

        with pytest.raises(ValueError):
            self.bank.register_account(account)

    def test_transaction_history_initially_empty(self):
        assert self.bank.transaction_history() == ()

    def test_transaction_history_sorted_by_date(self):
        account = Account(
            owner_id=self.customer.customer_id,
            currency=Currency.USD,
        )

        self.bank.register_account(account)

        older = Transaction(
            transaction_id=uuid4(),
            transaction_type=TransactionType.DEPOSIT,
            amount=Money(100, Currency.USD),
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        newer = Transaction(
            transaction_id=uuid4(),
            transaction_type=TransactionType.WITHDRAWAL,
            amount=Money(50, Currency.USD),
            occurred_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        account._transactions.extend([newer, older])

        history = self.bank.transaction_history()

        assert history == (older, newer)

    def test_transaction_history_combines_accounts(self):
        account1 = Account(
            self.customer.customer_id,
            Currency.USD,
        )

        account2 = Account(
            self.customer.customer_id,
            Currency.USD,
        )

        self.bank.register_account(account1)
        self.bank.register_account(account2)

        transaction1 = Transaction(
            uuid4(),
            TransactionType.DEPOSIT,
            Money(100, Currency.USD),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        transaction2 = Transaction(
            uuid4(),
            TransactionType.DEPOSIT,
            Money(200, Currency.USD),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        account1._transactions.append(transaction1)
        account2._transactions.append(transaction2)

        history = self.bank.transaction_history()

        assert len(history) == 2
        assert history == (transaction1, transaction2)
