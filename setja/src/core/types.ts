export interface HexisProfile {
  name: string;
  summary_style?: string;
  include?: string[];
  ignore?: string[];
  focus?: string[];
  boost?: string[];
}

export interface BuildOptions {
  hexisName: string;
}

export interface InjectOptions {
  hexisName: string;
  query?: string;
}

export interface ArtifactSummary {
  title: string;
  body: string;
  sourcePath: string;
  kind: 'research' | 'html' | 'image' | 'runir';
}

export interface SummarizerContext {
  hexis: HexisProfile;
  sourcePath: string;
  task?: string;
}

export interface Summarizer {
  summarizeText(input: string, context: SummarizerContext): Promise<string>;
  summarizeStructured?(input: Record<string, unknown>, context: SummarizerContext): Promise<string>;
  summarizeImage?(input: {
    sourcePath: string;
    mimeType: string;
    bytes: string;
    metadata: Record<string, unknown>;
  }, context: SummarizerContext): Promise<string>;
}

export interface RunirRecallResult {
  items: Array<{
    title?: string;
    text: string;
    score?: number;
    metadata?: Record<string, unknown>;
  }>;
}
