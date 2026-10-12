# Untrusted repository and suspicious-URL safety

Use this during repository comparisons, tool evaluations, skill acquisition, supply-chain review, and incident follow-up involving untrusted source code.

## Pre-execution triage

Quarantine is necessary but not sufficient. Before running an advertised CLI, installer, test suite, package script, container, or application entry point:

1. Read the manifest and the actual entry point named by the README.
2. Trace imports from that entry point far enough to identify startup side effects.
3. Search the staged tree for:
   - subprocess or shell execution;
   - downloader-then-execute chains;
   - hidden-window or noninteractive PowerShell;
   - encoded commands and IP-literal URLs;
   - credential, wallet, exchange, proxy/account, persistence, or remote-control code unrelated to the stated purpose;
   - install hooks and package lifecycle scripts.
4. Treat topical mismatch as a high-signal finding. A writing tool containing transaction signing, exchange-account automation, or hidden executable launchers is unsafe regardless of README claims.
5. Do not rely on a skill-specific scanner to assess a general application repository. Combine static scanners with direct review of the real executable path.
6. Do not execute the candidate merely to confirm suspicious behavior. Source evidence is sufficient to reject a downloader/launcher.

## Defang hostile indicators

Never emit a suspected payload URL as a live raw URL in user-facing prose, code blocks, Markdown, tool annotations, or issue drafts. Desktop renderers and link-preview systems may fetch URLs automatically even inside code formatting.

Use a non-resolvable representation such as:

- `hxxp://example[.]invalid/file[.]exe`
- `203[.]0[.]113[.]10:8000/payload[.]exe`

Keep enough structure for identification while preventing click-through and automatic unfurling. Do not send a suspected binary URL to extraction, browser, preview, or metadata tools. Inspect the URL string from local source instead.

## If rendering triggers a download prompt

1. Tell the user to cancel; do not save or open the file.
2. Identify the owning application and correlate the prompt time with process, parent-process, and network logs.
3. Check the intended download directory, temporary directories, application data, partial-download suffixes, and filename search results.
4. Check for matching processes and active connections, including platform-specific execution layers such as Wine.
5. Distinguish clearly among:
   - remote contact or metadata fetch;
   - payload transfer into cache or a save dialog;
   - file saved to disk;
   - payload execution.
6. Disclose any confirmed remote contact even when no file was saved.
7. Keep every indicator defanged in the incident report so the report cannot retrigger the fetch.

## Reporting standard

State:

- which source file or rendered message contained the indicator;
- which process initiated the connection and what evidence supports attribution;
- whether a file or partial file exists;
- whether any execution process or connection remains;
- what is known versus inferred;
- the containment action and recommended product/security follow-up.
