"""Workflow handlers that gather input and call the business logic."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re

from config import (
    CASH_ACCOUNT,
    CASH_IN_CD_CASE_ACCOUNT,
    CASH_IN_DUO_GEAR_ACCOUNT,
    CHECKING_ACCOUNT,
    SALES_PERFORMANCES_ACCOUNT,
    VENMO_ACCOUNT,
)
from models import CDProduct, JournalEntry, JournalLine
from journal_logic import (
    build_cd_sales_entry,
    build_mobile_deposit_entry,
    build_transfer_entry,
    validate_entry,
)
from prompts import (
    prompt_account_by_prefix,
    prompt_account_from_list,
    prompt_amount,
    prompt_amount_with_default,
    prompt_check_number,
    prompt_date,
    prompt_int,
    prompt_open_invoice_or_manual,
    prompt_seq_number,
    prompt_text,
    prompt_transaction_number,
)
from sheets_api import SheetsClient


def debug_print(debug: bool, message: str) -> None:
    if debug:
        print(f"[DEBUG:handler] {message}")


def handle_transfer_entry(debug: bool = False) -> JournalEntry:
    print("\nTransfer Between Checking and Savings")
    entry_date = prompt_date()
    amount = prompt_amount()

    debug_print(debug, f"Transfer date entered: {entry_date}")
    debug_print(debug, f"Transfer amount entered: {amount}")

    print("1. Checking -> Savings")
    print("2. Savings -> Checking")
    direction_choice = prompt_text("Direction")

    direction = {
        "1": "checking_to_savings",
        "2": "savings_to_checking",
    }.get(direction_choice)
    if direction is None:
        raise ValueError("Direction must be 1 or 2.")

    comment = prompt_text("Comment")

    debug_print(debug, f"Transfer direction selected: {direction}")
    debug_print(debug, f"Transfer comment: {comment}")

    entry = build_transfer_entry(
        entry_date=entry_date,
        amount=amount,
        direction=direction,
        comment=comment,
    )

    debug_print(debug, f"Built transfer entry with {len(entry.lines)} lines")
    return entry


def handle_mobile_deposit_entry(
    client: SheetsClient,
    valid_accounts: list[str],
    debug: bool = False,
) -> JournalEntry:
    print("\nMobile Deposit to Checking")
    entry_date = prompt_date()
    amount = prompt_amount()
    description = prompt_text("Description", default="Mobile Deposit to Checking")

    debug_print(debug, f"Mobile deposit date entered: {entry_date}")
    debug_print(debug, f"Mobile deposit amount entered: {amount}")
    debug_print(debug, f"Mobile deposit description: {description}")

    credit_account = prompt_account_by_prefix(
        valid_accounts,
        prefix="Rcvbls",
        label="Select receivables account",
    )
    debug_print(debug, f"Mobile deposit receivables account selected: {credit_account}")

    open_invoices = client.get_open_invoices_for_account(credit_account)
    debug_print(debug, f"Open invoices found: {len(open_invoices)}")

    receivables_doc_nbr = prompt_open_invoice_or_manual(open_invoices)
    receivables_doc_type = "PMT"
    receivables_ext_doc = prompt_check_number()
    comment = prompt_text("Comment")

    debug_print(debug, f"Selected/entered invoice number: {receivables_doc_nbr}")
    debug_print(debug, f"Generated ExtDoc for mobile deposit: {receivables_ext_doc}")
    debug_print(debug, f"Mobile deposit comment: {comment}")

    entry = build_mobile_deposit_entry(
        entry_date=entry_date,
        amount=amount,
        credit_account=credit_account,
        description=description,
        comment=comment,
        receivables_doc_type=receivables_doc_type,
        receivables_doc_nbr=receivables_doc_nbr,
        receivables_ext_doc=receivables_ext_doc,
    )

    debug_print(debug, f"Built mobile deposit entry with {len(entry.lines)} lines")
    return entry


def handle_auto_deposit_entry(
    client: SheetsClient,
    valid_accounts: list[str],
    debug: bool = False,
) -> JournalEntry:
    print("\nAuto Deposit to Checking")
    entry_date = prompt_date()
    amount = prompt_amount()
    description = prompt_text("Description", default="Auto Deposit to Checking")

    debug_print(debug, f"Auto deposit date entered: {entry_date}")
    debug_print(debug, f"Auto deposit amount entered: {amount}")
    debug_print(debug, f"Auto deposit description: {description}")

    credit_account = prompt_account_by_prefix(
        valid_accounts,
        prefix="Rcvbls",
        label="Select receivables account",
    )
    debug_print(debug, f"Auto deposit receivables account selected: {credit_account}")

    open_invoices = client.get_open_invoices_for_account(credit_account)
    debug_print(debug, f"Open invoices found: {len(open_invoices)}")

    receivables_doc_nbr = prompt_open_invoice_or_manual(open_invoices)
    receivables_doc_type = "ACH"
    receivables_ext_doc = prompt_transaction_number()
    comment = prompt_text("Comment")

    debug_print(debug, f"Selected/entered invoice number: {receivables_doc_nbr}")
    debug_print(debug, f"Generated ExtDoc for auto deposit: {receivables_ext_doc}")
    debug_print(debug, f"Auto deposit comment: {comment}")

    entry = build_mobile_deposit_entry(
        entry_date=entry_date,
        amount=amount,
        credit_account=credit_account,
        description=description,
        comment=comment,
        receivables_doc_type=receivables_doc_type,
        receivables_doc_nbr=receivables_doc_nbr,
        receivables_ext_doc=receivables_ext_doc,
    )

    debug_print(debug, f"Built auto deposit entry with {len(entry.lines)} lines")
    return entry


def handle_recurring_entry(client: SheetsClient, debug: bool = False) -> JournalEntry:
    print("\nPost Recurring Entry")
    client.display_recurring_entries()

    seq = prompt_seq_number()
    debug_print(debug, f"Recurring Seq selected: {seq}")

    entry = client.get_recurring_entry_by_seq(seq)
    debug_print(debug, f"Loaded recurring entry with {len(entry.lines)} lines")

    entry.entry_date = prompt_date()
    debug_print(debug, f"Recurring entry date overridden to: {entry.entry_date}")

    if len(entry.lines) == 2:
        default_amount = _first_nonzero_amount(entry)
        debug_print(debug, f"Two-line recurring entry default amount: {default_amount}")
        new_amount = prompt_amount_with_default("Amount", default_amount)
        debug_print(debug, f"Two-line recurring entry overridden amount: {new_amount}")
        _apply_single_amount(entry, new_amount)
    else:
        debug_print(debug, "Multi-line recurring entry: prompting per nonzero line")
        _prompt_line_amounts(entry, debug=debug)

    validate_entry(entry)
    debug_print(debug, "Recurring entry validated successfully")
    return entry


def _first_nonzero_amount(entry: JournalEntry) -> Decimal:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            return line.debit
        if line.credit != Decimal("0.00"):
            return line.credit
    return Decimal("0.00")


def _apply_single_amount(entry: JournalEntry, amount: Decimal) -> None:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            line.debit = amount
        if line.credit != Decimal("0.00"):
            line.credit = amount


def _prompt_line_amounts(entry: JournalEntry, debug: bool = False) -> None:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            label = f"Debit amount for {line.account}"
            line.debit = prompt_amount_with_default(label, line.debit)
            debug_print(debug, f"Updated debit for {line.account}: {line.debit}")
        elif line.credit != Decimal("0.00"):
            label = f"Credit amount for {line.account}"
            line.credit = prompt_amount_with_default(label, line.credit)
            debug_print(debug, f"Updated credit for {line.account}: {line.credit}")


def handle_performance_entry(client: SheetsClient, debug: bool = False) -> JournalEntry:
    print("\nPost Performance Entry")
    
    # Get performance schedule
    schedule_rows = client.get_performance_schedule()
    if not schedule_rows:
        raise ValueError("No performances found in schedule.")
    
    # Display options
    print("\nAvailable Performances:")
    for idx, row in enumerate(schedule_rows, start=1):
        venue = row.get("Venue", "")
        date_str = row.get("Date", "")
        pays = row.get("Pays", "0")
        band_count = row.get("#in Bnd", "0")
        print(f"{idx}. {date_str} - {venue} (Pays: {pays}, Band: {band_count})")
    
    # Get user selection
    while True:
        try:
            choice = int(input("Select performance (number): ").strip())
            if 1 <= choice <= len(schedule_rows):
                selected_gig = schedule_rows[choice - 1]
                break
            else:
                print(f"Please enter a number between 1 and {len(schedule_rows)}.")
        except ValueError:
            print("Please enter a valid number.")
    
    debug_print(debug, f"Selected performance: {selected_gig.get('Venue', '')}")
    
    # Get band members data
    band_members = client.get_band_members()
    debug_print(debug, f"Loaded {len(band_members)} band members")
    
    # Extract gig data
    venue = selected_gig.get("Venue", "").strip()
    date_str = selected_gig.get("Date", "").strip()
    pays_str = selected_gig.get("Pays", "0").strip()
    band_count_str = selected_gig.get("#in Bnd", "0").strip()
    
    # Clean up strings by removing non-numeric characters (except decimal point for pays)
    pays_str = re.sub(r'[^\d.]', '', pays_str)
    band_count_str = re.sub(r'[^\d]', '', band_count_str)
    
    try:
        pays_amount = Decimal(pays_str) if pays_str else Decimal("0")
        band_count = int(band_count_str) if band_count_str else 0
    except (ValueError, TypeError):
        raise ValueError(f"Invalid pays amount '{selected_gig.get('Pays', '')}' or band count '{selected_gig.get('#in Bnd', '')}'")
    
    # Parse the performance date
    try:
        entry_date = datetime.strptime(date_str, "%m/%d/%Y").date()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date format in schedule: '{date_str}'")
    
    # Calculate default sales amount
    default_sales = pays_amount * band_count
    
    # Prompt for sales amount with default
    sales_amount = prompt_amount_with_default("Sales amount", default_sales)
    
    # Calculate amounts
    default_sales = pays_amount * band_count
    cash_amount = default_sales  # Cash amount equals the original calculated sales
    member_pay = pays_amount   # Each member gets the full pays amount
    
    debug_print(debug, f"Performance date: {entry_date}, Sales: ${sales_amount}, Cash: ${cash_amount}, Member pay: ${member_pay}")
    
    # Prompt for comment
    comment = prompt_text("Comment (optional)").strip()
    
    # Build journal entry
    description = f"Performance {venue}"
    
    entry = JournalEntry(
        entry_date=entry_date,
        description=description,
        comment="",  # Will be set on first line only
        lines=[],
    )
    
    # Generate DocNbr: days since Nov 7, 2023 + First letters of venue name (inclusive)
    venue_words = venue.split()
    base_date = date(2023, 11, 7)
    days_since = (entry_date - base_date).days + 1
    
    # After 3/21/2026 or if invoice number > 866, limit to first 4 words only
    cutoff_date = date(2026, 3, 21)
    if entry_date > cutoff_date or days_since > 866:
        words_to_use = venue_words[:4]  # First 4 words max
    else:
        words_to_use = venue_words  # All words
    
    doc_suffix = "".join(word[0].upper() for word in words_to_use if word)
    doc_nbr = f"{days_since}{doc_suffix}"
    
    # Sales line (credit) - first line gets the comment
    entry.lines.append(JournalLine(
        account=SALES_PERFORMANCES_ACCOUNT,
        debit=Decimal("0.00"),
        credit=sales_amount,
        comment=comment if comment else "",
    ))
    
    # Receivables line (debit)
    receivables_account = f"Rcvbls {venue}"
    entry.lines.append(JournalLine(
        account=receivables_account,
        debit=sales_amount,
        credit=Decimal("0.00"),
        doc_type="INV",
        doc_nbr=doc_nbr,
    ))
    
    # Cash line (credit)
    entry.lines.append(JournalLine(
        account=CASH_ACCOUNT,
        debit=Decimal("0.00"),
        credit=cash_amount,
    ))
    
    # Band member pay lines (debit)
    band_positions = ["Vocal", "Piano", "Bass", "Drums", "Guitar", "Vibes"]
    paid_members = set()
    
    for position in band_positions:
        member_alias = selected_gig.get(position, "").strip()
        # Treat "None" (string) the same as blank/empty
        if member_alias and member_alias != "None" and member_alias not in paid_members:
            member_data = band_members.get(member_alias)
            if member_data:
                member_name = member_data.get("Name", member_alias)
                pay_account = f"*Pay {member_name}"
                entry.lines.append(JournalLine(
                    account=pay_account,
                    debit=member_pay,
                    credit=Decimal("0.00"),
                ))
                paid_members.add(member_alias)
                debug_print(debug, f"Added pay line for {member_name}: ${member_pay}")
    
    # Validate entry
    validate_entry(entry)
    debug_print(debug, f"Performance entry validated with {len(entry.lines)} lines")
    
    # Move completed gig to history
    try:
        client.move_completed_gig_to_history(selected_gig)
        debug_print(debug, "Moved completed gig to history")
    except Exception as e:
        print(f"Warning: Could not move gig to history: {e}")
        # Don't fail the entry for this
    
    return entry


def handle_cd_sales_entry(client: SheetsClient, debug: bool = False) -> JournalEntry:
    print("\nCD Sales / Donation Jar Entry")

    entry_date = prompt_date()
    debug_print(debug, f"CD sales date entered: {entry_date}")

    products = client.get_active_cd_products()
    if not products:
        raise ValueError("No active CD products found in CD_Master.")

    print("\nActive CDs:")
    for idx, product in enumerate(products, start=1):
        print(
            f"{idx}. {product.cd_name} - Sell: {product.sell_price:.2f}, Cost: {product.unit_cost:.2f}, "
            f"Sales Acct: {product.sales_account}"
        )

    while True:
        try:
            selection = int(input("Select CD type (number): ").strip())
            if 1 <= selection <= len(products):
                cd = products[selection - 1]
                break
            print(f"Please enter a number between 1 and {len(products)}.")
        except ValueError:
            print("Please enter a valid number.")

    quantity = Decimal(prompt_int("Quantity sold"))

    payment_method = prompt_account_from_list(
        ["Cash", "Check", "Helcim", "Venmo"],
        label="Payment method",
    )

    fee_total = prompt_amount_with_default("Total fees", Decimal("0.00"))
    if payment_method in {"Cash", "Check"} and fee_total > Decimal("0.00"):
        print("Note: Cash/Check sales should have zero fees; overriding fee to 0.00.")
        fee_total = Decimal("0.00")

    sold_from_location = prompt_account_from_list(
        ["From Ammo_Qty", "From Duo_Gear_Qty"],
        label="Sold from location",
    )

    total_collected = prompt_amount_with_default("Total collected", cd.sell_price * quantity)
    if total_collected < Decimal("0.00"):
        raise ValueError("Total collected cannot be negative.")

    comment_default = cd.default_comment or cd.cd_name
    comment = prompt_text("Comment", default=comment_default)

    # Determine deposit account by payment method and source location
    if sold_from_location == "From Duo_Gear_Qty":
        deposit_account = CASH_IN_DUO_GEAR_ACCOUNT
    else:
        deposit_account = {
            "Cash": CASH_IN_CD_CASE_ACCOUNT,
            "Check": CHECKING_ACCOUNT,
            "Helcim": CHECKING_ACCOUNT,
            "Venmo": VENMO_ACCOUNT,
        }.get(payment_method, CASH_IN_CD_CASE_ACCOUNT)

    debug_print(debug, f"CD selected: {cd.cd_name}")
    debug_print(debug, f"Quantity entered: {quantity}")
    debug_print(debug, f"Payment method entered: {payment_method}")
    debug_print(debug, f"Deposit account: {deposit_account}")
    debug_print(debug, f"Sold from location: {sold_from_location}")
    debug_print(debug, f"Fee total entered: {fee_total}")
    debug_print(debug, f"Total collected entered: {total_collected}")
    debug_print(debug, f"Comment: {comment}")

    entry = build_cd_sales_entry(
        entry_date=entry_date,
        cd_product=cd,
        quantity=quantity,
        payment_method=payment_method,
        deposit_account=deposit_account,
        fee_total=fee_total,
        total_collected=total_collected,
        sold_from_location=sold_from_location,
        comment=comment,
    )

    if total_collected < (cd.sell_price * quantity):
        print("\nWARNING: Total collected is less than expected sales revenue.")
        debug_print(debug, "Total collected less than sales revenue")

    debug_print(debug, f"CD sales entry built with {len(entry.lines)} lines")
    return entry
