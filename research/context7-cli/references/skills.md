# Skills Commands
Manage AI coding skills from the Context7 registry.

## Install
```bash
ctx7 skills install /anthropics/skills
ctx7 skills install /anthropics/skills pdf
ctx7 skills install /anthropics/skills --all
```

Target a specific IDE:
```bash
ctx7 skills install /anthropics/skills pdf --claude
ctx7 skills install /anthropics/skills pdf --cursor
ctx7 skills install /anthropics/skills pdf --universal
ctx7 skills install /anthropics/skills --all --global
```

## Search
```bash
ctx7 skills search pdf
ctx7 skills search typescript testing
ctx7 skills search react nextjs
```

## Suggest
```bash
ctx7 skills suggest
ctx7 skills suggest --global
ctx7 skills suggest --claude
```

## Generate
Requires login.
```bash
ctx7 skills generate
ctx7 skills generate --claude
ctx7 skills generate --global
```

## List
```bash
ctx7 skills list
ctx7 skills list --claude
ctx7 skills list --global
```

## Remove
```bash
ctx7 skills remove pdf
ctx7 skills remove pdf --claude
ctx7 skills remove pdf --global
```

## Info
```bash
ctx7 skills info /anthropics/skills
```
