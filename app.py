"""RemitMatch — local AI bank transfer reconciliation prototype.
Run: streamlit run app.py --server.address 127.0.0.1
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from decimal import Decimal

import streamlit as st

from matcher import export_approved, load_csv, reconcile
from model import MODEL_ID, load_encoder

HERE = Path(__file__).resolve().parent
st.set_page_config(page_title="RemitMatch · Local AI", page_icon="🧾", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    h1, h2, h3 {letter-spacing: -.035em;}
    .hero {border: 1px solid rgba(125,155,183,.19); border-radius: 20px;
      padding: 24px 28px; background: linear-gradient(112deg,#0b2030,#103d41); margin-bottom: 22px;}
    .eyebrow {font-size: .78rem; font-weight: 700; letter-spacing: .13em; color: #71e4cc;}
    .hero h1 {color: #f2fbff; font-size: 2.8rem; margin: 8px 0;}
    .hero p {color: #cee0e7; font-size: 1.05rem; margin: 0; max-width: 760px;}
    .pill {display:inline-block; border: 1px solid #4a9388; color: #aaf2df;
      border-radius:100px; padding: 5px 12px; margin: 16px 8px 0 0; font-size:.8rem;}
    [data-testid="stMetricValue"] {font-size: 1.7rem;}
    [data-testid="stExpander"] {border-radius: 14px;}
    .minor {color:#91a5b6; font-size: .84rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def encoder():
    return load_encoder()


def get_bytes() -> tuple[bytes | None, bytes | None]:
    use_samples = st.session_state.get("use_samples", True)
    if use_samples:
        return (
            (HERE / "sample_data" / "invoices.csv").read_bytes(),
            (HERE / "sample_data" / "bank_payments.csv").read_bytes(),
        )
    inv = st.session_state.get("inv_file")
    pay = st.session_state.get("pay_file")
    return (inv.getvalue() if inv else None, pay.getvalue() if pay else None)


with st.sidebar:
    st.markdown("## ◉ RemitMatch")
    st.caption("A private AI assistant for a painfully ordinary accounting job.")
    st.divider()
    st.toggle("Use synthetic sample data", value=True, key="use_samples")
    if st.session_state.use_samples:
        st.success("Synthetic invoices + bank payments loaded")
        st.caption("11 bank entries · 10 outstanding invoices · intentional duplicates and ambiguity")
    else:
        st.file_uploader("Invoices CSV", type=["csv"], key="inv_file", help="Columns: invoice_id,customer,amount,date,aliases (optional)")
        st.file_uploader("Bank deposits CSV", type=["csv"], key="pay_file", help="Columns: payment_id,date,amount,reference")
    st.divider()
    st.markdown("**How it works**")
    st.caption("1. Read two local CSVs")
    st.caption("2. Compare references with an open-weight embedding model")
    st.caption("3. Check amount, invoice ID, date and ambiguity")
    st.caption("4. Review and explicitly approve")
    st.caption("5. Export confirmed matches only")
    st.divider()
    st.caption(f"Model: `{MODEL_ID}`")
    st.caption("Inference runs on your computer. Bank data is not sent to an AI API.")
    st.caption("Prototype — validate results before importing into an ERP.")

st.markdown("""
<div class="hero">
  <div class="eyebrow">LOCAL-FIRST FINANCE WORKFLOW</div>
  <h1>Make sense of the money that arrived.</h1>
  <p>Bank statements rarely say which invoice a payment belongs to. RemitMatch reads messy
  transfer descriptions, proposes invoice matches with open-weight AI, and keeps a human in control.</p>
  <span class="pill">🔒 No cloud AI API</span>
  <span class="pill">🧠 Open-weight embeddings</span>
  <span class="pill">✓ Human-approved export</span>
