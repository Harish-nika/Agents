const API_BASE = import.meta.env.VITE_API_URL || ""

const GROQ_SESSION_KEY = "groq_session_key"
const GROQ_LLM_MODE = "groq_llm_mode"

export type GroqLlmMode = "saved" | "session" | "ollama"

function getToken(): string {
  return localStorage.getItem("access_token") || ""
}

export function getGroqLlmMode(): GroqLlmMode {
  const mode = localStorage.getItem(GROQ_LLM_MODE)
  if (mode === "saved" || mode === "session" || mode === "ollama") return mode
  return "saved"
}

export function setGroqLlmMode(mode: GroqLlmMode) {
  localStorage.setItem(GROQ_LLM_MODE, mode)
}

export function getGroqSessionKey(): string {
  return localStorage.getItem(GROQ_SESSION_KEY) || ""
}

export function setGroqSessionKey(key: string) {
  const trimmed = key.trim()
  if (trimmed) localStorage.setItem(GROQ_SESSION_KEY, trimmed)
  else localStorage.removeItem(GROQ_SESSION_KEY)
}

/** @deprecated use session key + mode */
export function getGroqApiKey(): string {
  return getGroqSessionKey()
}

export function setGroqApiKey(key: string) {
  setGroqSessionKey(key)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const mode = getGroqLlmMode()
  if (mode === "session") {
    const sessionKey = getGroqSessionKey()
    if (sessionKey) headers["X-Groq-API-Key"] = sessionKey
  } else if (mode === "ollama") {
    headers["X-Groq-Prefer"] = "ollama"
  } else if (mode === "saved") {
    headers["X-Groq-Prefer"] = "saved"
  }
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json"
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, err.detail || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  login: (username: string, password: string) =>
    apiFetch<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => apiFetch<{ username: string }>("/api/v1/auth/me"),
  dashboard: () => apiFetch<DashboardStats>("/api/v1/dashboard/stats"),
  jds: (activeOnly = false) =>
    apiFetch<JD[]>(`/api/v1/jds?active_only=${activeOnly}`),
  getJd: (id: number) => apiFetch<JD>(`/api/v1/jds/${id}`),
  createJd: (data: JDInput) =>
    apiFetch<JD>("/api/v1/jds", { method: "POST", body: JSON.stringify(data) }),
  updateJd: (id: number, data: JDInput) =>
    apiFetch<JD>(`/api/v1/jds/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  archiveJd: (id: number) =>
    apiFetch("/api/v1/jds/" + id + "/archive", { method: "POST" }),
  restoreJd: (id: number) =>
    apiFetch<JD>(`/api/v1/jds/${id}/restore`, { method: "POST" }),
  deleteJd: (id: number) =>
    apiFetch<void>(`/api/v1/jds/${id}`, { method: "DELETE" }),
  indexJdAsync: (id: number) =>
    apiFetch<JobCreated>(`/api/v1/jds/${id}/index-async`, { method: "POST" }),
  parseJd: (raw_text: string) =>
    apiFetch<JDParsed>("/api/v1/jds/parse", {
      method: "POST",
      body: JSON.stringify({ raw_text }),
    }),
  parseJdAsync: (raw_text: string) =>
    apiFetch<JobCreated>("/api/v1/jds/parse-async", {
      method: "POST",
      body: JSON.stringify({ raw_text }),
    }),
  getJobs: (ids: number[]) =>
    apiFetch<ProcessingJob[]>(`/api/v1/jobs?ids=${ids.join(",")}`),
  getJob: (id: number) => apiFetch<ProcessingJob>(`/api/v1/jobs/${id}`),
  cancelJob: (id: number) =>
    apiFetch<ProcessingJob>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }),
  candidates: (status?: string) =>
    apiFetch<Candidate[]>(`/api/v1/candidates${status ? `?status=${status}` : ""}`),
  deleteCandidate: (id: number) =>
    apiFetch<void>(`/api/v1/candidates/${id}`, { method: "DELETE" }),
  deleteAllCandidates: () =>
    apiFetch<void>("/api/v1/candidates", { method: "DELETE" }),
  uploadResume: (file: File, targetJdId?: number) => {
    const form = new FormData()
    form.append("file", file)
    if (targetJdId) form.append("target_jd_id", String(targetJdId))
    return apiFetch<Candidate>("/api/v1/candidates/upload", {
      method: "POST",
      body: form,
    })
  },
  uploadResumeAsync: (file: File, targetJdId?: number) => {
    const form = new FormData()
    form.append("file", file)
    if (targetJdId) form.append("target_jd_id", String(targetJdId))
    return apiFetch<JobCreated>("/api/v1/candidates/upload-async", {
      method: "POST",
      body: form,
    })
  },
  hrQuestions: () => apiFetch<HRQuestion[]>("/api/v1/hr-questions"),
  hrQuestionsGrouped: () => apiFetch<HRCandidateGroup[]>("/api/v1/hr-questions/grouped"),
  updateQuestion: (id: number, data: { status?: string; hr_answer?: string }) =>
    apiFetch<HRQuestion>(`/api/v1/hr-questions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  reassessSuspicion: (candidateId: number) =>
    apiFetch<JobCreated>(`/api/v1/candidates/${candidateId}/reassess-suspicion`, {
      method: "POST",
    }),
  groqSettings: () => apiFetch<GroqSettings>("/api/v1/settings/groq"),
  saveGroqKey: (api_key: string) =>
    apiFetch<GroqSettings>("/api/v1/settings/groq", {
      method: "PUT",
      body: JSON.stringify({ api_key }),
    }),
  deleteGroqKey: () =>
    apiFetch<{ ok: boolean }>("/api/v1/settings/groq", { method: "DELETE" }),
  health: () => apiFetch<{ status: string; ollama: boolean; ollama_cpu: boolean; ollama_gpu: boolean; groq?: boolean; using_groq?: boolean }>("/api/v1/health"),
}

export interface DashboardStats {
  active_jds: number
  candidates: number
  analyzed: number
  failed: number
  avg_score: number
  pending_questions: number
  ollama_ok: boolean
  ollama_cpu?: boolean
  ollama_gpu?: boolean
  groq_ok?: boolean
  using_groq?: boolean
}

export interface JD {
  id: number
  title: string
  role: string
  department: string
  seniority: string
  content: string
  skills: string[]
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface JDInput {
  title: string
  role: string
  department: string
  seniority: string
  content: string
  skills: string[]
}

export interface JDParsed {
  role: string
  title: string
  department: string
  seniority: string
  skills: string[]
  must_haves: string[]
  nice_to_haves: string[]
  content: string
}

export interface Analysis {
  id: number
  candidate_id: number
  jd_id: number
  jd_title: string
  jd_role: string
  technical_score: number
  hr_score: number
  overall_score: number
  fit_summary: string
  strengths: string[]
  gaps: string[]
  suspicion_score: number
  suspicion_flags: string[]
  suspicion_reasoning?: string
  hr_verification_summary?: string
  recommended_role: string
  similarity_score: number
}

export interface Candidate {
  id: number
  name: string
  email: string
  phone: string
  status: string
  parse_method: string
  created_at?: string
  analyses: Analysis[]
  pending_hr_questions?: number
  verification_summary?: string
  verification_category_counts?: Record<string, number>
  verification_completeness?: number | null
}

export interface HRQuestion {
  id: number
  candidate_id: number
  candidate_name: string
  analysis_id: number
  question: string
  category?: string
  source_flag?: string
  resume_excerpt?: string
  hr_answer?: string
  status: string
  suspicion_score: number
  suspicion_flags?: string[]
  suspicion_reasoning?: string
  jd_title: string
  created_at?: string
  answered_at?: string
}

export interface HRCandidateGroup {
  candidate_id: number
  candidate_name: string
  suspicion_score: number
  suspicion_flags: string[]
  suspicion_reasoning: string
  jd_title: string
  verification_summary?: string
  verification_category_counts?: Record<string, number>
  questions: HRQuestion[]
}

export interface JobStep {
  id: string
  label: string
  status: string
}

export interface ProcessingJob {
  id: number
  job_type: string
  label: string
  status: string
  current_step: string
  steps: JobStep[]
  viz?: Record<string, unknown> | null
  result: Record<string, unknown> | null
  error: string
  candidate_id: number | null
  created_at?: string
  updated_at?: string
}

export interface JobCreated {
  job_id: number
}

export interface GroqSettings {
  has_saved_key: boolean
  key_mask: string
  updated_at?: string | null
}
