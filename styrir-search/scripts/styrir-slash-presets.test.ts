import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const skillDir = dirname(dirname(fileURLToPath(import.meta.url)));
const skillsRoot = dirname(skillDir);

const presets = [
  {
    folder: "styrir-search-simple",
    displayName: "StyrirSearch:simple",
    mode: "styrir_search",
    copy: "Use for normal bounded search with a JSON evidence ledger."
  },
  {
    folder: "styrir-search-plus",
    displayName: "StyrirSearch:plus",
    mode: "styrir_plus",
    copy: "Use for contested or multi-facet search with a contradiction sweep."
  },
  {
    folder: "styrir-search-deep-local",
    displayName: "StyrirSearch:deep-local",
    mode: "deep_search_local",
    copy: "Use for a local deep-search handoff manifest."
  },
  {
    folder: "styrir-search-deep-aiq",
    displayName: "StyrirSearch:deep-AIQ",
    mode: "nvidia_aiq_handoff",
    copy: "Use for a configured NVIDIA AI-Q target or handoff manifest."
  }
];

function readPreset(folder: string, relativePath: string): string {
  return readFileSync(join(skillsRoot, folder, relativePath), "utf8");
}

test("slash preset wrapper skills surface the requested Styrir lanes", () => {
  for (const preset of presets) {
    const skill = readPreset(preset.folder, "SKILL.md");
    const metadata = readPreset(preset.folder, "agents/openai.yaml");

    assert.match(skill, new RegExp(`name: ${preset.folder}`));
    assert.match(skill, /REQUIRED BASE SKILL: styrir-search/);
    assert.match(skill, new RegExp(`forceMode.: .${preset.mode}.`));
    assert.match(skill, new RegExp(preset.copy.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));

    assert.match(metadata, new RegExp(`display_name: "${preset.displayName}"`));
    assert.ok(metadata.includes(`Use $${preset.folder}`));
    assert.match(metadata, new RegExp(`forceMode=${preset.mode}`));
  }
});
