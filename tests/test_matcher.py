from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from matcher import (
    Invoice, Payment, export_approved, invoice_id_mentioned, load_csv,
    parse_amount, reconcile, spreadsheet_safe,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeEncoder:
    """An injectable encoder proves scoring can be tested without network/model fetch."""
    def encode(self, sentences, normalize_embeddings=True):
        vectors = []
        for text in sentences:
            if "sunrise" in text or "bakery" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "ocean" in text or "printing" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


def inv(code="INV-12", name="Sunrise Bakers", amt="1200", d="2026-10-01"):
    return Invoice(code, name, Decimal(amt), date.fromisoformat(d))


def pay(code="PAY-1", reference="SUNRISE BAKERY payment INV-12", amt="1200", d="2026-10-02"):
    return Payment(code, date.fromisoformat(d), Decimal(amt), reference)


def test_load_sample_files():
    invoices = load_csv((ROOT / "sample_data/invoices.csv").read_bytes(), "invoices")
    payments = load_csv((ROOT / "sample_data/bank_payments.csv").read_bytes(), "payments")
    assert len(invoices) == 10
    assert len(payments) == 11
    assert invoices[0].aliases == ("Sunrise Bakery", "Sunrise Bakes")


def test_csv_rejects_duplicate_ids():
    raw = "payment_id,date,amount,reference\nA,2026-10-01,100,one\nA,2026-10-02,200,two\n"
    with pytest.raises(ValueError, match="Duplicate"):
        load_csv(raw, "payments")


def test_csv_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        load_csv("invoice_id,amount\nA,100", "invoices")


def test_csv_rejects_bad_date_and_negative_amount():
    with pytest.raises(ValueError, match="line 2"):
        load_csv("payment_id,date,amount,reference\nA,no-date,10,test", "payments")
    with pytest.raises(ValueError, match="positive"):
        parse_amount("-1")


def test_amount_parsing_not_float():
    assert parse_amount("1,200.20") == Decimal("1200.20")
    assert parse_amount("0.1") + parse_amount("0.2") == Decimal("0.30")


def test_id_boundaries_avoid_false_match():
    assert invoice_id_mentioned("CEFT INV 1001 Sunrise", "INV-1001")
    assert invoice_id_mentioned("CEFT INV-1001 Sunrise", "INV-1001")
    assert not invoice_id_mentioned("CEFT INV-10010 Sunrise", "INV-1001")


def test_model_required_for_ai():
    with pytest.raises(ValueError, match="encoder"):
        reconcile([pay()], [inv()], None)


def test_ai_sorts_candidates_and_keeps_suggested_only():
    results = reconcile([pay()], [inv(), inv("INV-13", "Blue Ocean Printing")], FakeEncoder())
    assert results[0].candidates[0].invoice_id == "INV-12"
    assert results[0].status == "Strong suggestion"
    assert results[0].candidates[0].invoice_id_in_reference


def test_different_amount_is_reviewed_not_approved():
    results = reconcile([pay(amt="1700")], [inv()], FakeEncoder())
    assert "Review" in results[0].status
    with pytest.raises(ValueError, match="different-amount"):
        export_approved(results, {"PAY-1": "INV-12"})


def test_repeated_bank_row_is_flagged():
    results = reconcile([pay("A"), pay("B")], [inv()], FakeEncoder())
    assert all(r.status == "Review: repeated transfer" for r in results)


def test_invoice_collision_is_flagged():
    results = reconcile([
        pay("A", "SUNRISE INV-12"),
        pay("B", "SUNRISE BAKERS different deposit"),
    ], [inv()], FakeEncoder())
    assert all(r.status == "Review: invoice collision" for r in results)


def test_exports_only_approved_human_selection():
    results = reconcile([pay()], [inv()], FakeEncoder())
    assert len(export_approved(results, {}).splitlines()) == 1  # header only
    rows = export_approved(results, {"PAY-1": "INV-12"})
    assert "APPROVED_BY_REVIEWER" in rows
    assert "PAY-1" in rows


def test_double_approval_rejected():
    results = reconcile([pay("A"), pay("B", "Sunrise second transfer")], [inv()], FakeEncoder())
    with pytest.raises(ValueError, match="twice"):
        export_approved(results, {"A": "INV-12", "B": "INV-12"})


def test_unknown_invoice_approval_rejected():
    results = reconcile([pay()], [inv()], FakeEncoder())
    with pytest.raises(ValueError, match="not an offered candidate"):
        export_approved(results, {"PAY-1": "INV-9999"})


def test_one_cent_mismatch_not_exact():
    results = reconcile([pay(amt="1200.01")], [inv()], FakeEncoder())
    assert results[0].candidates[0].exact_amount is False
    assert "Review" in results[0].status


def test_amount_overprecision_rejected():
    with pytest.raises(ValueError, match="more than two decimal"):
        parse_amount("0.001")


def test_spreadsheet_formula_injection_prevented():
    assert spreadsheet_safe("=HYPERLINK(\"http://bad\")").startswith("'")
    assert spreadsheet_safe("ordinary bank transfer") == "ordinary bank transfer"
    p = pay(reference="=1+1")
    matched = reconcile([p], [inv()], FakeEncoder())
    assert "'=1+1" in export_approved(matched, {"PAY-1": "INV-12"})
