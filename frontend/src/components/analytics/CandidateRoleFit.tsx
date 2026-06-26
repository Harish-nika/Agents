import type { Analysis } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

function fitLabel(score: number): { text: string; variant: "default" | "secondary" | "outline" | "destructive" } {
  if (score >= 85) return { text: "Strong fit", variant: "default" }
  if (score >= 70) return { text: "Good fit", variant: "secondary" }
  if (score >= 55) return { text: "Partial fit", variant: "outline" }
  return { text: "Weak fit", variant: "destructive" }
}

function roleLabel(a: Analysis): string {
  return a.jd_title && a.jd_title !== a.jd_role ? `${a.jd_role} — ${a.jd_title}` : a.jd_role
}

export default function CandidateRoleFit({ analyses }: { analyses: Analysis[] }) {
  if (!analyses.length) return null

  const sorted = [...analyses].sort((a, b) => b.overall_score - a.overall_score)
  const best = sorted[0]
  const multi = sorted.length > 1

  return (
    <div className="mb-4 rounded-lg border bg-muted/30 p-3 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">Role suitability</p>
        {multi && (
          <Badge variant="default" className="text-xs">
            Best fit: {roleLabel(best)} ({Math.round(best.overall_score)})
          </Badge>
        )}
      </div>

      {multi ? (
        <div className="space-y-2">
          {sorted.map((a) => {
            const isBest = a.id === best.id
            const fit = fitLabel(a.overall_score)
            const pct = Math.round(a.overall_score)
            return (
              <div key={a.id} className={`space-y-1 ${isBest ? "opacity-100" : "opacity-90"}`}>
                <div className="flex justify-between items-center gap-2 text-xs">
                  <span className={isBest ? "font-semibold" : "text-muted-foreground"}>
                    {roleLabel(a)}
                    {isBest && <span className="ml-1 text-primary">★</span>}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={fit.variant} className="text-[10px] px-1.5 py-0">{fit.text}</Badge>
                    <span className="font-medium tabular-nums w-8 text-right">{pct}</span>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${isBest ? "bg-primary" : "bg-primary/50"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-[11px] text-muted-foreground line-clamp-2">{a.fit_summary}</p>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-sm">
          <p className="text-muted-foreground">{roleLabel(best)}</p>
          <p className="text-xs mt-1 text-muted-foreground">
            Re-upload with &ldquo;Match all active roles&rdquo; to compare against every JD.
          </p>
        </div>
      )}
    </div>
  )
}
