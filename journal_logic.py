"""Business logic for validating and building journal entries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from config import (
    CASH_IN_CD_CASE_ACCOUNT,
    CASH_PAYMENT_FEES_ACCOUNT,
    CHECKING_ACCOUNT,
    DONATIONS_ACCOUNT,
    SAVINGS_ACCOUNT,
)
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


def build_cd_sales_entry(
    entry_date: date,
    cd_product: "CDProduct",
    quantity: Decimal,
    payment_method: str,
    deposit_account: str,
    fee_total: Decimal,
    total_collected: Decimal,
    sold_from_location: str,
    comment: str,
) -> JournalEntry:
    from models import CDProduct

    if quantity <= Decimal("0.00"):
        raise JournalLogicError("Quantity must be greater than zero.")

    sales_revenue = (cd_product.sell_price * quantity).quantize(CENT)
    cogs_total = (cd_product.unit_cost * quantity).quantize(CENT)
    donation_amount = (total_collected - sales_revenue).quantize(CENT)
    fee_per_unit = (fee_total / quantity).quantize(CENT) if quantity != Decimal("0.00") else Decimal("0.00")

    net_per_unit = (cd_product.sell_price - cd_product.unit_cost - fee_per_unit).quantize(CENT)
    if net_per_unit < Decimal("0.00"):
        net_per_unit = Decimal("0.00")

    artist_royalty_total = (net_per_unit * cd_product.royalty_artist_percent * quantity).quantize(CENT)
    musician_royalty_total = (net_per_unit * cd_product.royalty_musicians_percent * quantity).quantize(CENT)

    entry = JournalEntry(
        entry_date=entry_date,
        description=f"CD Sales / Donation Jar - {cd_product.cd_name} ({sold_from_location})",
        comment=comment,
        lines=[],
    )


    entry.lines.append(JournalLine(
        account=deposit_account,
        debit=total_collected,
        credit=Decimal("0.00"),
    ))

    entry.lines.append(JournalLine(
        account=cd_product.sales_account,
        debit=Decimal("0.00"),
        credit=sales_revenue,
    ))

    if donation_amount > Decimal("0.00"):
        entry.lines.append(JournalLine(
            account=DONATIONS_ACCOUNT,
            debit=Decimal("0.00"),
            credit=donation_amount,
        ))

    entry.lines.append(JournalLine(
        account=cd_product.cogs_account,
        debit=cogs_total,
        credit=Decimal("0.00"),
    ))
    entry.lines.append(JournalLine(
        account=cd_product.inventory_account,
        debit=Decimal("0.00"),
        credit=cogs_total,
    ))

    if fee_total > Decimal("0.00"):
        entry.lines.append(JournalLine(
            account=CASH_PAYMENT_FEES_ACCOUNT,
            debit=fee_total,
            credit=Decimal("0.00"),
        ))
        entry.lines.append(JournalLine(
            account=deposit_account,
            debit=Decimal("0.00"),
            credit=fee_total,
        ))

    if cd_product.has_royalty and artist_royalty_total > Decimal("0.00"):
        entry.lines.append(JournalLine(
            account=cd_product.royalty_artist_expense_account,
            debit=artist_royalty_total,
            credit=Decimal("0.00"),
        ))
        entry.lines.append(JournalLine(
            account=cd_product.royalty_artist_payable_account,
            debit=Decimal("0.00"),
            credit=artist_royalty_total,
        ))

    if cd_product.has_royalty and musician_royalty_total > Decimal("0.00"):
        entry.lines.append(JournalLine(
            account=cd_product.royalty_musicians_expense_account,
            debit=musician_royalty_total,
            credit=Decimal("0.00"),
        ))
        entry.lines.append(JournalLine(
            account=cd_product.royalty_musicians_payable_account,
            debit=Decimal("0.00"),
            credit=musician_royalty_total,
        ))

    validate_entry(entry)
    return entry
