# Nano Banana 2

Everyday images. Cheap, fast, strong with reference images. Use Lite for drafts, the full model for finals.

| Field | Value |
|---|---|
| Model ID | `gemini-3.1-flash-image-preview` (Lite: `gemini-3.1-flash-lite-image`) |
| Provider | Google AI Studio (also on fal.ai; on Kie AI as `nano-banana-2`) |
| Method | Sync (instant reply) |
| Type | Image |
| API key | `~/.config/generate/.env` → `GEMINI_API_KEY` |
| Docs | https://ai.google.dev/gemini-api/docs/image-generation |
| Cost | ~$0.034 per 1K image (Lite less) — ballpark, checked 2026-08 |

## Endpoint

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model-id}:generateContent
```

Auth header: `x-goog-api-key: $GEMINI_API_KEY` (the older `?key=` URL param also works).

## Request format

```bash
source ~/.config/generate/.env
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-image:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "role": "user",
      "parts": [
        {"text": "YOUR PROMPT"},
        {"inlineData": {"mimeType": "image/png", "data": "BASE64_REF_IMAGE"}}
      ]
    }],
    "generationConfig": {
      "responseModalities": ["IMAGE"],
      "imageConfig": {"aspectRatio": "16:9", "imageSize": "1K"}
    }
  }' > reply.json
```

Reference images: base64-encode files from `~/generations/refs/` into `inlineData.data` — raw base64, no `data:image/png;base64,` prefix. One `inlineData` part per ref (up to 14). Omit the `inlineData` part for pure text-to-image.

## Response handling

Sync. The image comes back base64 at `candidates[0].content.parts[].inlineData.data` with `mimeType` alongside. Decode and save:

```bash
jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' reply.json \
  | base64 -d > ~/generations/{project}_{description}_{timestamp}.png
```

## Notes

- Missing `"responseModalities": ["IMAGE"]` silently produces text-only output — the most common "it returned no image" cause.
- Truncated base64 or a data-URL prefix in `inlineData.data` → 400 invalid argument.
- `imageConfig.imageSize` takes `1K` / `2K` / `4K`; `aspectRatio` takes `1:1`, `16:9`, `9:16`, etc.
- Google requires API-restricted keys (enforced since 2026-06). On persistent 403s, restrict the key to the Generative Language API in Cloud Console.
- Kie AI fallback: model `nano-banana-2` via the Kie jobs flow (createTask/recordInfo — see `kling-3.0.md` for the shape); its `input` takes `prompt`, `image_input` (public URLs), `aspect_ratio`, `resolution` (1K/2K/4K), `output_format`.
- fal.ai also hosts it; check https://fal.ai/models for the current path if both other routes fail.
