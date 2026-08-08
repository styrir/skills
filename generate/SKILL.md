---
name: generate
description: Use when the user asks for media generation — /generate, generate or create an image, thumbnail, logo draft, poster, product shot, UI mockup, or generate video, animate an image, or turn reference images into a clip.
---

# /generate — routed media generation

One command for images and video. Route every request to the cheapest capable model, gate paid runs behind an explicit cost quote, save every output flat into one library, and log how each file was made.

## Preflight (every run)

1. Keys live in `~/.config/generate/.env` (`KIE_API_KEY`, `FAL_KEY`, `WAVESPEED_API_KEY`, `GEMINI_API_KEY`). If that file is missing, STOP and tell the user to copy `.env.example` from this skill folder to that path and fill it in. Read keys by sourcing the file in the shell — never paste key values into code, prompts, or logs.
2. The output library is `~/generations`, reference images in `~/generations/refs/`. Run `mkdir -p ~/generations/refs` if missing.

## Models

| Task | Default model | Recipe |
|---|---|---|
| Image — everyday & drafts (default) | Nano Banana 2 (Lite for drafts) | `models/nano-banana-2.md` |
| Image — readable text: signs, posters, menus, packaging, UI mockups | GPT Image 2 | `models/gpt-image-2.md` |
| Video — general (default) | Kling 3.0 | `models/kling-3.0.md` |
| Video — higher quality, or from a start frame | Veo 3.1 | `models/veo-3.1.md` |
| Video — animate reference images | Seedance 2.0 Fast | `models/seedance-2.0-fast.md` |

Read the recipe file before every generation. To add a model, copy `models/_template.md` — one markdown file per model, nothing else changes.

## Provider routing

1. Default to the LOWEST COST provider that runs the model well (compare Kie AI, fal.ai, Google AI Studio direct; each recipe names its primary).
2. If the cheapest route lacks the model, fails auth, or errors, fall back to the next provider. WaveSpeed AI is the last-resort fallback — it has no recipe here yet; check wavespeed.ai for the model path and add a recipe if you wire it.
3. Never hide a provider swap. Say which route ran and why.

## Output

- Save every file FLAT into `~/generations`. No subfolders.
- Reference images live in `~/generations/refs/`.
- Naming: `{project}_{description}_{unix-timestamp}.{ext}` — lowercase snake_case. `{project}` is the active project or repo name; with no project context, use a short slug from the subject instead of asking.

## Rules

- Quote the model, duration, resolution, and expected dollars (the recipe's ballpark, labeled as a ballpark), then wait for the user's explicit go before any paid video run. Quoting alone is not approval. One approval = one run.
- Draft on the cheap image model first. Rerun on a quality model only when the user picks a favourite.
- Never describe a specific logo, face, or branded product in words. Pass the real image file from `~/generations/refs/` as a reference; if it's missing, stop and ask the user for it. Generic scene objects (a kayak, a mountain, a coffee cup) belong in the prompt text as usual.
- Defaults when the user doesn't specify: 16:9 aspect, the cheapest quality tier (std/720p video, 1K image), 5-second clips.
- Run generations one at a time to avoid rate limits.
- After every save, write the sidecar log.

## Sidecar log

After each saved file, write a same-basename `.json` next to it:

```json
{
  "model": "kling-3.0/video",
  "prompt": "the full text prompt that was sent to the API",
  "refs": ["refs/logo.png"],
  "params": { "aspect": "16:9", "duration": 5 },
  "created": "2026-08-08T09:41:00Z"
}
```

Same basename plus `.json` is the contract — any future tool or a plain folder search can recover exactly how a file was made. `model` is the Model ID from the recipe's table, verbatim.

## Async pattern (most video models)

1. POST the job → the reply contains a task id
2. Poll the status URL → every 5 to 10 seconds, patiently
3. Status says complete → the reply now contains a file URL
4. Download immediately → result URLs often expire in hours
5. Save into `~/generations`, then write the sidecar log

## Maintenance

- A "model not found" error means the provider shipped a new version: copy the fresh id from that provider's model page into the recipe file. That is the only maintenance this system needs.
- Costs in recipes are ballparks (checked 2026-08). Check the provider's pricing page before promising a price.

## Bonus

`references/gallery-prompt.md` holds a copy-paste prompt that builds a local gallery-wall page over `~/generations`.
