# Kling 3.0

General video. The sensible default: good motion, fair price.

| Field | Value |
|---|---|
| Model ID | `kling-3.0/video` |
| Provider | Kie AI |
| Method | Async (submit, then poll) |
| Type | Video |
| API key | `~/.config/generate/.env` → `KIE_API_KEY` |
| Docs | https://kie.ai/model/kling-3.0/video.md (plain markdown — fetch it to check the current input schema) |
| Cost | video ballpark $0.20–0.35 per second; std = 720p, pro = 1080p; 3–15 s clips — checked 2026-08 |

## Endpoint

```
POST https://api.kie.ai/api/v1/jobs/createTask
```

Auth header: `Authorization: Bearer $KIE_API_KEY`.

## Request format

```bash
source ~/.config/generate/.env
curl -s -X POST "https://api.kie.ai/api/v1/jobs/createTask" \
  -H "Authorization: Bearer $KIE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kling-3.0/video",
    "input": {
      "prompt": "YOUR PROMPT",
      "duration": 5,
      "aspect_ratio": "16:9"
    }
  }'
```

`input` also accepts `image_urls` for image-to-video and a std/pro quality switch — VERIFY the exact field names against the Docs URL before the first call.

## Response handling

Async. createTask replies `{"code":200,"msg":"success","data":{"taskId":"..."}}`. The `code` inside the body must be 200 — HTTP 200 with a body `code != 200` is an application-level failure.

Poll every 5–10 seconds:

```bash
curl -s -H "Authorization: Bearer $KIE_API_KEY" \
  "https://api.kie.ai/api/v1/jobs/recordInfo?taskId=$TASK_ID"
```

`data.state` walks `waiting | queuing | generating | success | fail`. On `success`, `data.resultJson` is a JSON **string** — parse it, then download `resultUrls[0]` immediately (result URLs expire) into `~/generations`. On `fail`, surface `failCode` / `failMsg` to the user.

## Notes

- Paid video lane: quote model, duration, resolution, and dollars, then wait for an explicit go. One approval = one run.
- 402 = insufficient Kie credits; 429 = rate limited — back off, one job at a time.
- Local ref images need public URLs; Kie has a file-upload helper for that.
