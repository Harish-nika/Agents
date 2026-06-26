import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  avgByRole,
  comparisonForJd,
  scoreDistribution,
  shortName,
  topCandidates,
  verificationGapTotals,
  type ScoreRow,
} from "@/lib/analytics"
import type { Candidate } from "@/lib/api"

const SCORE_COLORS = ["hsl(var(--destructive))", "hsl(var(--muted-foreground))", "hsl(142 76% 36%)", "hsl(var(--primary))"]
const BAR_COLORS = ["hsl(var(--primary))", "hsl(142 76% 36%)", "hsl(217 91% 60%)"]

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-muted-foreground">{p.name}: <span className="text-foreground font-medium">{p.value}</span></p>
      ))}
    </div>
  )
}

export function ScoreDistributionChart({ rows }: { rows: ScoreRow[] }) {
  const data = scoreDistribution(rows)
  if (!rows.length) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Score distribution</CardTitle>
      </CardHeader>
      <CardContent className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={24} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="count" name="Candidates" radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={SCORE_COLORS[i % SCORE_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function AvgScoreByRoleChart({ rows }: { rows: ScoreRow[] }) {
  const data = avgByRole(rows)
  if (!data.length) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Average score by role</CardTitle>
      </CardHeader>
      <CardContent className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 16, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="role" width={100} tick={{ fontSize: 10 }} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="overall" name="Avg overall" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} barSize={14} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function VerificationGapsChart({ candidates }: { candidates: Candidate[] }) {
  const data = verificationGapTotals(candidates)
  if (!data.length) return null
  const colors = ["#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#64748b"]
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Verification gaps by category</CardTitle>
      </CardHeader>
      <CardContent className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="category" cx="50%" cy="50%" outerRadius={72} label={({ category, count }) => `${category} (${count})`} labelLine={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function TopCandidatesChart({ rows }: { rows: ScoreRow[] }) {
  const data = topCandidates(rows, 6).map((r) => ({
    name: shortName(r.name),
    overall: Math.round(r.overall),
    role: r.jdRole,
  }))
  if (!data.length) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Top candidates</CardTitle>
      </CardHeader>
      <CardContent className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={28} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="overall" name="Overall" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function RoleScoreComparisonChart({
  rows,
  jdId,
  minScore = 0,
  title,
}: {
  rows: ScoreRow[]
  jdId: number | "all"
  minScore?: number
  title?: string
}) {
  const data = comparisonForJd(rows, jdId, minScore).map((r) => ({
    name: shortName(r.name),
    overall: Math.round(r.overall),
    technical: Math.round(r.technical),
    hr: Math.round(r.hr),
    suspicion: Math.round(r.suspicion),
  }))
  if (!data.length) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title ?? "Candidate score comparison"}</CardTitle>
        <p className="text-xs text-muted-foreground">Overall · Technical · HR fit — sorted by overall score</p>
      </CardHeader>
      <CardContent className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={28} />
            <Tooltip content={<ChartTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="overall" name="Overall" fill={BAR_COLORS[0]} radius={[2, 2, 0, 0]} />
            <Bar dataKey="technical" name="Technical" fill={BAR_COLORS[1]} radius={[2, 2, 0, 0]} />
            <Bar dataKey="hr" name="HR fit" fill={BAR_COLORS[2]} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function RoleRankingTable({ rows, jdId, minScore = 0 }: { rows: ScoreRow[]; jdId: number | "all"; minScore?: number }) {
  const ranked = comparisonForJd(rows, jdId, minScore)
  if (!ranked.length) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Ranking</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b">
                <th className="pb-2 pr-4 font-medium">#</th>
                <th className="pb-2 pr-4 font-medium">Candidate</th>
                <th className="pb-2 pr-4 font-medium">Role</th>
                <th className="pb-2 pr-4 font-medium text-right">Overall</th>
                <th className="pb-2 pr-4 font-medium text-right">Tech</th>
                <th className="pb-2 pr-4 font-medium text-right">HR</th>
                <th className="pb-2 font-medium text-right">Suspicion</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r, i) => (
                <tr key={`${r.candidateId}-${r.jdId}`} className="border-b border-muted/50 last:border-0">
                  <td className="py-2 pr-4 text-muted-foreground">{i + 1}</td>
                  <td className="py-2 pr-4 font-medium">{r.name}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{r.jdRole}</td>
                  <td className="py-2 pr-4 text-right font-semibold text-primary">{Math.round(r.overall)}</td>
                  <td className="py-2 pr-4 text-right">{Math.round(r.technical)}</td>
                  <td className="py-2 pr-4 text-right">{Math.round(r.hr)}</td>
                  <td className="py-2 text-right">{Math.round(r.suspicion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
