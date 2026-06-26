import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Loader2, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import {
  RoleRankingTable,
  RoleScoreComparisonChart,
} from "@/components/analytics/CandidateCharts"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import useCustomToast from "@/hooks/useCustomToast"
import { comparisonForJd, dedupeCandidates, flattenAnalyses, jdOptionsFromAnalyses } from "@/lib/analytics"
import { api } from "@/lib/api"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/results")({
  component: ResultsPage,
  head: () => ({ meta: [{ title: "Results — Recruiting Agent" }] }),
})

function scoreColor(score: number) {
  if (score >= 70) return "default"
  if (score >= 50) return "secondary"
  return "destructive"
}

function ResultsPage() {
  const [minScore, setMinScore] = useState(0)
  const [roleFilter, setRoleFilter] = useState("all")
  const qc = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: candidates, isLoading } = useQuery({
    queryKey: ["candidates", "analyzed"],
    queryFn: () => api.candidates("analyzed"),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteCandidate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidates"] })
      qc.invalidateQueries({ queryKey: ["hr-questions"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      showSuccessToast("Candidate deleted")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const deleteAllMut = useMutation({
    mutationFn: () => api.deleteAllCandidates(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["candidates"] })
      qc.invalidateQueries({ queryKey: ["hr-questions"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      showSuccessToast("All candidates cleared")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const allRows = flattenAnalyses(candidates ?? [])
  const jdOptions = jdOptionsFromAnalyses(candidates ?? [])
  const roleFilterId: number | "all" = roleFilter === "all" ? "all" : Number(roleFilter)
  const selectedJdLabel = jdOptions.find((j) => String(j.id) === roleFilter)?.label

  const filtered = useMemo(() => {
    const deduped = dedupeCandidates(candidates ?? [])
    return deduped.filter((c) => {
      const match = c.analyses.find((a) => roleFilter === "all" || String(a.jd_id) === roleFilter)
      if (!match || match.overall_score < minScore) return false
      return true
    })
  }, [candidates, roleFilter, minScore])

  const getDisplayAnalysis = (c: (typeof filtered)[0]) => {
    if (roleFilter === "all") return c.analyses[0]
    return c.analyses.find((a) => String(a.jd_id) === roleFilter) ?? c.analyses[0]
  }

  const confirmDelete = (name: string, id: number) => {
    if (window.confirm(`Permanently delete "${name}" and all analysis results?`)) {
      deleteMut.mutate(id)
    }
  }

  const confirmDeleteAll = () => {
    if (window.confirm("Delete ALL candidates and their analysis? This cannot be undone.")) {
      deleteAllMut.mutate()
    }
  }

  const hasAnalyses = allRows.length > 0
  const comparisonCount = comparisonForJd(allRows, roleFilterId, minScore).length

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analysis Results</h1>
          <p className="text-muted-foreground">Candidate scores, role comparison, and fit summaries</p>
        </div>
        {(candidates?.length ?? 0) > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="text-destructive border-destructive/30 hover:bg-destructive/10"
            disabled={deleteAllMut.isPending}
            onClick={confirmDeleteAll}
          >
            {deleteAllMut.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4 mr-2" />
            )}
            Clear all candidates
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-4 items-end">
        <div className="w-48">
          <p className="text-sm mb-2">Min score: {minScore}</p>
          <Slider value={[minScore]} onValueChange={([v]) => setMinScore(v)} max={100} step={5} />
        </div>
        <Select value={roleFilter} onValueChange={setRoleFilter}>
          <SelectTrigger className="w-72"><SelectValue placeholder="Filter by analyzed role" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All analyzed roles</SelectItem>
            {jdOptions.map((jd) => (
              <SelectItem key={jd.id} value={String(jd.id)}>{jd.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {hasAnalyses && comparisonCount > 0 && (
        <div className="grid gap-4 lg:grid-cols-1">
          <RoleScoreComparisonChart
            rows={allRows}
            jdId={roleFilterId}
            minScore={minScore}
            title={roleFilter === "all" ? "Score comparison — all roles" : `Score comparison — ${selectedJdLabel}`}
          />
          <RoleRankingTable rows={allRows} jdId={roleFilterId} minScore={minScore} />
        </div>
      )}

      {hasAnalyses && comparisonCount === 0 && roleFilter !== "all" && (
        <p className="text-sm text-amber-600 dark:text-amber-400 border border-amber-500/30 rounded-md p-3">
          No candidates were analyzed against <strong>{selectedJdLabel}</strong>. Switch to <strong>All analyzed roles</strong> or re-upload resumes targeting that JD.
        </p>
      )}

      <div className="space-y-4">
        {isLoading && <p className="text-muted-foreground">Loading…</p>}
        {filtered.map((c) => {
          const best = getDisplayAnalysis(c)
          if (!best) return null
          return (
            <Card key={c.id}>
              <CardContent className="pt-4">
                <div className="flex justify-between items-start mb-3 gap-3">
                  <div>
                    <p className="font-semibold text-lg">{c.name}</p>
                    <p className="text-sm text-muted-foreground">{c.email || "—"} · {c.parse_method}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={scoreColor(best.overall_score)} className="text-base px-3 py-1">
                      {Math.round(best.overall_score)}/100
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      disabled={deleteMut.isPending}
                      title="Delete candidate"
                      onClick={() => confirmDelete(c.name, c.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <p className="text-sm mb-3">{best.fit_summary}</p>
                {best.hr_verification_summary && (
                  <p className="text-sm mb-3 text-green-600 dark:text-green-400 border-l-2 border-green-500 pl-3">
                    HR verified: {best.hr_verification_summary}
                  </p>
                )}
                {(c.pending_hr_questions ?? 0) > 0 && (
                  <div className="mb-3 space-y-1">
                    <Badge variant="outline" className="text-amber-500 border-amber-500/40">
                      Verification pending ({c.pending_hr_questions})
                    </Badge>
                    {c.verification_summary && (
                      <p className="text-xs text-muted-foreground">{c.verification_summary}</p>
                    )}
                    {c.verification_category_counts && Object.keys(c.verification_category_counts).length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(c.verification_category_counts).map(([cat, n]) => (
                          <Badge key={cat} variant="outline" className="text-[10px] text-amber-600 border-amber-500/30">
                            {cat}: {n}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {best.suspicion_flags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {best.suspicion_flags.map((f) => <Badge key={f} variant="outline" className="text-orange-500 border-orange-500/30">{f}</Badge>)}
                  </div>
                )}
                {c.analyses.map((a) => (
                  <div key={a.id} className="border-t pt-3 mt-3 grid grid-cols-4 gap-2 text-sm">
                    <div><p className="text-muted-foreground">Role</p><p>{a.jd_role}</p></div>
                    <div><p className="text-muted-foreground">Technical</p><p className="font-medium">{Math.round(a.technical_score)}</p></div>
                    <div><p className="text-muted-foreground">HR Fit</p><p className="font-medium">{Math.round(a.hr_score)}</p></div>
                    <div><p className="text-muted-foreground">Suspicion</p><p className="font-medium">{Math.round(a.suspicion_score)}</p></div>
                  </div>
                ))}
                {best.suspicion_reasoning && (
                  <p className="text-xs text-muted-foreground mt-2 italic border-t pt-2">
                    Initial concern: {best.suspicion_reasoning}
                  </p>
                )}
              </CardContent>
            </Card>
          )
        })}
        {!isLoading && filtered.length === 0 && !hasAnalyses && (
          <p className="text-muted-foreground">No results yet. Upload resumes after creating a JD.</p>
        )}
        {!isLoading && filtered.length === 0 && hasAnalyses && (
          <p className="text-muted-foreground">No results match the current filters.</p>
        )}
      </div>
    </div>
  )
}
