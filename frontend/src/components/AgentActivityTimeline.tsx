import { useMemo } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react"
import type { JobStep, ProcessingJob } from "@/lib/api"

const PHASE_LABEL: Record<string, string> = {
  receive: "Receiving file",
  parse: "Parsing resume",
  normalize: "Structuring text",
  verify: "Verifying education & experience",
  embed: "Embedding vectors",
  search: "Searching matching roles",
  score: "LLM scoring",
  suspicion: "Suspicion analysis",
  save: "Saving results",
  llm: "Extracting fields",
  chunk: "Chunking JD",
  index: "Writing index",
  done: "Complete",
  llm_reassess: "Reassessing suspicion",
  update: "Updating records",
}

interface VizNode {
  text: string
  similarity?: number
}

interface JobViz {
  phase?: string
  tokens?: VizNode[]
  jd_nodes?: VizNode[]
}

function elapsedLabel(createdAt?: string): string {
  if (!createdAt) return ""
  const start = new Date(createdAt).getTime()
  const sec = Math.max(0, Math.floor((Date.now() - start) / 1000))
  if (sec < 60) return `${sec}s`
  return `${Math.floor(sec / 60)}m ${sec % 60}s`
}

function StepTimeline({ steps }: { steps: JobStep[] }) {
  return (
    <ol className="flex flex-wrap gap-1">
      {steps.map((s) => (
        <li
          key={s.id}
          className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] border ${
            s.status === "running"
              ? "border-primary bg-primary/10 text-primary animate-pulse"
              : s.status === "done"
                ? "border-green-500/30 text-green-600"
                : s.status === "failed"
                  ? "border-destructive/30 text-destructive"
                  : "border-muted text-muted-foreground"
          }`}
          title={s.label}
        >
          {s.status === "running" && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
          {s.status === "done" && <CheckCircle2 className="h-2.5 w-2.5" />}
          {s.status === "failed" && <XCircle className="h-2.5 w-2.5" />}
          {s.status === "pending" && <Circle className="h-2.5 w-2.5" />}
          <span className="truncate max-w-[72px]">{s.label}</span>
        </li>
      ))}
    </ol>
  )
}

function SimilarityBars({ jdNodes }: { jdNodes: VizNode[] }) {
  const data = jdNodes
    .filter((n) => typeof n.similarity === "number")
    .map((n) => ({
      name: n.text.length > 14 ? `${n.text.slice(0, 12)}…` : n.text,
      similarity: Math.round((n.similarity ?? 0) * 100),
    }))
    .slice(0, 5)

  if (!data.length) return null

  return (
    <div className="h-[100px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 4, right: 8, top: 4, bottom: 4 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 10 }} />
          <Bar dataKey="similarity" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} barSize={10} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function TokenChips({ tokens }: { tokens: VizNode[] }) {
  if (!tokens?.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {tokens.slice(0, 12).map((t) => (
        <Badge key={t.text} variant="secondary" className="text-[10px] px-1.5 py-0 font-normal">
          {t.text}
        </Badge>
      ))}
    </div>
  )
}

export default function AgentActivityTimeline({ job }: { job: ProcessingJob }) {
  const viz = (job.viz ?? {}) as JobViz
  const running = job.steps.find((s) => s.status === "running")
  const phase = running?.id ?? viz.phase ?? job.current_step ?? "receive"
  const caption = PHASE_LABEL[phase] ?? running?.label ?? "Processing"

  const jdNodes = useMemo(() => viz.jd_nodes ?? [], [viz.jd_nodes])
  const tokens = useMemo(() => viz.tokens ?? [], [viz.tokens])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
        <span className="truncate">{caption}</span>
        {job.created_at && <span className="shrink-0 tabular-nums">{elapsedLabel(job.created_at)}</span>}
      </div>
      <StepTimeline steps={job.steps} />
      {jdNodes.length > 0 && (phase === "search" || phase === "score") && (
        <SimilarityBars jdNodes={jdNodes} />
      )}
      {tokens.length > 0 && (phase === "embed" || phase === "normalize" || phase === "parse") && (
        <TokenChips tokens={tokens} />
      )}
    </div>
  )
}
