# 🧾 RemitMatch — Local AI for messy bank-transfer references

**Match the money that arrived to the invoice it belongs to — without sending private financial records to a cloud AI API.**

Built for **Hacktoberfest 2026 · Open-Source AI Challenge · Week 2: Side Hustle**.

> **Status:** working MVP with reviewed exports. Not financial advice, a payment processor, or a substitute for checking original bank records.

## The everyday problem

A bank statement says `NIMALI STORES ONLINE TRANSFER`, while the accounting system has `Nimali Grocery Stores` with invoice `INV-1002`. A business owner has to identify the right invoice and verify the money. Multiply that by dozens of transfers, abbreviated merchant names, duplicate deposits, ambiguous payers and incomplete references.

RemitMatch combines **open-weight sentence embeddings** with auditable accounting rules to make suggestions — not decisions. The reviewer explicitly approves each match and exports only reviewed links.

## Features

- 📑 Import **two CSV files** (bank deposits and open invoices) or run the fully synthetic demo.
- 🧠 Run **`sentence-transformers/all-MiniLM-L6-v2` locally** to compare customer and payment-reference meaning.
- 🔎 Use amounts, text similarity, explicit invoice numbers and time proximity to improve ranking.
- ⚠️ Flag ambiguous matches, inconsistent amounts, duplicated transfer descriptions and multiple payments pointing to one invoice.
- ✅ Require **human approval** before any match is exported; no bank or accounting writes.
- 🔐 Keep data local. The default server binds to **127.0.0.1**, and Streamlit usage reporting is disabled.
- 🧪 A rule-only ablation and tests help show what the embeddings add.

## Quickstart (Windows / PowerShell)

Requires **Python 3.10+** and enough RAM/storage for Python, PyTorch and a small embedding model.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m streamlit run app.py
```

If activation is restricted, run `.venv\Scripts\python.exe` instead of `python` in the commands.

### Quickstart (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m streamlit run app.py
```

Open `http://127.0.0.1:8501` in a browser. The app starts with sample data enabled. Click **Run local AI matching**. Inspect a result, choose a candidate, click **Approve match**, and download an approved-only CSV.

## Truly offline after one-time setup

The **first model download** needs internet. After that, you can turn off internet access and explicitly prohibit Hugging Face Hub fetches:

```powershell
# PowerShell, in the same terminal before launching Streamlit
$env:REMITMATCH_OFFLINE="1"
python -m streamlit run app.py
```

```bash
# macOS / Linux
export REMITMATCH_OFFLINE=1
python -m streamlit run app.py
```

The app's inference path calls only `SentenceTransformer(...).encode(...)` in your Python process. It does **not** call a hosted model API. Do not upload financial CSVs into a publicly hosted Streamlit deployment if you want the local-data privacy property. Other Python dependencies may perform their own update checks outside this inference path; audit and firewall the environment for highly sensitive work.

## Input data format

**`invoices.csv`** — `aliases` is optional, use `|` to separate multiple alternative names:

```csv
invoice_id,customer,amount,date,aliases
INV-1001,Sunrise Bakers,18500.00,2026-10-01,Sunrise Bakery|Sunrise Bakes
INV-1002,Nimali Grocery Stores,42750.00,2026-10-02,Nimali Stores
```

**`bank_payments.csv`**:

```csv
payment_id,date,amount,reference
BNK-001,2026-10-03,18500.00,CEFT SUNRISE BAKERY PAYMENT
BNK-002,2026-10-04,42750.00,NIMALI STORES ONLINE TRANSFER
```

- Dates must be **`YYYY-MM-DD`**, and all amounts are interpreted as **LKR**.
- Amounts must be positive and nonzero; IDs must be unique in their CSV.
- Only positive deposits and one-payment-to-one-invoice **exact amount** approval are supported in the MVP.
- Keep CSV field values containing commas in double quotes, as with ordinary CSV files.
- The included dataset is **synthetic**; it includes an intentionally duplicated payment and ambiguous references.

## How the AI helps

`all-MiniLM-L6-v2` creates a **384-dimensional vector** from each payment reference and from each invoiced customer name or alias. For each candidate invoice, the app calculates:

