"""Pure-Python, auditable bank-payment matching logic for RemitMatch.

An open-weight sentence embedding model supplies meaning-aware name matching.
Financial rules are deliberately deterministic and all decisions require approval.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Protocol, Sequence


class Encoder(Protocol):
    def encode(self, sentences: Sequence[str], normalize_embeddings: bool = True): ...


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    customer: str
    amount: Decimal
    date: date
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Payment:
    payment_id: str
    date: date
    amount: Decimal
    reference: str


@dataclass(frozen=True)
class Candidate:
    invoice_id: str
    customer: str
    amount: Decimal
    score: float
    semantic: float
    lexical: float
    exact_amount: bool
    invoice_id_in_reference: bool
    amount_difference: Decimal
    explanation: str


@dataclass(frozen=True)
class MatchResult:
    payment: Payment
    candidates: tuple[Candidate, ...]
    status: str
    note: str


STOPWORDS = {
    "pvt", "private", "ltd", "limited", "co", "company", "the", "and", "of",
    "bank", "online", "fund", "funds", "transfer", "trf", "ft", "deposit", "dep",
    "payment", "pay", "paid", "received", "credit", "cr", "ceft", "slips", "slip",
    "lkr", "cash", "to", "for", "from", "via", "ref", "reference", "txn",
    "transaction", "bill", "invoice", "inv", "mobile", "app", "branch", "rtgs",
}


def normalize(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))


def clean_name(value: str) -> str:
    tokens = normalize(value).split()
    return " ".join(t for t in tokens if t not in STOPWORDS and not t.isdigit()) or normalize(value)


def clean_reference(value: str) -> str:
    return clean_name(value)


def parse_amount(value: str) -> Decimal:
    try:
        cleaned = re.sub(r"(?i)\b(?:LKR|Rs\.?)\b", "", value).strip().replace(",", "")
        unrounded = Decimal(cleaned)
        number = unrounded.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid monetary amount: {value!r}") from exc
    if number != unrounded:
        raise ValueError(f"Amount has more than two decimal places: {value!r}")
    if not number.is_finite() or number <= 0:
        raise ValueError(f"Amount must be a positive finite number: {value!r}")
    return number


def load_csv(raw: bytes | str, kind: str) -> list[Invoice] | list[Payment]:
    """Parse local CSV bytes; fail closed for bad finance records.

    Dates are YYYY-MM-DD. No invalid rows are silently skipped.
    """
    if kind not in ("invoices", "payments"):
        raise ValueError("kind must be 'invoices' or 'payments'")
    try:
        body = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded (UTF-8 BOM is supported)") from exc
    reader = csv.DictReader(io.StringIO(body))
    required = (
        ("invoice_id", "customer", "amount", "date")
        if kind == "invoices"
        else ("payment_id", "date", "amount", "reference")
    )
    missing = [field for field in required if field not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"{kind.title()} CSV is missing columns: {', '.join(missing)}")
    rows = []
    seen_ids = set()
    for line, record in enumerate(reader, start=2):
        if not record or not any((v or "").strip() for v in record.values() if isinstance(v, str)):
            continue
        try:
            id_col = "invoice_id" if kind == "invoices" else "payment_id"
            record_id = (record[id_col] or "").strip()
            if not record_id:
                raise ValueError(f"{id_col} is empty")
            if record_id in seen_ids:
                raise ValueError(f"Duplicate {id_col}: {record_id}")
            seen_ids.add(record_id)
            amount = parse_amount(record["amount"] or "")
            transaction_date = date.fromisoformat((record["date"] or "").strip())
            if kind == "invoices":
                customer = (record["customer"] or "").strip()
                if not customer:
                    raise ValueError("customer is empty")
                aliases = tuple(
                    name.strip() for name in (record.get("aliases") or "").split("|") if name.strip()
                )
                rows.append(Invoice(record_id, customer, amount, transaction_date, aliases))
            else:
                reference = (record["reference"] or "").strip()
                if not reference:
                    raise ValueError("reference is empty")
                rows.append(Payment(record_id, transaction_date, amount, reference))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"Error on CSV line {line}: {exc}") from exc
    if not rows:
        raise ValueError(f"{kind.title()} CSV contains no data rows")
    return rows


def invoice_id_mentioned(reference: str, invoice_id: str) -> bool:
    # Boundaries avoid interpreting INV-1001 as a match for INV-10010.
    tokens = re.findall(r"[a-z0-9]+", invoice_id.lower())
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s\W]*".join(map(re.escape, tokens)) + r"(?![a-z0-9])"
    return re.search(pattern, reference.lower()) is not None


def lexical_similarity(a: str, b: str) -> float:
    a_tokens, b_tokens = set(a.split()), set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    ratio = SequenceMatcher(None, a, b).ratio()
    return max(overlap, ratio)


def amount_similarity(payment: Decimal, invoice: Decimal) -> float:
    difference = abs(payment - invoice)
    if difference == 0:
        return 1.0
    return max(0.0, 1.0 - float(difference / max(payment, invoice)) / 0.20)


def date_similarity(payment_date: date, invoice_date: date) -> float:
    delta = (payment_date - invoice_date).days
    if delta < -3:
        return 0.0
    if delta < 0:
        return 0.4
    return max(0.0, 1.0 - delta / 90.0)


def cosine_from_normalized(a: Sequence[float], b: Sequence[float]) -> float:
    return max(0.0, min(1.0, sum(float(x) * float(y) for x, y in zip(a, b))))


def reconcile(
    payments: Sequence[Payment],
    invoices: Sequence[Invoice],
    encoder: Encoder | None,
    *,
    use_embeddings: bool = True,
    top_k: int = 3,
) -> list[MatchResult]:
    """Rank candidates; never initiate transfers, write a ledger or approve matches.

    Setting use_embeddings=False provides an auditable rule-only baseline. It is
    intended for evaluation, not a claim that the AI model is unnecessary.
    """
    if not payments or not invoices:
        raise ValueError("Need at least one payment and invoice")
    if use_embeddings and encoder is None:
        raise ValueError("An open-weight encoder is required for AI matching")

    names = [tuple([i.customer, *i.aliases]) for i in invoices]
    # Include aliases: customers sometimes use an abbreviated trading name.
    text_inputs = [clean_reference(p.reference) for p in payments]
    invoice_inputs = [clean_name(n) for group in names for n in group]
    all_vecs = None
    if use_embeddings:
        all_vecs = encoder.encode(text_inputs + invoice_inputs, normalize_embeddings=True)
        if len(all_vecs) != len(text_inputs) + len(invoice_inputs):
            raise ValueError("Encoder returned an unexpected embedding count")

    offsets = []
    current = len(payments)
    for group in names:
        offsets.append(list(range(current, current + len(group))))
        current += len(group)

    results: list[MatchResult] = []
    fingerprints = Counter((p.date, p.amount, normalize(p.reference)) for p in payments)

    for p_idx, payment in enumerate(payments):
        candidates = []
        pay_text = text_inputs[p_idx]
        for i_idx, invoice in enumerate(invoices):
            textual_names = [clean_name(n) for n in names[i_idx]]
            lexical = max(lexical_similarity(pay_text, n) for n in textual_names)
            semantic = (
                max(cosine_from_normalized(all_vecs[p_idx], all_vecs[x]) for x in offsets[i_idx])
                if use_embeddings else 0.0
            )
            amount = amount_similarity(payment.amount, invoice.amount)
            exact = payment.amount == invoice.amount
            invoice_ref = invoice_id_mentioned(payment.reference, invoice.invoice_id)
            recency = date_similarity(payment.date, invoice.date)
            # Fixed, inspectable score. AI is the largest single feature.
            score = (
                0.38 * semantic + 0.22 * lexical + 0.23 * amount
                + 0.12 * float(invoice_ref) + 0.05 * recency
            )
            evidence = []
            if invoice_ref:
                evidence.append("invoice number appears in transfer reference")
            if exact:
                evidence.append("amount matches exactly")
            elif payment.amount != invoice.amount:
                evidence.append(f"amount differs by LKR {abs(payment.amount - invoice.amount):,.2f}")
            if use_embeddings:
                evidence.append(f"local AI name similarity {semantic:.0%}")
            if lexical > 0.6:
                evidence.append("business names look similar")
            candidates.append(Candidate(
                invoice_id=invoice.invoice_id,
                customer=invoice.customer,
                amount=invoice.amount,
                score=round(score, 4),
                semantic=round(semantic, 4),
                lexical=round(lexical, 4),
                exact_amount=exact,
                invoice_id_in_reference=invoice_ref,
                amount_difference=abs(payment.amount - invoice.amount),
                explanation="; ".join(evidence) or "weak evidence",
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        top = candidates[0]
        gap = top.score - candidates[1].score if len(candidates) > 1 else 1.0
        fingerprint = (payment.date, payment.amount, normalize(payment.reference))
        if fingerprints[fingerprint] > 1:
            status = "Review: repeated transfer"
            note = "More than one bank row has the same date, amount and reference. Verify against the bank statement."
        elif not top.exact_amount and top.score < 0.35:
            status = "No confident match"
            note = "No credible same-amount match. Investigate manually; split payments are not supported."
        elif not top.exact_amount:
            status = "Review: amount difference"
            note = "No exact-amount candidate is ranked first. Check split payments or fees manually."
        elif gap < 0.10 and not top.invoice_id_in_reference:
            status = "Review: ambiguous"
            note = "Two invoice candidates have similar scores. Confirm the customer manually."
        elif (top.invoice_id_in_reference and gap >= 0.10) or (
            top.score >= 0.72 and gap >= 0.10 and max(top.semantic, top.lexical) >= 0.65
        ):
            status = "Strong suggestion"
            note = "Suggestion only: explicitly approve before exporting."
        elif top.score >= 0.43:
            status = "Needs review"
            note = "Inspect the reference and candidate evidence before approving."
        else:
            status = "No confident match"
            note = "No convincing evidence. Leave unapproved or investigate outside the app."
        results.append(MatchResult(payment, tuple(candidates[:top_k]), status, note))

    # A likely double-paid invoice is never presented as a strong suggestion.
    winners = Counter(
        r.candidates[0].invoice_id for r in results
        if r.candidates and r.candidates[0].exact_amount and r.candidates[0].score >= 0.43
    )
    return [
        replace(r, status="Review: invoice collision",
                note="Several bank rows point to this invoice. Verify before assigning either payment.")
        if r.candidates and winners[r.candidates[0].invoice_id] > 1
        and r.status not in ("Review: repeated transfer",) else r
        for r in results
    ]


def spreadsheet_safe(value: str) -> str:
    """Prevent spreadsheet-formula injection in exported user-provided CSV text."""
    if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def export_approved(results: Sequence[MatchResult], approvals: dict[str, str]) -> str:
    """Export only explicitly approved 1:1 links; never auto-post to accounting."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["payment_id", "payment_date", "bank_reference", "payment_amount_lkr", "invoice_id", "customer", "invoice_amount_lkr", "decision", "ai_candidate_score"])
    seen_invoices = set()
    for result in results:
        invoice_id = approvals.get(result.payment.payment_id, "")
        if not invoice_id:
            continue
        candidate = next((c for c in result.candidates if c.invoice_id == invoice_id), None)
        if candidate is None:
            raise ValueError(f"Approved invoice {invoice_id} is not an offered candidate for {result.payment.payment_id}")
        if invoice_id in seen_invoices:
            raise ValueError(f"An invoice was approved twice: {invoice_id}")
        if not candidate.exact_amount:
            raise ValueError(f"Cannot export a different-amount link: {result.payment.payment_id} -> {invoice_id}")
        seen_invoices.add(invoice_id)
        writer.writerow([
            spreadsheet_safe(result.payment.payment_id), result.payment.date.isoformat(), spreadsheet_safe(result.payment.reference),
            f"{result.payment.amount:.2f}", spreadsheet_safe(invoice_id), spreadsheet_safe(candidate.customer),
            f"{candidate.amount:.2f}", "APPROVED_BY_REVIEWER", f"{candidate.score:.4f}",
        ])
    return out.getvalue()
