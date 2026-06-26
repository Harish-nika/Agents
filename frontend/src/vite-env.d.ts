/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_EXTRACTION_API_URL: string
  readonly VITE_MUNI_API_URL: string
  readonly VITE_DOCPROC_API_URL?: string
  /** When set, validation highlight/text hit this base URL instead of VITE_API_URL (backend proxy). */
  readonly VITE_VALIDATION_API_URL?: string
  readonly VITE_APP_VERSION: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
