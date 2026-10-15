---
title: 'RemitMatch: The AI Bookkeeper That Never Sees Your Cloud'
published: false
description: 'I built a local-first side hustle for small businesses that reconciles messy bank transfers with open-weight AI — without uploading a bank statement to an AI service.'
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12).* 

## What I Built

**A bank statement tells you that money arrived. It doesn't always tell you which invoice was paid.**

Imagine you run a small bakery-supply business. Your accounting software has an unpaid invoice for **Nimali Grocery Stores**. Your bank CSV says:

```text
BNK-002 | 2026-10-04 | LKR 42,750 | NIMALI STORES ONLINE TRANSFER
```

Another payment says `CEFT SUNRISE BAKERY PAYMENT`. Another includes an invoice number, but not the customer's full name. Two rows appear to be the **same payment**. One payment could belong to either of two hardware stores charging the same amount.

Each of these is simple for a human to check individually. Together they make reconciliation an irritating, repetitive job. And when the business is small, the person doing it is often the same person trying to sell, deliver and support the product.

So I built **RemitMatch**: a local-first AI reconciliation desk for freelancers, small businesses and bookkeepers.

You upload an open-invoice CSV and a bank-payment CSV. An open-weight model compares the *meaning* of payer references with business names, even when the strings are not identical. Deterministic rules verify amounts, invoice IDs and dates. The interface ranks potential matches, explains why they were suggested, and flags duplicates or conflicts.

**Importantly, the software never decides that money has paid an invoice on its own.** The human must approve each candidate. Only explicitly approved, exact-amount, one-to-one matches appear in the export.

### Who would pay?

My initial target customer is a small shop or accountant processing many direct bank transfers but not using an expensive enterprise reconciliation tool. The potential product is not “AI accounting.” It is a narrowly scoped time-saver that can be installed on the customer's own laptop, with revenue from setup, configuration and support. **This is a business hypothesis, not a claim that someone has paid me.**

## Demo

**Local demo:** [ADD YOUR ACTUAL SCREEN RECORDING OR DEMO LINK BEFORE PUBLISHING]

You can also reproduce the flow yourself using the synthetic files in the repository:

```bash
python -m pip install -r requirements.txt
python scripts/download_model.py     # only needed once
python -m streamlit run app.py
```

Open `http://127.0.0.1:8501` and select **Run local AI matching**. Examine the suggestions for `BNK-002`, the intentionally repeated `BNK-008` and `BNK-011`, and the deliberately ambiguous hardware transfer `BNK-009`. Approve a valid exact-amount candidate, then export the reviewed CSV.

The demo data is fictional. The app doesn't send it to a hosted AI inference API.

## Code

**GitHub:** [REPLACE WITH THE ACTUAL PUBLIC REMITMATCH REPOSITORY URL]

The project includes a Streamlit interface, auditable reconciliation code, one-time local model setup, synthetic sample CSVs, a baseline-evaluation script and a core unit-test suite. The code is MIT licensed; the embedding model is Apache-2.0 licensed.

For reviewers who want to see where the AI matters, start with `matcher.py` in the repository: its `reconcile()` function calls the embedding encoder, combines meaning-aware name similarity with finance-specific rules, and returns inspectable candidate evidence.

## How I Built It

I intentionally didn't ask a language model to “act as an accountant.” In a money-related workflow, fluent language is not the same thing as a valid payment match.

Instead, RemitMatch has **two distinct responsibilities**:

**1. Open-weight AI does the messy-text work.**

I use [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), an Apache-2.0-licensed embedding model, through the open-source Sentence Transformers library. It runs in the Python process on the user's machine. Payment references and customer names are turned into local sentence vectors, allowing semantic similarity to contribute to the candidate ranking.

**2. Explicit code handles financial constraints.**

Each candidate has an inspectable ranking formula:

```text
38%  Local AI name similarity
22%  Lexical business-name similarity
23%  Amount similarity
12%  Exact invoice ID present in bank reference
 5%  Payment/invoice date proximity
```

Those weights are **engineering heuristics, not statistical confidence percentages**. Additional rules detect repeated bank rows, multiple deposits targeting one invoice, ambiguous candidates and amount differences. Amounts use Python `Decimal`, not floating-point arithmetic. The user must manually approve; the export enforces an exact-amount, one-to-one link and is not connected to a live bank or ERP.

The included tests use an injectable deterministic test encoder so they can run without downloading model weights. A separate `scripts/evaluate.py` lets anyone compare **real-model + rules** with **rules only** on a small labeled *synthetic* dataset. I am deliberately not claiming real-world accuracy from a handful of invented rows.

### The hardest design choice

It wasn't choosing the model. It was deciding **what not to automate**.

A semantic model can confidently associate a transfer with the wrong customer if two firms have similar names. A matching amount can also be a coincidence. So I chose a reviewer-first interface instead of automatically changing invoice states. The best side-hustle software isn't necessarily software that does everything. Sometimes the sellable feature is turning ten minutes of detective work into a short, inspectable checklist.

## Why Does Open Innovation Matter?

For this product, **local execution is the feature, not an implementation detail**.

Consider the alternatives. A hosted AI service could absolutely help interpret the names — and might perform better on some difficult references. But using it may mean transmitting bank references and customer details to an external processor, budgeting for usage-based pricing, and accepting whatever model behavior and terms that provider chooses.

An open-weight embedding model changes the economics and the privacy boundary:

- **Private by design:** after a one-time model download, inference can run with internet disconnected. Sensitive CSV content stays within the user's local application rather than being submitted to a hosted AI model API.
- **Low marginal inference cost:** there is no per-request model API charge; customers still pay for their computer, setup and maintenance.
- **A modifiable system:** the model can be exchanged for a domain-adapted alternative and the scoring rules can be tuned for local bank-transfer vocabulary.
- **A stronger trust story:** technical users can inspect the code, run the ablation, and see where both the model and accounting rules contributed. They can change or remove the system without depending on an external AI provider's pricing.

This is where open innovation worked better **for the specific business constraints**: not necessarily higher model accuracy, but local control over data and predictable infrastructure costs. I wouldn't promise that any open model always beats a closed one. I would promise that the user gets to decide where their sensitive data goes.

## What I'd Validate Next

The prototype handles one-to-one, exact-amount deposits in LKR. It does not yet resolve partial payments, multiple-invoice transfers, refunds or native Sinhala/Tamil bank references. Those are important limitations, not features to hide.

Next, I'd sit with a real business owner, use a consented or anonymized sample of their transfer descriptions, and measure three things: minutes spent matching deposits, how often the correct invoice appears among the top three candidates, and whether their preference for private local software is strong enough to justify a setup or support fee.

**That would turn a hackathon prototype into a side hustle.**

---

*Built for Hacktoberfest 2026. The story here is a working MVP and a commercial hypothesis — not a fabricated customer testimonial or a claimed production deployment.*
