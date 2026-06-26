import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Briefcase, HelpCircle, TrendingUp, Users } from "lucide-react"
import {
  AvgScoreByRoleChart,
  RoleSuitabilityMatrix,
  ScoreDistributionChart,
  TopCandidatesChart,
  VerificationGapsChart,
} from "@/components/analytics/CandidateCharts"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { flattenAnalyses } from "@/lib/analytics"
import { api } from "@/lib/api"

export const Route = createFileRoute("/_layout/")({
  component: DashboardPage,
  head: () => ({ meta: [{ title: "Dashboard — Recruiting Agent" }] }),
})

function DashboardPage() {
  const { data: stats, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, refetchInterval: 30000 })
  const { data: candidates } = useQuery({ queryKey: ["candidates", "analyzed"], queryFn: () => api.candidates("analyzed") })

  const rows = flattenAnalyses(candidates ?? [])
  const analyzed = stats?.analyzed ?? 0

  if (isLoading) return <p className="text-muted-foreground">Loading…</p>

  const metrics = [
    { label: "Active JDs", value: stats?.active_jds ?? 0, icon: Briefcase },
    { label: "Candidates", value: stats?.candidates ?? 0, icon: Users },
    { label: "Analyzed", value: analyzed, icon: Users },
    { label: "Avg Score", value: `${Math.round(stats?.avg_score ?? 0)}`, icon: TrendingUp },
    { label: "HR Questions", value: stats?.pending_questions ?? 0, icon: HelpCircle },
  ]

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Pipeline health and score analytics</p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant={stats?.using_groq ? "default" : stats?.ollama_ok ? "secondary" : "destructive"}>
          LLM: {stats?.using_groq ? "Groq" : stats?.ollama_ok ? "Ollama" : "Offline"}
        </Badge>
        {stats?.using_groq && (
          <Badge variant={stats.groq_ok ? "default" : "destructive"}>
            Groq {stats.groq_ok ? "OK" : "Invalid key"}
          </Badge>
        )}
        {!stats?.using_groq && stats?.ollama_gpu && <Badge variant="outline">GPU Ollama</Badge>}
        {stats?.failed ? <Badge variant="secondary">{stats.failed} failed uploads</Badge> : null}
        {rows.length > 0 && (
          <Badge variant="outline">{rows.length} analysis{rows.length !== 1 ? "es" : ""} across roles</Badge>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {metrics.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent><div className="text-3xl font-bold">{value}</div></CardContent>
          </Card>
        ))}
      </div>

      {rows.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <ScoreDistributionChart rows={rows} />
          <TopCandidatesChart rows={rows} />
          <AvgScoreByRoleChart rows={rows} />
          {candidates && candidates.length > 0 && <RoleSuitabilityMatrix candidates={candidates} />}
          {candidates && candidates.length > 0 && <VerificationGapsChart candidates={candidates} />}
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">No analyses yet. Create a JD, index it, then upload resumes to see charts here.</p>
          </CardContent>
        </Card>
      )}

      <div>
        <h2 className="text-lg font-semibold mb-4">Recent Analyses</h2>
        {!candidates?.length ? (
          <p className="text-muted-foreground">No analyses yet. Upload resumes to get started.</p>
        ) : (
          <div className="space-y-3">
            {candidates.slice(0, 8).map((c) => {
              const best = c.analyses[0]
              if (!best) return null
              return (
                <Card key={c.id}>
                  <CardContent className="pt-4 flex justify-between items-start gap-4">
                    <div>
                      <p className="font-medium">{c.name}</p>
                      <p className="text-sm text-muted-foreground">{best.jd_title} · {best.recommended_role}</p>
                      <p className="text-sm mt-1 line-clamp-2">{best.fit_summary}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-2xl font-bold text-primary">{Math.round(best.overall_score)}</p>
                      <p className="text-xs text-muted-foreground">Tech {Math.round(best.technical_score)} · Suspicion {Math.round(best.suspicion_score)}</p>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
