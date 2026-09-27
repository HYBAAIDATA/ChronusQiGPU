/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Python backend base URL. Defaults to same-origin (Node proxy). */
  readonly VITE_PYTHIA_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
