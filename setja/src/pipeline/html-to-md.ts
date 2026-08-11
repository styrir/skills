import TurndownService from 'turndown';
import { readUtf8 } from '../core/fs.js';
import { HexisProfile, Summarizer } from '../core/types.js';

const turndownService = new TurndownService({
  headingStyle: 'atx',
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
  emDelimiter: '*',
  strongDelimiter: '**'
});

export async function summarizeHtmlFiles(
  files: string[],
  summarizer: Summarizer,
  hexis: HexisProfile
): Promise<string> {
  const sections: string[] = [];

  for (const filePath of files) {
    const raw = readUtf8(filePath);
    const markdown = turndownService.turndown(raw).trim();
    const summaryInput = markdown || raw.replace(/\s+/g, ' ').trim();
    const summary = await summarizer.summarizeText(summaryInput, {
      hexis,
      sourcePath: filePath
    });

    sections.push(`## ${filePath}`);
    sections.push(summary.trim());
    sections.push('');
  }

  return sections.join('\n').trim();
}