</div>
""", unsafe_allow_html=True)

inv_data, bank_data = get_bytes()
if not inv_data or not bank_data:
    st.info("Provide both CSV files in the sidebar, or turn on sample data to explore the demo.")
    st.stop()

fingerprint = hashlib.sha256(inv_data + b"\0" + bank_data).hexdigest()
if st.session_state.get("fingerprint") != fingerprint:
    st.session_state.fingerprint = fingerprint
    st.session_state.results = None
    st.session_state.approvals = {}

try:
    invoices = load_csv(inv_data, "invoices")
    payments = load_csv(bank_data, "payments")
except ValueError as error:
    st.error(f"Please fix your CSV: {error}")
    st.stop()

col_a, col_b, col_c = st.columns([1,1,2])
col_a.metric("Outstanding invoices", len(invoices))
col_b.metric("Bank deposits", len(payments))
col_c.metric("Total deposits shown (LKR)", f"{sum((p.amount for p in payments), start=Decimal(0)):,.2f}")

st.caption("Expected columns: invoices → invoice_id, customer, amount, date, optional aliases (separate with |); payments → payment_id, date, amount, reference. Dates YYYY-MM-DD. Amounts LKR.")
left, _right = st.columns([1, 1])
with left:
    run = st.button("✨ Run local AI matching", type="primary", use_container_width=True)

if run:
    with st.spinner("Loading the local model and comparing payment references… (first run requires model download)"):
        try:
            local_model = encoder()
            st.session_state.results = reconcile(payments, invoices, local_model, top_k=3)
            st.session_state.approvals = {}
        except Exception as error:
            st.error(f"Local model could not run: {error}")
            st.info("Install requirements and download model once with `python scripts/download_model.py`. See README.md for offline instructions.")
            st.stop()

results = st.session_state.get("results")
if results is None:
    st.markdown("#### Ready for a safe, explainable demo")
    st.write("Try the synthetic dataset first. The samples include small-business trading-name variations, a duplicated transfer, an ambiguous payer and an unmatched amount.")
    with st.expander("Preview the input data"):
        st.write("**Bank payment references**")
        st.dataframe([{
            "Payment": p.payment_id, "Date": p.date.isoformat(),
            "Amount (LKR)": f"{p.amount:,.2f}", "Bank reference": p.reference
        } for p in payments], use_container_width=True, hide_index=True)
    st.stop()

statuses = Counter(result.status for result in results)
strong = statuses.get("Strong suggestion", 0)
review = sum(n for k, n in statuses.items() if "Review" in k or k == "Needs review")
matched = len(st.session_state.approvals)
summary_cols = st.columns(4)
summary_cols[0].metric("Strong suggestions", strong)
summary_cols[1].metric("Review required", review)
summary_cols[2].metric("Explicitly approved", matched)
summary_cols[3].metric("No confident match", statuses.get("No confident match", 0))
st.divider()
st.subheader("Reconciliation desk")
st.caption("Scores are ranking signals, **not calibrated probabilities**. No suggestion is posted to accounting or exported without your approval.")

for result in results:
    payment = result.payment
    best = result.candidates[0] if result.candidates else None
    linked = st.session_state.approvals.get(payment.payment_id)
    short_desc = (payment.reference[:64] + "…") if len(payment.reference) > 64 else payment.reference
    label = f"{payment.payment_id}  ·  LKR {payment.amount:,.2f}  ·  {short_desc}"
    with st.expander(label, expanded=result.status != "Strong suggestion"):
        status_col, detail_col = st.columns([1, 2])
        with status_col:
            st.markdown(f"**{('✅ Approved' if linked else result.status)}**")
            st.caption(result.note)
            if best:
                st.markdown(f"Top candidate: **{best.invoice_id}**")
                st.caption(f"{best.customer} · LKR {best.amount:,.2f}")
        with detail_col:
            st.dataframe([{
                "Invoice": c.invoice_id,
                "Customer": c.customer,
                "Amount (LKR)": f"{c.amount:,.2f}",
                "Score*": f"{c.score:.0%}",
                "AI name similarity": f"{c.semantic:.0%}",
                "Exact amount": "Yes" if c.exact_amount else "No",
                "Reference ID": "Yes" if c.invoice_id_in_reference else "No",
            } for c in result.candidates], use_container_width=True, hide_index=True)
        if best:
            st.caption("Evidence for top candidate: " + best.explanation)
        valid_candidates = [c for c in result.candidates if c.exact_amount]
        if valid_candidates:
            names = {c.invoice_id: f"{c.invoice_id} — {c.customer} (LKR {c.amount:,.2f})" for c in valid_candidates}
            selected = st.selectbox(
                "Reviewer decision (only exact-amount matches can be approved)",
                options=[""] + list(names),
                index=([""] + list(names)).index(linked) if linked in names else 0,
                format_func=lambda key, names=names: names.get(key, "Choose invoice to approve…"),
                key=f"choice_{payment.payment_id}",
            )
            act_col, undo_col, _ = st.columns([1, 1, 2])
            with act_col:
                if st.button("Approve match", key=f"approve_{payment.payment_id}", type="primary"):
                    if not selected:
                        st.warning("Choose an invoice first.")
                    elif selected in st.session_state.approvals.values() and st.session_state.approvals.get(payment.payment_id) != selected:
                        st.error("That invoice is already approved for another deposit. One-to-one matching is enforced.")
                    else:
                        st.session_state.approvals[payment.payment_id] = selected
                        st.rerun()
            with undo_col:
                if linked and st.button("Remove approval", key=f"undo_{payment.payment_id}"):
                    st.session_state.approvals.pop(payment.payment_id, None)
                    st.rerun()
        else:
            st.info("No candidate has the exact amount. Investigate outside the app; split/partial payments are not supported in this MVP.")

st.divider()
st.subheader("Export your decisions")
if st.session_state.approvals:
    try:
        content = export_approved(results, st.session_state.approvals)
        st.download_button(
            "⬇ Download approved matches CSV",
            data=content.encode("utf-8"),
            file_name="remitmatch_approved.csv",
            mime="text/csv",
            type="primary",
        )
        st.success(f"Ready to export {len(st.session_state.approvals)} reviewer-approved match(es).")
    except ValueError as error:
        st.error(f"Cannot export: {error}")
else:
    st.info("Approve at least one exact-amount match to enable a safe CSV export.")
st.caption("* Scores are heuristic rankings composed of embedding similarity, text similarity, amount checks, invoice number and date. Never treat them as payment proof.")
