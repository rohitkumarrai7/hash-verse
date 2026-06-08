"""Production smoke test — run against any backend base URL."""
from __future__ import annotations

import json
import sys
import time
import uuid

import httpx

DEFAULT_URLS = {
    "youtube": "https://www.youtube.com/shorts/khYDC9qhOLo",
    "instagram": "https://www.instagram.com/reel/DTQr-bdjd8q/",
}

FE_ORIGIN = "https://hash-verse.vercel.app"


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    raise SystemExit(1)


def test_health(client: httpx.Client, base: str) -> None:
    r = client.get(f"{base}/health", timeout=90.0)
    if r.status_code != 200:
        fail(f"GET /health -> {r.status_code} {r.text[:200]}")
    data = r.json()
    if data.get("status") != "ok":
        fail(f"/health body: {data}")
    ok(f"GET /health -> qdrant={data.get('qdrant')}")


def test_cors(client: httpx.Client, base: str) -> None:
    r = client.options(
        f"{base}/api/v1/ingest",
        headers={
            "Origin": FE_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30.0,
    )
    allow = r.headers.get("access-control-allow-origin", "")
    if r.status_code not in (200, 204) or not allow:
        fail(f"CORS preflight -> {r.status_code} allow-origin={allow!r}")
    ok(f"CORS preflight -> Access-Control-Allow-Origin={allow}")


def test_ingest_and_chat(client: httpx.Client, base: str) -> str:
    sid = str(uuid.uuid4())
    body = {
        "session_id": sid,
        "youtube_url": DEFAULT_URLS["youtube"],
        "instagram_url": DEFAULT_URLS["instagram"],
    }
    r = client.post(f"{base}/api/v1/ingest", json=body, timeout=60.0)
    if r.status_code != 200:
        fail(f"POST /ingest -> {r.status_code} {r.text[:300]}")
    ok("POST /api/v1/ingest started")

    for i in range(72):
        time.sleep(5)
        st = client.get(f"{base}/api/v1/ingest/{sid}", timeout=60.0).json()
        status = st.get("status")
        print(f"        poll[{i}] {status}: {(st.get('message') or '')[:80]}")
        if status == "completed":
            ok(f"Ingest completed (video_a={bool(st.get('video_a'))}, video_b={bool(st.get('video_b'))})")
            break
        if status == "failed":
            fail(f"Ingest failed: {st.get('message')}")
    else:
        fail("Ingest timed out after 6 minutes")

    chat_body = {"session_id": sid, "message": "Which video has higher engagement rate? Reply in one sentence."}
    tokens: list[str] = []
    with client.stream(
        "POST",
        f"{base}/api/v1/chat",
        json=chat_body,
        timeout=120.0,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        if resp.status_code != 200:
            fail(f"POST /chat -> {resp.status_code} {resp.read().decode()[:300]}")
        buf = ""
        for chunk in resp.iter_text():
            buf += chunk
            if "event: message" in buf or '"type":"error"' in buf:
                parts = buf.replace("\r\n", "\n").split("\n\n")
                for part in parts[:-1]:
                    for line in part.split("\n"):
                        if line.startswith("data:"):
                            payload = json.loads(line[5:].strip())
                            if payload.get("type") == "token":
                                tokens.append(payload.get("content", ""))
                            elif payload.get("type") == "error":
                                fail(f"Chat SSE error: {payload.get('message')}")
                            elif payload.get("type") == "done":
                                text = "".join(tokens).strip()
                                if not text:
                                    fail("Chat returned empty response")
                                ok(f"Chat stream ({len(text)} chars): {text[:120]}...")
                                return sid
                buf = parts[-1]
    fail("Chat stream ended without done event")


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    print(f"\n=== Production smoke test: {base} ===\n")
    with httpx.Client(follow_redirects=True) as client:
        test_health(client, base)
        test_cors(client, base)
        test_ingest_and_chat(client, base)
    print("\n=== All checks passed ===\n")


if __name__ == "__main__":
    main()
