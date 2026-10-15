"""One-time download before a fully offline local AI session."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import MODEL_ID, load_encoder

if __name__ == "__main__":
    model = load_encoder()
    vectors = model.encode(["a customer bank payment"], normalize_embeddings=True)
    print(f"Downloaded/loaded {MODEL_ID}; embedding length: {len(vectors[0])}")
    print("Set REMITMATCH_OFFLINE=1 to disallow hub access during inference.")
