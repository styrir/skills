# GPT Image 2

Text inside images: signs, posters, menus, packaging, UI mockups. Best-in-class typography.

| Field | Value |
|---|---|
| Model ID | `openai/gpt-image-2` (edits/refs: `openai/gpt-image-2/edit`) |
| Provider | fal.ai |
| Method | Sync (instant reply; queue available for slow renders) |
| Type | Image |
| API key | `~/.config/generate/.env` → `FAL_KEY` |
| Docs | https://fal.ai/models/openai/gpt-image-2/api |
| Cost | ~$0.05 per image at medium quality — ballpark, checked 2026-08 |

## Endpoint

```
POST https://fal.run/openai/gpt-image-2
```

Auth header: `Authorization: Key $FAL_KEY` (the word `Key`, not `Bearer`).

## Request format

```bash
source ~/.config/generate/.env
curl -s -X POST "https://fal.run/openai/gpt-image-2" \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "YOUR PROMPT — put the exact text to render in quotes",
    "image_size": "landscape_16_9",
    "quality": "medium"
  }' > reply.json
```

With reference images, use the edit endpoint: `POST https://fal.run/openai/gpt-image-2/edit` with the refs as public URLs (upload local files first — see Notes) and an optional mask.

## Response handling

Sync. Image URL at `.images[0].url` — download immediately and save into `~/generations`:

```bash
curl -s -o ~/generations/{project}_{description}_{timestamp}.png "$(jq -r '.images[0].url' reply.json)"
```

## Notes

- VERIFY the `/edit` input field names (reference image list, mask) against the Docs link before first use — fal schemas are per-endpoint.
- Local refs need a public URL for fal: upload via fal's storage/CDN, or Kie AI's file-upload helper.
- Up to ~3840 px max edge, aspect ratio ≤ 3:1.
- Slow render or timeout: swap the host to `https://queue.fal.run/openai/gpt-image-2` (same body, same auth) → reply gives `request_id`, `status_url`, `response_url`; poll `status_url` every 5–10 s, then GET `response_url` for the same `.images[0].url` shape.
