# Styrir Search Provider Matrix

| Need | Preferred route | Existing skill to consult | Caveat |
| --- | --- | --- | --- |
| Current library/API docs | `direct_search` or `styrir_search` | `/Users/brooks/Code/skills/research/context7-cli/SKILL.md` | Resolve library ID before fetching docs. |
| Web discovery plus extraction | `styrir_search` or `styrir_plus` | `/Users/brooks/Code/skills/research/tavily-cli/SKILL.md` | Search snippets are discovery only; fetch/extract before evidence. |
| Provider-backed local Deep Search | `deep_search_local` | `/Users/brooks/Code/skills/research/deep-search-cli/SKILL.md` | Use the CLI path and preserve gate outputs. |
| Parallel provider/auth | `deep_search_local` support lane | `/Users/brooks/Code/skills/research/deep-search-provider-setup/SKILL.md` | Do not print credentials; report only provider path. |
| Optional Parallel vendor workflows | explicit Parallel request | `/Users/brooks/Code/skills/research/parallel-cli/SKILL.md` | Paid third-party service; do not silently prefer it for ordinary lookup. |
| Legacy Hermes structured search | migration/normalization | `/Users/brooks/Code/skills/research/structured-search-agent/SKILL.md` | Normalize YAML to Styrir JSON before using it as the canonical ledger. |
| NVIDIA AI-Q deep research | `nvidia_aiq_handoff` | AI-Q REST target or shipped AI-Q skill/CLI wrapper | Prefer REST API for local agent integration; no `aiqBaseUrl` means manifest-only handoff. |
