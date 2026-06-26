import { Brain } from "lucide-react"
import { useState } from "react"
import AgentActivityTimeline from "@/components/AgentActivityTimeline"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useAgentJobs from "@/hooks/useAgentJobs"
import type { ProcessingJob } from "@/lib/api"

function JobStatusBadge({ status }: { status: string }) {
  if (status === "running") return <Badge variant="default" className="text-[10px] px-1.5 py-0">Running</Badge>
  if (status === "pending") return <Badge variant="secondary" className="text-[10px] px-1.5 py-0">Queued</Badge>
  if (status === "completed") return <Badge className="text-[10px] px-1.5 py-0 bg-green-600">Done</Badge>
  if (status === "cancelled") return <Badge variant="outline" className="text-[10px] px-1.5 py-0">Stopped</Badge>
  return <Badge variant="destructive" className="text-[10px] px-1.5 py-0">Failed</Badge>
}

function JobCard({ job }: { job: ProcessingJob }) {
  const { dismissJob, cancelJob } = useAgentJobs()
  const [stopping, setStopping] = useState(false)
  const isActive = job.status === "pending" || job.status === "running"

  const onStop = async () => {
    setStopping(true)
    try {
      await cancelJob(job.id)
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="rounded-lg border bg-background/60 p-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-xs font-medium truncate" title={job.label}>{job.label}</p>
        <JobStatusBadge status={job.status} />
      </div>
      <AgentActivityTimeline job={job} />
      {job.error && <p className="text-xs text-destructive mt-2">{job.error}</p>}
      {isActive && (
        <Button
          variant="destructive"
          size="sm"
          className="mt-2 h-7 text-xs w-full"
          disabled={stopping}
          onClick={onStop}
        >
          {stopping ? "Stopping…" : "Stop"}
        </Button>
      )}
      {(job.status === "completed" || job.status === "failed" || job.status === "cancelled") && (
        <Button variant="ghost" size="sm" className="mt-2 h-7 text-xs w-full" onClick={() => dismissJob(job.id)}>
          Dismiss
        </Button>
      )}
    </div>
  )
}

export default function AgentNetworkPanel() {
  const { jobs, activeJobs, clearFinished } = useAgentJobs()
  const display = jobs.slice(0, 3)
  const hasFinished = jobs.some((j) => ["completed", "failed", "cancelled"].includes(j.status))

  return (
    <aside className="w-80 border-l bg-card/50 flex flex-col shrink-0 hidden xl:flex">
      <div className="p-4 border-b flex items-center gap-2">
        <Brain className="h-4 w-4 text-primary" />
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-sm">Agent Activity</h2>
          <p className="text-[11px] text-muted-foreground truncate">
            {activeJobs.length > 0
              ? `${activeJobs.length} task${activeJobs.length > 1 ? "s" : ""} — live pipeline`
              : "Step timeline · similarity · skill chips"}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {display.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-12 px-2">
            <Brain className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>Upload resumes or save a JD to see pipeline progress live.</p>
            <p className="text-xs mt-2 opacity-70">Parse → verify → embed → search → score.</p>
          </div>
        )}

        {display.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>

      {hasFinished && activeJobs.length === 0 && (
        <div className="p-3 border-t">
          <Button variant="outline" size="sm" className="w-full text-xs" onClick={clearFinished}>
            Clear finished
          </Button>
        </div>
      )}
    </aside>
  )
}
