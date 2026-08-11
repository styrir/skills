import { readUtf8 } from '../core/fs.js';
import { HexisProfile, Summarizer } from '../core/types.js';

export async function summarizeResearchFiles(
  files: string[],
  summarizer: Summarizer,
  hexis: HexisProfile
): Promise<string> {
  const sections: string[] = [];

  for (const filePath of files) {
    const raw = readUtf8(filePath);
    const summary = await summarizer.summarizeText(raw, {
      hexis,
      sourcePath: filePath
    });

    sections.push(`## ${filePath}`);
    sections.push(summary.trim());
    sections.push('');
  }

  return sections.join('\n').trim();
}
