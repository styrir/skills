# Styrir workspace

Generated work belongs in the ignored repository-local `/.styrir/` workspace, not in source or maintained documentation by default.

```text
.styrir/
├── runs/
├── analysis/
│   ├── raw/
│   └── reports/
├── pipelines/
├── build/
├── cache/
├── logs/
└── tmp/
```

Use `runs/<run-id>/` for self-contained execution evidence, `analysis/` for generated analysis, `pipelines/` for local pipeline state and handoffs, and the remaining directories for disposable lifecycle-appropriate output.

Never store credentials in `.styrir/`. Ignoring a directory is not access control. Promote only the smallest reviewed durable artifact into tracked source or documentation.
