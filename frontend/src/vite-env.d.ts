/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  /** Identifiants utilisés par les tests d'intégration uniquement. */
  readonly VITE_TEST_EMAIL?: string;
  readonly VITE_TEST_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
