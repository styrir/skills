"""Run GPT Researcher deep research and write its returned sources as JSON to <out.json>.

Usage: gptr_deep_sources.py <question> <out.json>   (settings and keys come from the environment the TS adapter builds)
       gptr_deep_sources.py --check      (import check only: prints the installed version, no network)

Only {url, title} leave this process. GPT Researcher's report and research context are never produced:
they are not evidence, and skipping them keeps report text out of any ledger.
"""
import asyncio, importlib.metadata as md, json, sys
from pathlib import Path


def main() -> None:
    version = md.version("gpt-researcher")
    if sys.argv[1:] == ["--check"]:
        from gpt_researcher import GPTResearcher  # noqa: F401  (fails here if the install is broken)
        print(json.dumps({"gpt_researcher": version}))
        return
    from gpt_researcher import GPTResearcher

    researcher = GPTResearcher(sys.argv[1], report_type="deep")
    asyncio.run(researcher.conduct_research())
    sources = []
    for s in researcher.get_research_sources():
        url = s.get("url") if isinstance(s, dict) else s
        if url:
            sources.append({"url": url, "title": (s.get("title") if isinstance(s, dict) else None) or ""})
    # A file, not stdout: GPT Researcher logs to stdout.
    Path(sys.argv[2]).write_text(json.dumps({"gpt_researcher": version, "sources": sources,
                                              "gptr_cost_estimate_usd": researcher.get_costs()}))


main()
