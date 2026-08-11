# GitNexus code intelligence

Load this document for architecture exploration, execution-flow tracing, dependency or blast-radius analysis, API-route analysis, structural debugging, symbol refactors, or change-impact verification.

- `.gitnexusrc` pins pure index mode so analysis does not rewrite hand-authored agent guidance.
- `.gitnexus/` is generated local graph storage and must remain ignored.
- Use GitNexus as a structural map, then confirm load-bearing conclusions in source and tests.

After the repository has at least one Git commit:

```bash
gitnexus analyze .
gitnexus status
```

Before changing indexed symbols, resolve the symbol and run impact analysis. Treat HIGH, CRITICAL, and UNKNOWN risk as requiring explicit investigation. Before commit or handoff, run change detection when available and report any index or worktree-resolution limitation.
