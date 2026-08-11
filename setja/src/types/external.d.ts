declare module 'yaml' {
  const YAML: {
    parse(input: string): any;
    stringify?(input: unknown): string;
  };

  export default YAML;
}

declare module 'sharp' {
  export interface Metadata {
    width?: number;
    height?: number;
    format?: string;
    channels?: number;
    density?: number;
  }

  export interface SharpInstance {
    metadata(): Promise<Metadata>;
  }

  export interface SharpStatic {
    (input: string | Buffer): SharpInstance;
  }

  const sharp: SharpStatic;
  export default sharp;
}
