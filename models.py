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
class RecurringEntrySummary:
    seq: int
    description: str
    default_amount: Decimal
    line_count: int
