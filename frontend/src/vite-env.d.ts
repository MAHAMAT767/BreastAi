/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  /** Identifiants utilisés par les tests d'intégration uniquement. */
  readonly VITE_TEST_EMAIL?: string;
  readonly VITE_TEST_PASSWORD?: string;
  /** `'1'` : une API injoignable devient un échec au lieu d'un test ignoré. */
  readonly VITE_REQUIRE_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
