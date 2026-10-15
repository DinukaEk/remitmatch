"""Evaluate synthetic fixture top-1 retrieval against rule-only baseline.

Honest limitation: synthetic data is a smoke test, not a real-world accuracy claim.
Run: python scripts/evaluate.py
"""
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from matcher import load_csv, reconcile
from model import load_encoder


def score(results, truth):
    eligible = [(r, truth[r.payment.payment_id]) for r in results if truth.get(r.payment.payment_id)]
    correct = sum(r.candidates[0].invoice_id == expected for r, expected in eligible)
    return correct, len(eligible)


def main():
    invoices = load_csv((ROOT / "sample_data/invoices.csv").read_bytes(), "invoices")
    payments = load_csv((ROOT / "sample_data/bank_payments.csv").read_bytes(), "payments")
    with open(ROOT / "sample_data/expected_matches.csv", newline="", encoding="utf-8") as fh:
        truth = {r["payment_id"]: r["expected_invoice_id"] for r in csv.DictReader(fh)}
    rule_only = reconcile(payments, invoices, encoder=None, use_embeddings=False)
    model = load_encoder()
    ai = reconcile(payments, invoices, encoder=model)
    a, b = score(ai, truth)
    c, d = score(rule_only, truth)
    print(f"Synthetic top-1 retrieval, open-weight model + rules: {a}/{b}")
    print(f"Synthetic top-1 retrieval, rules without embeddings: {c}/{d}")
    print("Not a production accuracy benchmark; manual review is mandatory.")
    print("\nPayment ID | AI suggestion | Baseline suggestion | Expected")
    for x, y in zip(ai, rule_only):
        print(f"{x.payment.payment_id:10} | {x.candidates[0].invoice_id:13} | {y.candidates[0].invoice_id:19} | {truth.get(x.payment.payment_id) or '(none)'}")

if __name__ == "__main__":
    main()
