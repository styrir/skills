# Qualification snapshot — 2026-11-08

## Boundary

Local DOCX/PDF conversion and mathematical-fidelity verification guidance.
Acceptance covers the bundled synthetic fixtures and installed source links;
it does not certify every future document, perfect OCR, or research claims.

## Diagnosis and change

- Fast PDF extraction omitted image-based inline math because its math detection
  depends on text/font signals. Tight equation recognition also produced repeated
  expressions on an owner-provided input, observed earlier in this author session.
- The converter uses full-page balanced OCR. The skill requires source comparison,
  logged corrections, and original LaTeX recovery when clipped exports are ambiguous.
- Original web math annotations resolved ambiguous notation during that session.
  No owner documents, source URLs, captured content, or generated research outputs
  are included here.

## Observed checks

- Apple Silicon; Pandoc 3.13, Marker 2.1.0, Surya 0.23.0, llama.cpp 9820.
- `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 convert-documents-to-markdown/scripts/check.py`:
  PASS using cached models. Word text/table/image/native math, digital/scanned PDF
  text/figures, raster inline signed values and subscripts, equation recognition,
  selected pages, unchanged source hashes, and refusal to overwrite output.
- Ruff, skill validation and `git diff --check`: PASS.
- Harness manifest check for shared agents and Claude: PASS. The existing
  `research-convert` command and both skill discovery paths resolve to repository
  source. The previous local directory was backed up by the standard link manager.
- DOX pass: README indexes the new skill; its SKILL.md owns and links its scripts,
  fixtures and this snapshot. Root AGENTS.md routing remains applicable unchanged.

## Limits

- Other formats' anydoc route was retained from the upstream skill, not live-qualified.
- Marker may keep local helper services alive; its larger inference process stops
  on exit. Package/model provisioning and arbitrary malformed inputs are outside
  the fixture check.
- OCR output still needs mathematical verification. Original images alone do not
  meet the operator's editable-LaTeX requirement.
