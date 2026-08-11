declare module "node:fs" {
  export function appendFileSync(path: string, data: string): void;
  export function existsSync(path: string): boolean;
  export function mkdirSync(path: string, options?: any): void;
  export function readFileSync(path: string | number, encoding: string): string;
  export function readdirSync(path: string): string[];
  export function statSync(path: string): { isDirectory(): boolean; isFile(): boolean };
  export function writeFileSync(path: string, data: string): void;
  export function mkdtempSync(prefix: string): string;
}

declare module "node:url" {
  export function pathToFileURL(path: string): { href: string };
  export function fileURLToPath(url: string | URL): string;
}

declare module "node:assert/strict" {
  const assert: any;
  export default assert;
}

declare module "node:child_process" {
  export function spawnSync(...args: any[]): any;
}

declare module "node:os" {
  export function tmpdir(): string;
}

declare module "node:path" {
  export function join(...parts: string[]): string;
  export function dirname(path: string): string;
}

declare module "node:test" {
  const test: any;
  export default test;
}

declare const process: any;
declare const console: any;
declare const URL: any;
declare function structuredClone<T>(value: T): T;

interface ImportMeta {
  url: string;
}
