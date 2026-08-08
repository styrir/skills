# Veo 3.1

Higher-quality video, optionally from a start frame. Slower than Kling.

| Field | Value |
|---|---|
| Model ID | `veo-3.1-generate-preview` |
| Provider | Google AI Studio |
| Method | Async (predictLongRunning, then poll the operation) |
| Type | Video |
| API key | `~/.config/generate/.env` → `GEMINI_API_KEY` |
| Docs | https://ai.google.dev/gemini-api/docs/veo |
| Cost | 8-second clips by default (`durationSeconds` adjusts, within model-supported values — check docs), 720p–4K, 1–4 samples per call (each sample bills) — check the pricing page |

## Endpoint

```
POST https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning
```

Auth header: `x-goog-api-key: $GEMINI_API_KEY`.

## Request format

Vertex-style `instances` + `parameters` — NOT the Gemini `generateContent` shape:

```bash
source ~/.config/generate/.env
operation_name=$(curl -s "https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [{
      "prompt": "YOUR PROMPT",
      "image": {"mimeType": "image/png", "bytesBase64Encoded": "START_FRAME_BASE64"}
    }],
    "parameters": {"aspectRatio": "16:9", "resolution": "720p", "sampleCount": 1}
  }' | jq -r .name)
```

Omit `image` for pure text-to-video. The start frame uses `bytesBase64Encoded` — NOT `inlineData`; mixing the two formats is the top cause of 400 errors on this endpoint.

## Response handling

Poll every ~10 seconds until `.done == true`:

```bash
curl -s -H "x-goog-api-key: $GEMINI_API_KEY" \
  "https://generativelanguage.googleapis.com/v1beta/${operation_name}"
```

The finished operation carries the generated video's file URI (under `.response`, e.g. `...generateVideoResponse.generatedSamples[0].video.uri` — VERIFY the exact path against the docs on first use; SDK examples abstract it). Download it with the same `x-goog-api-key` header immediately: Google stores results only ~2 days.

## Notes

- Field placement matters: `aspectRatio` / `resolution` / `durationSeconds` / `sampleCount` go in `parameters`; the start-frame `image`, `lastFrame`, and `referenceImages` go in `instances[0]`. Misplacing one → 400.
- Paid video lane: quote first, explicit go, one approval = one run — and `sampleCount` multiplies the bill.
- Also available on Kie AI (separate veo endpoints there, not the unified jobs API) if Google AI Studio rejects the job.
