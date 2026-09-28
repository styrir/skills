# Jev research sources

- Video: "10 Levels of Jev For Agentic Engineers", IndyDevDan, published 2026-09-28, 35:17 — https://www.youtube.com/watch?v=_U-O5lYhJ7Q
  Local transcript (YouTube auto-captions, not committed): `research/jev/transcript.md`
- Repo: https://github.com/disler/ten-levels-of-jev (MIT) @ `777adaf47d37ae0553220d35b2f15b3a3a063305` — local clone (not committed): `research/jev/repo/`
- OpenRouter: Jev hub https://openrouter.ai/docs/guides/community/jev · "What is Jev" https://openrouter.ai/blog/insights/what-is-jev/ · "Jev vs LLM" benchmarks https://openrouter.ai/blog/tutorials/jev-vs-llm-when-to-use-each/ · Auto-approve permission prompts cookbook https://openrouter.ai/docs/cookbook/coding-agents/auto-approve-permission-prompts-with-jev
- TypeSafe: jaggedness (v1.13) https://docs.typesafe.ai/model-jaggedness/jev-1.13
- Requesty: Decisions https://docs.requesty.ai/features/decisions · model page https://www.requesty.ai/model/typesafe/jev
- Prior internal assessment: ~/Code/agent-ops/docs/jev-workgraph-assessment.md (2026-09-19, untracked in agent-ops)

To re-create local-only inputs:
```bash
gh repo clone disler/ten-levels-of-jev research/jev/repo -- --depth 1
yt-dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt -o research/jev/video.%(ext)s https://www.youtube.com/watch?v=_U-O5lYhJ7Q
```
