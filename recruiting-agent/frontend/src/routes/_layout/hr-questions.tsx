import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Loader2 } from "lucide-react"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import useAgentJobs from "@/hooks/useAgentJobs"
import useCustomToast from "@/hooks/useCustomToast"
import { api, type HRCandidateGroup, type HRQuestion } from "@/lib/api"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/hr-questions")({
  component: HRQuestionsPage,
  head: () => ({ meta: [{ title: "HR Questions — Recruiting Agent" }] }),
})

const CATEGORY_ORDER = ["education", "experience", "project", "timeline", "credential", "general"] as const
const CATEGORY_LABELS: Record<string, string> = {
  education: "Education",
  experience: "Experience",
  project: "Projects",
  timeline: "Timeline",
  credential: "Credentials",
  general: "Other",
}

function groupByCategory(questions: HRQuestion[]): Record<string, HRQuestion[]> {
  const groups: Record<string, HRQuestion[]> = {}
  for (const q of questions) {
    const cat = q.category || "general"
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(q)
  }
  return groups
}

function QuestionRow({
  q,
  answers,
  setAnswers,
  saveMut,
  qc,
}: {
  q: HRQuestion
  answers: Record<number, string>
  setAnswers: React.Dispatch<React.SetStateAction<Record<number, string>>>
  saveMut: { mutate: (v: { id: number; hr_answer: string }) => void; isPending: boolean }
  qc: ReturnType<typeof useQueryClient>
}) {
  return (
    <div className="rounded-lg border p-4 space-y-2">
      <div className="flex justify-between items-start gap-2">
        <p className="font-medium text-sm">{q.question}</p>
        <Badge
          variant={
            q.status === "resolved" ? "default"
              : q.status === "answered" ? "secondary"
                : q.status === "dismissed" ? "outline" : "secondary"
          }
        >
          {q.status}
        </Badge>
      </div>
      {q.resume_excerpt && (
        <blockquote className="text-xs text-muted-foreground border-l-2 pl-2 italic">
          &ldquo;{q.resume_excerpt}&rdquo;
        </blockquote>
      )}
      <div>
        <Label className="text-xs text-muted-foreground">HR verification notes</Label>
        <Textarea
          rows={3}
          placeholder="What did the candidate say? What did you verify (docs, references, call notes)?"
          value={answers[q.id] ?? ""}
          onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
          onBlur={() => {
            const val = (answers[q.id] ?? "").trim()
            if (val !== (q.hr_answer || "").trim()) {
              saveMut.mutate({ id: q.id, hr_answer: val })
            }
          }}
        />
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={saveMut.isPending}
          onClick={() => saveMut.mutate({ id: q.id, hr_answer: (answers[q.id] ?? "").trim() })}
        >
          Save answer
        </Button>
        {q.status !== "dismissed" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => api.updateQuestion(q.id, { status: "dismissed" }).then(() => qc.invalidateQueries({ queryKey: ["hr-questions"] }))}
          >
            Dismiss
          </Button>
        )}
      </div>
    </div>
  )
}

function CandidateGroupCard({ group }: { group: HRCandidateGroup }) {
  const qc = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { trackJob, jobs } = useAgentJobs()
  const [answers, setAnswers] = useState<Record<number, string>>(() =>
    Object.fromEntries(group.questions.map((q) => [q.id, q.hr_answer || ""])),
  )

  const saveMut = useMutation({
    mutationFn: ({ id, hr_answer }: { id: number; hr_answer: string }) =>
      api.updateQuestion(id, { hr_answer }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr-questions"] })
      showSuccessToast("Answer saved")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const reassessMut = useMutation({
    mutationFn: () => api.reassessSuspicion(group.candidate_id),
    onSuccess: ({ job_id }) => {
      trackJob(job_id, (job) => {
        if (job.status === "completed") {
          showSuccessToast("Suspicion reassessed — check Analysis Results")
          qc.invalidateQueries({ queryKey: ["candidates"] })
          qc.invalidateQueries({ queryKey: ["hr-questions"] })
        } else if (job.status === "failed") {
          showErrorToast(job.error || "Reassessment failed")
        }
      })
      showSuccessToast("Reassessment started — see Agent Activity panel")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const reassessRunning = jobs.some(
    (j) =>
      j.job_type === "hr_reassess" &&
      j.candidate_id === group.candidate_id &&
      (j.status === "pending" || j.status === "running"),
  )

  const hasAnswers = Object.values(answers).some((a) => a.trim().length > 0)
  const openCount = group.questions.filter((q) => q.status === "pending").length
  const byCategory = groupByCategory(group.questions)
  const counts = group.verification_category_counts ?? {}

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start gap-4">
          <div>
            <CardTitle className="text-lg">{group.candidate_name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {group.jd_title} · Suspicion {Math.round(group.suspicion_score)}/100
              {openCount > 0 && ` · ${openCount} open`}
            </p>
          </div>
          <Link to="/results">
            <Button variant="outline" size="sm">View results</Button>
          </Link>
        </div>
        {group.verification_summary && (
          <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-sm font-medium text-amber-700 dark:text-amber-400">Pending verification</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {Object.entries(counts).map(([cat, n]) => (
                <Badge key={cat} variant="outline" className="text-amber-600 border-amber-500/40">
                  {CATEGORY_LABELS[cat] ?? cat}: {n}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {group.suspicion_flags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {group.suspicion_flags.map((f) => (
              <Badge key={f} variant="outline" className="text-orange-500 border-orange-500/30">{f}</Badge>
            ))}
          </div>
        )}
        {group.suspicion_reasoning && (
          <p className="text-sm text-muted-foreground mt-2 italic">{group.suspicion_reasoning}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        {CATEGORY_ORDER.filter((cat) => byCategory[cat]?.length).map((cat) => (
          <div key={cat}>
            <h3 className="text-sm font-semibold mb-3">{CATEGORY_LABELS[cat]}</h3>
            <div className="space-y-4">
              {byCategory[cat].map((q) => (
                <QuestionRow
                  key={q.id}
                  q={q}
                  answers={answers}
                  setAnswers={setAnswers}
                  saveMut={saveMut}
                  qc={qc}
                />
              ))}
            </div>
          </div>
        ))}

        <Button
          className="w-full sm:w-auto"
          disabled={!hasAnswers || reassessMut.isPending || reassessRunning}
          onClick={() => reassessMut.mutate()}
        >
          {reassessMut.isPending || reassessRunning ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Reassessing…
            </>
          ) : (
            "Reassess with HR input"
          )}
        </Button>
      </CardContent>
    </Card>
  )
}

function HRQuestionsPage() {
  const { data: groups, isLoading } = useQuery({
    queryKey: ["hr-questions", "grouped"],
    queryFn: api.hrQuestionsGrouped,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">HR Questions</h1>
        <p className="text-muted-foreground">
          Verification questions grouped by education, experience, projects, and timeline gaps.
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}

      <div className="space-y-6">
        {groups?.map((g) => <CandidateGroupCard key={g.candidate_id} group={g} />)}
        {!isLoading && !groups?.length && (
          <p className="text-muted-foreground">No HR questions yet. They appear when verification gaps or suspicion flags are found.</p>
        )}
      </div>
    </div>
  )
}
