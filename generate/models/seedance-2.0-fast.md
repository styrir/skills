# Seedance 2.0 Fast

Reference-to-video: feed it up to 9 images and it animates them. Pick it when the user wants existing images brought to life rather than a scene from a text prompt.

| Field | Value |
|---|---|
| Model ID | `bytedance/seedance-2.0/fast/reference-to-video` |
| Provider | fal.ai |
| Method | Async (queue) |
| Type | Video |
| API key | `~/.config/generate/.env` → `FAL_KEY` |
| Docs | https://fal.ai/models/bytedance/seedance-2.0/fast/reference-to-video |
| Cost | $0.24 per second at 720p (a 5 s clip ≈ $1.21) — ballpark, checked 2026-08 |

## Endpoint

```
POST https://queue.fal.run/bytedance/seedance-2.0/fast/reference-to-video
```

Auth header: `Authorization: Key $FAL_KEY`.

## Request format

```bash
source ~/.config/generate/.env
curl -s -X POST "https://queue.fal.run/bytedance/seedance-2.0/fast/reference-to-video" \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "YOUR PROMPT describing the motion",
    "reference_image_urls": ["https://public.url/ref1.png"]
  }'
```

VERIFY the exact input field names (the reference-image list, duration, resolution) against the Docs link before the first call — the schema is per-model on fal. Local ref files from `~/generations/refs/` need public URLs first (fal storage upload, or Kie AI's file-upload helper).

## Response handling

Queue reply gives `request_id`, `status_url`, `response_url`, `cancel_url`. Poll `GET {status_url}` (same auth header) every 5–10 s until `"status": "COMPLETED"`, then `GET {response_url}` — the video URL is at `.video.url` (VERIFY on first use). Download immediately into `~/generations`; result URLs expire.

## Notes

- Up to 9 reference images.
- Paid video lane: quote first, explicit go, one approval = one run.
- Real refs, never described: this model exists precisely so you pass the actual files.
