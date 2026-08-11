import fs from 'node:fs';
import YAML from 'yaml';
import { HexisProfile } from './types.js';

export function loadHexisProfile(name: string): HexisProfile {
  const projectPath = `${process.cwd()}/hexis/${name}.yaml`;
  const chosenPath = fs.existsSync(projectPath)
    ? projectPath
    : `${process.cwd()}/hexis/default.yaml`;

  if (!fs.existsSync(chosenPath)) {
    throw new Error(`Hexis profile not found: ${name}`);
  }

  const raw = fs.readFileSync(chosenPath, 'utf-8');
  const parsed = YAML.parse(raw) as HexisProfile | null;

  if (!parsed || !parsed.name) {
    throw new Error(`Invalid Hexis profile: ${chosenPath}`);
  }

  return parsed;
}

export function shouldIncludePath(filePath: string, hexis: HexisProfile): boolean {
  const normalized = filePath.replaceAll('\\', '/');
  const ignoreList = hexis.ignore || [];
  const includeList = hexis.include || [];

  if (ignoreList.some((entry) => normalized.startsWith(entry.replaceAll('\\', '/')))) {
    return false;
  }

  if (includeList.length === 0) return true;

  return includeList.some((entry) => normalized.startsWith(entry.replaceAll('\\', '/')));
}
