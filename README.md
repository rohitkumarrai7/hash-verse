# CreatorJoy RAG Analyst

A full-stack RAG chatbot for comparing YouTube videos and Instagram Reels. Paste two URLs, ingest transcripts + metadata, then ask comparative questions with **streaming SSE responses**, **timestamp-aware citations**, and **multi-turn memory**.

Built for the [CreatorJoy Technical Round Challenge](https://cliff-fountain-f34.notion.site/Technical-Round-Challenge-Engineers-3565786a2e8c81cb9518fb577683475d).

**Live demo:** Deploy frontend to Vercel + backend to Render (see [Deploy](#deploy)). Set `NEXT_PUBLIC_BACKEND_URL` to your Render API URL.

> **Screenshot:** Capture your dashboard during the Loom demo and save it as `docs/demo-screenshot.png`.

## What it does

1. Ingests **Video A (YouTube)** and **Video B (Instagram Reel)**
2. Extracts transcripts with timestamps, metadata (views, likes, comments, creator, followers, hashtags, upload date, duration)
3. Computes **engagement rate** dynamically: `((likes + comments) / views) × 100` (tooltip explains when metrics are partial)
4. Chunks transcripts (**512 tokens, 128 overlap**, sentence-aware splits), embeds with **BGE-small-en-v1.5**, stores in **Qdrant**
5. Answers creator questions via **LangGraph** with intent routing and hook-only retrieval for first-5s questions
6. Streams answers over **SSE** with citations like `[Video A · Chunk 4 · 00:00-00:15]` plus fallback badges from retrieved chunks

## Architecture

```
┌─────────────┐     POST /ingest      ┌──────────────────────────────────────┐
│  Next.js    │ ───────────────────►  │ FastAPI                               │
│  Frontend   │     POST /chat (SSE)  │  ├─ YouTube: youtube-transcript-api   │
└─────────────┘ ◄───────────────────  │  ├─ Instagram: Apify → yt-dlp+Whisper│
                                      │  ├─ Chunk + BGE embed                  │
                                      │  ├─ Qdrant (vectors + metadata)        │
                                      │  └─ LangGraph (retrieve → LLM stream)  │
                                      └──────────┬───────────────┬─────────────┘
                                                 │               │
                                            ┌────▼────┐    ┌─────▼─────┐
                                            │ Qdrant  │    │ Redis     │
                                            │ vectors │    │ cache +   │
                                            └─────────┘    │ checkpoints│
                                                           └───────────┘
```

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Next.js + Tailwind | Side-by-side embedded video cards + SSE chat |
| Backend | FastAPI | Native async + SSE streaming |
| Orchestration | **LangGraph** | Intent routing, hook filter, Redis-backed memory |
| Embeddings | BGE-small-en-v1.5 via FastEmbed (ONNX) | ~67MB model RAM; fits Render 512MB tier |
| Vector DB | **Qdrant** | Payload filters (`video_id`, `is_hook`); hybrid BM25 ready at scale |
| LLM | **Gemini 2.0 Flash** (default) | Direct API = lowest latency/cost; OpenRouter/OpenAI optional fallbacks |
| YouTube | youtube-transcript-api + yt-dlp | Free transcripts + multi-language fallback |
| Instagram | Apify + yt-dlp/faster-whisper | Triple fallback when scraping fails |
| Memory | Redis LangGraph checkpointer | Survives backend restarts when Redis is available |

### Why 512 tokens with 128 overlap?

BGE-small-en-v1.5 uses a 512-token context window. **512 tokens** ≈ 30–45 seconds of spoken content — enough for a hook or narrative beat. **128-token overlap** (~25%) keeps sentence boundaries intact so hooks aren't split across chunks. Chunking also prefers **sentence boundaries** when near the token limit.

### Why LLM streaming lives outside LangGraph (for now)

LangGraph handles retrieval + memory; the router streams tokens via Gemini's async API to avoid LangGraph's sync-first streaming constraints in the MVP. In production I'd add a dedicated streaming node inside the graph.

## Setup

### Prerequisites

- Docker + Docker Compose (recommended)
- API keys: `GEMINI_API_KEY`, `APIFY_TOKEN` (Instagram)

### Quick start

```bash
git clone https://github.com/rohitkumarrai7/hash-verse.git
cd hash-verse
cp .env.example .env
cp backend/.env.example backend/.env
# Edit both .env files with your keys

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Windows one-command backend

```powershell
cd backend
.\run.bat
```

### Local dev

```bash
docker compose up qdrant redis
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm run dev
```

## Deploy

### Frontend (Vercel)

1. Import repo, set root directory to `frontend`
2. Env: `NEXT_PUBLIC_BACKEND_URL=https://your-backend.onrender.com`

### Backend (Render)

1. Docker deploy from `backend/Dockerfile` (uses `$PORT`, no PyTorch — see [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md))
2. Set `GEMINI_API_KEY`, `APIFY_TOKEN`, `CORS_ORIGINS=https://hashverse-two.vercel.app`
3. Vercel: `NEXT_PUBLIC_BACKEND_URL=https://<your-service>.onrender.com`

## Demo flow (Loom script)

1. Paste YouTube + Instagram URLs → **Ingest & Analyze** (watch progress bar)
2. Show embedded players + engagement badges
3. Ask all 5 assignment questions + one follow-up for memory
4. Click a citation badge to highlight the source chunk
5. Explain cost math: BGE=$0, Gemini ~$1/day at 1K creators

### Tested URL pairs

| YouTube (A) | Instagram Reel (B) |
|-------------|-------------------|
| `https://www.youtube.com/watch?v=jNQXAC9IVRw` | `https://www.instagram.com/reel/DCqVQ8oxSKj/` |
| Any public captioned video | Any public creator Reel |

## Cost & scalability

| Line item @ 1K creators/day | Cost/day |
|-----------------------------|----------|
| BGE embeddings | $0 |
| Gemini Flash LLM | ~$1 |
| Apify scraping | ~$10 |
| **Total** | **~$11/day** |

At 10K creators: GPU embeddings, Qdrant cluster, Celery ingestion queue, semantic LLM cache, **Qdrant hybrid dense+BM25** for exact hook keywords.

## What I'd improve next

1. Celery workers for Whisper-heavy Instagram fallback
2. Qdrant hybrid search (dense + sparse BM25) for exact keyword matches
3. Move LLM streaming into a LangGraph streaming node
4. Semantic query cache for repeated creator questions

## Project structure

```
backend/          FastAPI + LangGraph + ingestion
frontend/         Next.js dashboard + SSE chat
docker-compose.yml
render.yaml       Render backend deploy template
```

## License

MIT — technical screening submission.
