import os

# Optional: enable mirror if needed.
# os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from huggingface_hub import snapshot_download

print("Starting Whisper model download (resume supported)...")

snapshot_download(
    repo_id="mlx-community/whisper-large-v3-mlx",
    local_dir="./local_whisper_model"
)

print("Done. Model saved in local_whisper_model/")