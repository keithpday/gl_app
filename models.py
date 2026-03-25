"""Core data models. These are UI-agnostic so a future GUI can reuse them."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class JournalLine:
    account: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    doc_type: str = ""
    doc_nbr: str = ""
    ext_doc: str = ""
    comment: str = ""


@dataclass
class JournalEntry:
    entry_date: date
    description: str
    comment: str = ""
    seq: int | None = None
    lines: list[JournalLine] = field(default_factory=list)

    def total_debits(self) -> Decimal:
        return sum((line.debit for line in self.lines), Decimal("0.00"))

    def total_credits(self) -> Decimal:
        return sum((line.credit for line in self.lines), Decimal("0.00"))

    def is_balanced(self) -> bool:
        return self.total_debits() == self.total_credits()


@dataclass
class OpenInvoice:
    account: str
    doc_nbr: str
    balance_remaining: Decimal


@dataclass
class CDProduct:
    cd_id: str
    cd_name: str
    sell_price: Decimal
    unit_cost: Decimal
    sales_account: str
    cogs_account: str
    inventory_account: str
    has_royalty: bool
    royalty_artist_percent: Decimal
    royalty_musicians_percent: Decimal
    royalty_artist_expense_account: str
    royalty_artist_payable_account: str
    royalty_musicians_expense_account: str
    royalty_musicians_payable_account: str
    default_comment: str
    category: str
    ammo_qty: Decimal = Decimal("0.00")
    duo_gear_qty: Decimal = Decimal("0.00")
    shelf_qty: Decimal = Decimal("0.00")
    last_inventory_date: str = ""


@dataclass
class RecurringEntrySummary:
    seq: int
    description: str
    default_amount: Decimal
    line_count: int
