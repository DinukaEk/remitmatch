# Final submission checklist + demo shot list

## Start the app (Windows PowerShell)

From this project folder:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_model.py
python -m streamlit run app.py
```

Keep the sample dataset switch **on**. The first download needs internet. `python scripts/evaluate.py` runs the *real* embedding model and reports a synthetic rule-only comparison; note the actual numbers after you run it. Run `python -m pytest -q` and record the results.

## A 60–90 second screen-recording plan

1. **0–10s:** Show the local URL `127.0.0.1:8501` and explain the privacy goal: no bank CSV goes to a cloud AI API.
2. **10–20s:** Show the bank CSV's `NIMALI STORES ONLINE TRANSFER` beside the invoice's full customer name.
3. **20–35s:** Click **Run local AI matching**; show ranked candidates and the local AI name similarity evidence.
4. **35–50s:** Open `BNK-008` / `BNK-011` to show the repeated bank reference and `BNK-009` to show ambiguity.
5. **50–65s:** Approve an exact-amount match, download the approved CSV and open the file.
6. **65–80s:** In your terminal, set `REMITMATCH_OFFLINE=1`, disconnect internet if possible, reopen the app and show that inference still works after the one-time model download.
7. **80–90s:** Say who might pay for this and why: local shopkeepers and accountants who want reliable, private, low-cost reconciliation assistance.

Record only synthetic data. A basic Windows screen recorder (Snipping Tool recording or OBS) is fine. Do not fabricate app output or claim an offline test you have not run.

## Publish steps

- [ ] Create a **public GitHub repo named `remitmatch`** and push these source files (do not commit `.venv/`, real bank data, or model weights).
- [ ] Install dependencies on a computer with internet access and perform one real-model inference in the UI.
- [ ] Run `python scripts/evaluate.py`; if sharing accuracy figures, say they are from **synthetic** data.
- [ ] Record and upload your actual walkthrough to YouTube (unlisted works) or another accessible host.
- [ ] In `SUBMISSION.md`, replace both bracketed placeholders for the repository and video links.
- [ ] If you meet a real user, append a **truthful** "My First User" section with what happened; otherwise do not add that section.
- [ ] Paste `SUBMISSION.md` into a new DEV article and remove the `published: false` frontmatter if DEV's editor asks you to (check the preview).
- [ ] Confirm the required **`devchallenge`** and **`hf26challenge`** tags are present.
- [ ] Publish via DEV **on or before October 18, 2026**. The challenge deadline is stated as October 18; verify the exact cutoff time on the live challenge page.

**Challenge URL:** https://dev.to/challenges/hacktoberfest-week2-2026-10-12

**Important:** A ZIP or local prototype by itself is **not** a submitted entry. Publication on DEV with your own actual repository and demo links is still needed.
