---
name: convert-documents-to-markdown
description: Convert research and meeting documents to Markdown with extracted figures and editable math. Use local Pandoc for DOCX and full-page Marker OCR for digital or scanned PDFs, with source verification of mathematical notation. Other Office, OpenDocument, EPUB, RTF, and CSV extraction uses anydoc.
license: MIT
metadata:
  upstream-author: firecrawl
---

# Convert documents to Markdown

## Word and PDF research

Resolve `<skill-dir>` from this file. Use the bundled converter rather than
rediscovering tools or streaming a large document into agent context:

```sh
python3 <skill-dir>/scripts/research-convert '/absolute/path/input.docx'
python3 <skill-dir>/scripts/research-convert '/absolute/path/input.pdf'
# PDF preview: zero-based pages, inclusive ranges
python3 <skill-dir>/scripts/research-convert '/absolute/path/input.pdf' --pages 0-2 --out '/absolute/path/preview'
```

- The command prints the resulting Markdown path. Default output is a new `<stem>.research/` directory beside the source; `--out` chooses another directory. Use separate output directories for DOCX/PDF copies sharing a stem. Existing output is never overwritten. Reuse a conversion only after checking the source identity and required page range.
- DOCX uses Pandoc, producing pipe tables, dollar-delimited LaTeX for native equations, and extracted `assets/`. Equations stored as images remain images and need recognition/source recovery before editable-math acceptance. Legacy binary `.doc` needs saving as DOCX in Word first.
- PDFs use Marker with local llama.cpp inference and full-page OCR (`--mode balanced --force_ocr`), inline math, figure extraction, metadata, and page separators. Fast mode's text/font heuristics can omit image-based inline math; tight equation crops can produce repetition. Do not silently switch back to that path.
- Editable LaTeX is required for mathematical notation in research conversions. Original equation images may accompany it as evidence, but do not satisfy that requirement alone. If source notation is clipped or unreadable, keep reconstruction explicitly unverified and seek an uncropped source rather than certifying inferred symbols.
- When the original web source is available, inspect rendered math for `annotation[encoding="application/x-tex"]` or other explicit source notation. Prefer that original LaTeX to OCR reconstruction; record the source URL and formula identity with corrections. Shared Gemini pages can expose annotations even when Word/PDF exports clip mathematical images.
- Compare inline and display math with source images before accepting a math-heavy PDF: signs, subscripts, superscripts, repeated expressions, and missing notation. Correct transcription errors against the source and record corrections alongside the output. Successful exit and math-block counts do not establish fidelity. Check tables and reading order before relying on them.
- Keep Markdown and its assets together. Conversion preserves useful structure, not exact page layout. For large files, convert to disk, inspect size/headings, then read selected sections. An instruction not to read a document also excludes converting it until authorized.
- Processing uses local inference; no optional cloud LLM (`--use_llm`), hosted conversion, or external inference endpoint is enabled. Model downloads are inbound provisioning; weights are cached. Marker may retain local helper services between runs; the larger OCR inference server stops on exit.
- If conversion fails, report the failure. Do not silently substitute text-only extraction or upload the document elsewhere.

## Dependencies and verification

Requires Python 3, native `pandoc`, `marker_single`, and `llama-server` on PATH.
The qualified setup uses Pandoc 3.13, Marker 2.1.0 and llama.cpp 9820 on Apple
Silicon. Example dependency provisioning on macOS:

```sh
brew install pandoc llama.cpp
uv tool install --python 3.12 marker-pdf==2.1.0
```

First PDF use downloads models. Run the bundled synthetic regression check:

```sh
python3 <skill-dir>/scripts/check-test.py
# After model provisioning, verify cached-model reuse:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 <skill-dir>/scripts/check-test.py
```

The check covers Word text/table/image/native math, digital/scanned PDF text and
figures, raster inline signs/subscripts/equations, page selection, unchanged
sources and refusal to overwrite existing output. Fixtures are synthetic.
Read [qualification](references/qualification.md) when assessing the tested
setup and its limits; it does not certify arbitrary documents.

## Other document formats

For broad-format extraction, anydoc needs Node 20+:

```sh
npx -y @firecrawl/anydoc input.pptx -o out.md
```

- Supported: DOC/DOCX/DOCM, ODT, RTF, EPUB, PDF, PPT/PPS/POT/PPTX/PPTM/PPSX/PPSM/POTM, ODP, XLS/XLSX/XLSM/XLSB, ODS, CSV. Use the Word/PDF route above for those formats.
- Format detection uses file content; pass `--format` only for ambiguous inputs such as stdin CSV or a missing/wrong extension.
- Exit codes: 0 success, 1 conversion failure, 2 usage error. Anydoc does not OCR scanned PDFs; external conversion needs explicit authorization.
- Inside a Node, Python, or Rust codebase, prefer the anydoc library (`@firecrawl/anydoc`, `firecrawl-anydoc`, or `anydoc`) to shelling out when it fits the requested application.
