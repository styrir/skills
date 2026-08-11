# Context7 CLI: Documentation Commands Summary

The Context7 CLI provides a two-step workflow to retrieve up-to-date documentation and code examples for any programming library or framework.

## Core Workflow
1. Resolve: Convert a library name into a specific Context7 Library ID.
2. Query: Use that ID to fetch documentation and code snippets.

Note: If a user provides an ID in `/org/project` or `/org/project/version` format, you can skip to Step 2.

## Step 1: Resolve a Library (`ctx7 library`)
This command maps a product name to a compatible ID. A `query` argument is required to rank results and disambiguate similar names.

### Usage Examples
```bash
ctx7 library react "How to clean up useEffect with async operations"
ctx7 library nextjs "How to set up app router with middleware"
ctx7 library prisma "How to define one-to-many relations with cascade delete"
```

### Selection Criteria
When choosing a library from the results, prioritize based on:
- Name Similarity: exact matches first
- Documentation Coverage: higher code snippet counts are preferred
- Source Reputation: prefer High or Medium authority indicators
- Benchmark Score: higher is better
- Versions: if the user specifies a version, prefer a version-specific ID

### Constraints & Tips
- Do not call `ctx7 library` more than 3 times per question.
- Never include sensitive data in the query.
- Use `--json` for scripting:
```bash
ctx7 library react "How to use hooks" --json | jq '.[0].id'
```

## Step 2: Query Documentation (`ctx7 docs`)
Retrieves specific technical answers and code blocks using the resolved library ID.

### Usage Examples
```bash
ctx7 docs /facebook/react "How to clean up useEffect with async operations"
ctx7 docs /vercel/next.js/v14.3.0-canary.87 "How to set up app router"
```

### Query Quality Guidelines
Use specific technical questions, not vague keywords.

### Output Types
1. Code snippets
2. Info snippets

### Constraints & Tips
- Do not call `ctx7 docs` more than 3 times per question.
- Output is clean when piped to other tools.

## Authentication & Limits
The tool works without authentication, but higher limits are available via:
1. `export CONTEXT7_API_KEY=your_key`
2. `ctx7 login`
