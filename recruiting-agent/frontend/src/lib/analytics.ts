import type { Analysis, Candidate } from "@/lib/api"

export interface ScoreRow {
  name: string
  candidateId: number
  jdId: number
  jdRole: string
  jdTitle: string
  overall: number
  technical: number
  hr: number
  suspicion: number
  pendingHr: number
}

export interface JdOption {
  id: number
  role: string
  title: string
  label: string
}

export function dedupeCandidates(candidates: Candidate[]): Candidate[] {
  return candidates.reduce<Candidate[]>((acc, c) => {
    const key = (c.email || c.name).toLowerCase()
    const prev = acc.find((x) => (x.email || x.name).toLowerCase() === key)
    if (!prev) {
      acc.push(c)
      return acc
    }
    const prevBest = prev.analyses[0]?.overall_score ?? 0
    const curBest = c.analyses[0]?.overall_score ?? 0
    if (curBest >= prevBest) {
      acc[acc.indexOf(prev)] = c
    }
    return acc
  }, [])
}

export function flattenAnalyses(candidates: Candidate[]): ScoreRow[] {
  const rows: ScoreRow[] = []
  for (const c of dedupeCandidates(candidates)) {
    for (const a of c.analyses) {
      rows.push({
        name: c.name,
        candidateId: c.id,
        jdId: a.jd_id,
        jdRole: a.jd_role,
        jdTitle: a.jd_title,
        overall: a.overall_score,
        technical: a.technical_score,
        hr: a.hr_score,
        suspicion: a.suspicion_score,
        pendingHr: c.pending_hr_questions ?? 0,
      })
    }
  }
  return rows
}

export function jdOptionsFromAnalyses(candidates: Candidate[]): JdOption[] {
  const seen = new Map<number, JdOption>()
  for (const row of flattenAnalyses(candidates)) {
    if (!seen.has(row.jdId)) {
      const label = row.jdTitle && row.jdTitle !== row.jdRole
        ? `${row.jdRole} — ${row.jdTitle}`
        : row.jdRole
      seen.set(row.jdId, { id: row.jdId, role: row.jdRole, title: row.jdTitle, label })
    }
  }
  return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label))
}

export function scoreDistribution(rows: ScoreRow[]): { bucket: string; count: number }[] {
  const buckets = [
    { bucket: "0–49", min: 0, max: 49 },
    { bucket: "50–69", min: 50, max: 69 },
    { bucket: "70–84", min: 70, max: 84 },
    { bucket: "85–100", min: 85, max: 100 },
  ]
  return buckets.map(({ bucket, min, max }) => ({
    bucket,
    count: rows.filter((r) => r.overall >= min && r.overall <= max).length,
  }))
}

export function avgByRole(rows: ScoreRow[]): { role: string; overall: number; count: number }[] {
  const map = new Map<string, { sum: number; count: number }>()
  for (const r of rows) {
    const key = r.jdRole || "Unknown"
    const cur = map.get(key) ?? { sum: 0, count: 0 }
    cur.sum += r.overall
    cur.count += 1
    map.set(key, cur)
  }
  return [...map.entries()]
    .map(([role, { sum, count }]) => ({
      role: role.length > 22 ? `${role.slice(0, 20)}…` : role,
      overall: Math.round(sum / count),
      count,
    }))
    .sort((a, b) => b.overall - a.overall)
}

export function verificationGapTotals(candidates: Candidate[]): { category: string; count: number }[] {
  const totals = new Map<string, number>()
  for (const c of dedupeCandidates(candidates)) {
    for (const [cat, n] of Object.entries(c.verification_category_counts ?? {})) {
      totals.set(cat, (totals.get(cat) ?? 0) + n)
    }
  }
  return [...totals.entries()]
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
}

export function topCandidates(rows: ScoreRow[], limit = 8): ScoreRow[] {
  return [...rows].sort((a, b) => b.overall - a.overall).slice(0, limit)
}

export function comparisonForJd(rows: ScoreRow[], jdId: number | "all", minScore = 0): ScoreRow[] {
  const filtered = jdId === "all" ? rows : rows.filter((r) => r.jdId === jdId)
  return filtered
    .filter((r) => r.overall >= minScore)
    .sort((a, b) => b.overall - a.overall)
}

export function bestFitByCandidate(candidates: import("@/lib/api").Candidate[]): Map<number, ScoreRow> {
  const map = new Map<number, ScoreRow>()
  for (const row of flattenAnalyses(candidates)) {
    const prev = map.get(row.candidateId)
    if (!prev || row.overall > prev.overall) map.set(row.candidateId, row)
  }
  return map
}

export function roleMatrix(
  candidates: import("@/lib/api").Candidate[],
): { candidate: string; [role: string]: string | number }[] {
  const rows = flattenAnalyses(candidates)
  const roles = [...new Set(rows.map((r) => r.jdRole))].sort()
  const byCandidate = new Map<number, { name: string; scores: Map<string, number> }>()
  for (const r of rows) {
    const cur = byCandidate.get(r.candidateId) ?? { name: shortName(r.name, 18), scores: new Map() }
    cur.scores.set(r.jdRole, Math.round(r.overall))
    byCandidate.set(r.candidateId, cur)
  }
  return [...byCandidate.values()].map(({ name, scores }) => {
    const row: { candidate: string; [key: string]: string | number } = { candidate: name }
    for (const role of roles) {
      row[role] = scores.get(role) ?? 0
    }
    return row
  })
}

export function shortName(name: string, max = 14): string {
  if (name.length <= max) return name
  const parts = name.split(" ")
  if (parts.length >= 2) return `${parts[0]} ${parts[parts.length - 1][0]}.`
  return `${name.slice(0, max - 1)}…`
}
