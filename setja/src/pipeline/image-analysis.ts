import sharp from 'sharp';
import { HexisProfile, Summarizer } from '../core/types.js';
import { guessMimeType, readBase64 } from './llm-summary.js';

export async function summarizeImageFiles(
  files: string[],
  summarizer: Summarizer,
  hexis: HexisProfile
): Promise<string> {
  const sections: string[] = [];

  for (const filePath of files) {
    const metadata = await sharp(filePath).metadata();

    const summary = summarizer.summarizeImage
      ? await summarizer.summarizeImage(
          {
            sourcePath: filePath,
            mimeType: guessMimeType(filePath),
            bytes: readBase64(filePath),
            metadata: {
              width: metadata.width,
              height: metadata.height,
              format: metadata.format,
              channels: metadata.channels,
              density: metadata.density
            }
          },
          {
            hexis,
            sourcePath: filePath
          }
        )
      : [
          `- file: ${filePath}`,
          `- width: ${String(metadata.width || '')}`,
          `- height: ${String(metadata.height || '')}`,
          `- format: ${String(metadata.format || '')}`
        ].join('\n');

    sections.push(`## ${filePath}`);
    sections.push(summary.trim());
    sections.push('');
  }

  return sections.join('\n').trim();
}
