"""Explicit local model boundary; no remote inference API."""
import os

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def load_encoder():
    # After one-time download, REMITMATCH_OFFLINE=1 disallows hub traffic.
    if os.environ.get("REMITMATCH_OFFLINE") == "1":
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_ID, local_files_only=os.environ.get("REMITMATCH_OFFLINE") == "1")
