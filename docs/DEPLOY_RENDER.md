# Deploying on Render (512MB free tier)

## What went wrong

### Out of memory

Render free web services have **512MB RAM total** (app + OS + Python). The original stack exceeded this because:

| Component | Approx. RAM |
|-----------|-------------|
| PyTorch (via `sentence-transformers`) | ~350–450MB |
| BGE-small weights in memory | ~130MB |
| faster-whisper (if imported) | ~150MB+ |
| FastAPI + LangChain + LangGraph | ~80–120MB |

**Total often > 700MB** — process killed before Uvicorn could bind a port.

**Fix applied:** Replaced `sentence-transformers` with [FastEmbed](https://github.com/qdrant/fastembed) (ONNX, ~67MB for BGE-small). Removed `faster-whisper` from production requirements; use **Apify** for Instagram on cloud.

### No open ports detected

Render injects a dynamic **`PORT`** (e.g. `10000`). Hardcoding `--port 8000` means Uvicorn listens on the wrong port; Render’s proxy finds nothing and reports “No open ports detected.”

**Fix applied:** `CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"`

## Environment variables (Render dashboard)

| Variable | Example |
|----------|---------|
| `GEMINI_API_KEY` | your key |
| `APIFY_TOKEN` | **Required** — copy from [Apify Integrations](https://console.apify.com/account/integrations). Needed for YouTube on Render (cloud IPs are blocked by YouTube) and Instagram Reels. |
| `CORS_ORIGINS` | `https://hashverse-two.vercel.app` |
| `LLM_PROVIDER` | `gemini` |
| `QDRANT_URL` | `https://<cluster>.aws.cloud.qdrant.io` |
| `QDRANT_API_KEY` | your Qdrant Cloud API key |

## Vercel frontend

Set in Vercel → Project → Environment Variables:

```
NEXT_PUBLIC_BACKEND_URL=https://hashverse-api.onrender.com
```

(Use your actual Render service URL.)

## If OOM persists

Set on Render:

```
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Smaller ONNX model (~90MB), slightly lower MTEB retrieval scores — fine for demo.

## Local Whisper (optional)

```bash
pip install faster-whisper
```