```text
ranking = 0.38 × semantic_similarity  (open-weight AI)
        + 0.22 × lexical_similarity   (name tokens and fuzzy text)
        + 0.23 × amount_similarity    (exact amount favored)
        + 0.12 × invoice_id_present  (explicit bank reference)
        + 0.05 × date_proximity
```

Candidates are sorted by this score. The values are **heuristics, not calibrated probabilities**. Rules separately flag duplicates, ambiguous top candidates and amount mismatches. Human review, a one-to-one constraint and an exact-amount gate prevent unreviewed or invalid links from appearing in the export.

This is not an LLM pretending to be an accountant. **The AI ranks ambiguous names; deterministic code checks financial constraints.** The model is essential to the semantic-matching approach, and an ablation lets us compare it to a no-AI baseline.

## Reproduce the synthetic comparison

```bash
python scripts/evaluate.py
```

The script compares **AI + rules** against **rules without embeddings**, reporting top-1 candidate retrieval on rows where a labeled invoice is available. This is not a performance guarantee or a production benchmark: the sample has only 11 invented deposits and no actual customer data.

## Tests

```bash
python -m pip install pytest
python -m pytest -q
```

The core tests use a fake deterministic encoder so the test suite needs **no model download or internet**. The actual Streamlit inference path requires the real open-weight model. The tests cover bad CSVs, integer-like invoice number boundaries, positive Decimal amounts, duplicate transfers, invoice collisions, candidate rankings, and guarded exports.

## Architecture

```text
CSV bank payments ──┐
                    ├── Validate input ──┬── Local MiniLM embeddings ─┐
CSV open invoices ──┘                    └── Explicit finance rules ──┤
                                                                   ▼
                                                            Ranked candidates
                                                                   ▼
                                                         Human review & approval
                                                                   ▼
                                                          Approved-only CSV
```

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, in-memory workflow, reviewer approvals |
| `matcher.py` | Pure-Python scoring, safety checks and export |
| `model.py` | Local model loading and offline switch |
| `scripts/download_model.py` | Fetch model once |
| `scripts/evaluate.py` | Synthetic data ablation |
| `sample_data/` | Fake invoices, payments and expected candidate links |
| `tests/` | Core logic verification |

## Why open innovation matters to this business

A shop owner cannot casually upload identifiable bank entries and client names to just any service. Open weights make it possible to keep inference local, even after disconnecting from the internet. The model is openly inspectable, deployable without per-token fees, and replaceable for a niche model trained on local transfer vocabulary. This is useful for small fixed-price installs and for businesses that prefer to own their data.

Could a hosted, closed AI API make candidate matches? Yes. But the local approach changes the **privacy boundary**, **ongoing marginal inference cost** and **ability to customize**. For this prototype, those advantages matter more than producing free-form generated text. The embedding model is Apache-2.0 licensed; this repository's app code is MIT licensed.

**Model attribution:** [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (Apache License 2.0).

## Who might pay? (hypothesis; not a validated sale)

Small retail shops, local service businesses, accountants handling multiple clients, and businesses that reconcile manual bank transfers. A potential side-hustle offer is a **one-time installation/setup service with optional support**, or an affordable monthly support plan, rather than charging per AI request. Price and demand need to be tested with real users.

## Important limitations

- **Do not automatically settle a real invoice** from a semantic match alone; verify at the bank and in the accounting system.
- No split payments, multiple invoices per deposit, currencies other than LKR, refunds or credit notes.
- English-script transfer references only; the base model is not verified for Sinhala or Tamil references.
- Similar customer names, identical amounts, OCR mistakes and copied bank references still need human review.
- No persisted database; approvals live in the current browser session until exported. Back up exported CSVs as appropriate.
- The repository contains no real banking data; please do not commit yours.

## Hacktoberfest submission

See [`SUBMISSION.md`](SUBMISSION.md) for the draft. Replace the GitHub and demo placeholders once you publish the repository and record a real walkthrough. Do not claim a customer trial or model evaluation you have not performed.

## License

MIT for this app; [Apache-2.0 for the embedding model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
