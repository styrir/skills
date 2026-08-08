# Model Name

One line on what this model is best at and when to pick it.

| Field | Value |
|---|---|
| Model ID | the-exact-model-id |
| Provider | Kie AI / fal.ai / WaveSpeed AI / Google AI Studio |
| Method | Sync (instant reply) or Async (submit, then poll) |
| Type | Image or Video |
| API key | `~/.config/generate/.env` → KEY_NAME |
| Docs | link to the provider's page for this model |
| Cost | rough price per image / per second |

## Endpoint

```
POST https://...
```

## Request format

(the exact JSON body from the docs, with prompt, aspect ratio, resolution, reference image fields)

## Response handling

(where the image/video lives in the reply: base64 field, or a URL to download. For async: the status endpoint and the field that says "done".)

## Notes

(gotchas: rate limits, max sizes, content rules, upload quirks)
