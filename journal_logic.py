"""Business logic for validating and building journal entries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from config import CHECKING_ACCOUNT, SAVINGS_ACCOUNT
from models import JournalEntry, JournalLine

CENT = Decimal("0.01")


class JournalLogicError(Exception):
    """Raised for business-rule problems."""


def money(value: str | int | float | Decimal) -> Decimal:
    amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    if amount <= Decimal("0.00"):
        raise JournalLogicError("Amount must be greater than zero.")
    return amount


def validate_account(account: str, valid_accounts: Iterable[str]) -> str:
    cleaned = account.strip()
    valid_set = {item.strip() for item in valid_accounts if item and item.strip()}
    if cleaned not in valid_set:
        raise JournalLogicError(f"Invalid account: {cleaned}")
    return cleaned


def validate_entry(entry: JournalEntry) -> None:
    if not entry.lines:
        raise JournalLogicError("Journal entry must contain at least one line.")


def build_transfer_entry(
    entry_date: date,
    amount: Decimal,
    direction: str,
    comment: str,
) -> JournalEntry:
    direction_key = direction.strip().lower()

    if direction_key == "checking_to_savings":
        description = "Transfer Checking to Savings"
        debit_account = SAVINGS_ACCOUNT
        credit_account = CHECKING_ACCOUNT
    elif direction_key == "savings_to_checking":
        description = "Transfer Savings to Checking"
        debit_account = CHECKING_ACCOUNT
        credit_account = SAVINGS_ACCOUNT
    else:
        raise JournalLogicError("Unknown transfer direction.")

    entry = JournalEntry(
        entry_date=entry_date,
        description=description,
        comment=comment,
        lines=[
            JournalLine(
                account=debit_account,
                debit=amount,
                credit=Decimal("0.00"),
                doc_type="",
                doc_nbr="",
                ext_doc="",
            ),
            JournalLine(
                account=credit_account,
                debit=Decimal("0.00"),
                credit=amount,
                doc_type="",
                doc_nbr="",
                ext_doc="",
            ),
        ],
    )
    validate_entry(entry)
    return entry


def build_mobile_deposit_entry(
    entry_date: date,
    amount: Decimal,
    credit_account: str,
    description: str,
    comment: str,
    receivables_doc_type: str = "",
    receivables_doc_nbr: str = "",
    receivables_ext_doc: str = "",
) -> JournalEntry:
    is_receivables = "rcvbls" in credit_account.lower()

    entry = JournalEntry(
        entry_date=entry_date,
        description=description.strip() or "Mobile Deposit to Checking",
        comment=comment,
        lines=[
            JournalLine(
                account=CHECKING_ACCOUNT,
                debit=amount,
                credit=Decimal("0.00"),
                doc_type="",
                doc_nbr="",
                ext_doc="",
            ),
            JournalLine(
                account=credit_account,
                debit=Decimal("0.00"),
                credit=amount,
                doc_type=receivables_doc_type if is_receivables else "",
                doc_nbr=receivables_doc_nbr if is_receivables else "",
                ext_doc=receivables_ext_doc if is_receivables else "",
            ),
        ],
    )
    validate_entry(entry)
    return entry
