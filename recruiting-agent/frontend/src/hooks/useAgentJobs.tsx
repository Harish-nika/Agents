import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { api, type ProcessingJob } from "@/lib/api"
import { isLoggedIn } from "@/hooks/useAuth"

const STORAGE_KEY = "ats_active_job_ids"

type JobCallback = (job: ProcessingJob) => void

interface AgentJobsContextValue {
  jobs: ProcessingJob[]
  activeJobs: ProcessingJob[]
  trackJob: (id: number, onComplete?: JobCallback) => void
  dismissJob: (id: number) => void
  cancelJob: (id: number) => Promise<void>
  clearFinished: () => void
}

const AgentJobsContext = createContext<AgentJobsContextValue | null>(null)

function loadStoredIds(): number[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "number") : []
  } catch {
    return []
  }
}

function saveIds(ids: number[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
}

export function AgentJobsProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [jobIds, setJobIds] = useState<number[]>(loadStoredIds)
  const callbacksRef = useRef<Map<number, JobCallback>>(new Map())
  const firedRef = useRef<Set<number>>(new Set())

  const persistIds = useCallback((ids: number[]) => {
    setJobIds(ids)
    saveIds(ids)
  }, [])

  const trackJob = useCallback((id: number, onComplete?: JobCallback) => {
    if (onComplete) callbacksRef.current.set(id, onComplete)
    setJobIds((prev) => {
      const next = [...new Set([...prev, id])]
      saveIds(next)
      return next
    })
  }, [])

  const dismissJob = useCallback(
    (id: number) => {
      callbacksRef.current.delete(id)
      firedRef.current.delete(id)
      persistIds(jobIds.filter((x) => x !== id))
    },
    [jobIds, persistIds],
  )

  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs", jobIds],
    queryFn: () => api.getJobs(jobIds),
    enabled: jobIds.length > 0 && isLoggedIn(),
    refetchInterval: (query) => {
      const list = query.state.data
      if (!list?.some((j) => j.status === "pending" || j.status === "running")) return false
      return 1500
    },
  })

  const cancelJob = useCallback(
    async (id: number) => {
      await api.cancelJob(id)
      qc.invalidateQueries({ queryKey: ["jobs", jobIds] })
      qc.invalidateQueries({ queryKey: ["candidates"] })
    },
    [qc, jobIds],
  )

  const clearFinished = useCallback(() => {
    const activeIds = new Set(
      jobs.filter((j) => j.status === "pending" || j.status === "running").map((j) => j.id),
    )
    persistIds(jobIds.filter((id) => activeIds.has(id)))
  }, [jobs, jobIds, persistIds])

  useEffect(() => {
    for (const job of jobs) {
      if (!["completed", "failed", "cancelled"].includes(job.status)) continue
      if (firedRef.current.has(job.id)) continue
      firedRef.current.add(job.id)
      const cb = callbacksRef.current.get(job.id)
      if (cb) {
        cb(job)
        callbacksRef.current.delete(job.id)
      }
      if (job.job_type === "resume_analysis" && job.status === "completed") {
        qc.invalidateQueries({ queryKey: ["candidates"] })
        qc.invalidateQueries({ queryKey: ["dashboard"] })
      }
    }
  }, [jobs, qc])

  const activeJobs = useMemo(
    () => jobs.filter((j) => j.status === "pending" || j.status === "running"),
    [jobs],
  )

  const value = useMemo(
    () => ({ jobs, activeJobs, trackJob, dismissJob, cancelJob, clearFinished }),
    [jobs, activeJobs, trackJob, dismissJob, cancelJob, clearFinished],
  )

  return <AgentJobsContext.Provider value={value}>{children}</AgentJobsContext.Provider>
}

export default function useAgentJobs() {
  const ctx = useContext(AgentJobsContext)
  if (!ctx) throw new Error("useAgentJobs must be used within AgentJobsProvider")
  return ctx
}
