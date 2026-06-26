import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { FileText, Loader2, Upload } from "lucide-react"
import { useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import useAgentJobs from "@/hooks/useAgentJobs"
import useCustomToast from "@/hooks/useCustomToast"
import { api, getGroqLlmMode } from "@/lib/api"
import { handleError } from "@/utils"

const ACCEPT = ".pdf,.docx,.txt,.jpg,.jpeg,.png,.tiff,.bmp,.webp"
const FORMATS = ["PDF", "Word (.docx)", "TXT", "JPG/PNG scans"]

export const Route = createFileRoute("/_layout/upload")({
  component: UploadPage,
  head: () => ({ meta: [{ title: "Upload — Recruiting Agent" }] }),
})

function UploadPage() {
  const qc = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { trackJob, jobs } = useAgentJobs()
  const fileRef = useRef<HTMLInputElement>(null)
  const [targetJd, setTargetJd] = useState<string>("all")
  const [log, setLog] = useState<string[]>([])
  const [queued, setQueued] = useState(0)
  const { data: jds } = useQuery({ queryKey: ["jds", "active"], queryFn: () => api.jds(true) })
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30000 })
  const { data: groqSaved } = useQuery({ queryKey: ["groq-settings"], queryFn: api.groqSettings })
  const llmMode = getGroqLlmMode()
  const usingOllamaDespiteSavedKey = llmMode === "ollama" && groqSaved?.has_saved_key

  const resumeJobs = jobs.filter((j) => j.job_type === "resume_analysis")
  const running = resumeJobs.filter((j) => j.status === "pending" || j.status === "running")
  const isBusy = queued > 0 || running.length > 0

  const uploadMut = useMutation({
    mutationFn: async (files: FileList) => {
      const results: string[] = []
      const jdId = targetJd === "all" ? undefined : Number(targetJd)
      const list = Array.from(files)
      setQueued(list.length)
      for (let i = 0; i < list.length; i++) {
        const file = list[i]
        try {
          const { job_id } = await api.uploadResumeAsync(file, jdId)
          trackJob(job_id, (job) => {
            if (job.status === "completed" && job.result) {
              const name = String(job.result.name || file.name)
              const status = String(job.result.status || "done")
              setLog((prev) => [...prev, `✅ ${file.name} → ${name} [${status}]`])
            } else if (job.status === "failed" || job.status === "cancelled") {
              setLog((prev) => [...prev, `❌ ${file.name} → ${job.error || job.status}`])
            }
            qc.invalidateQueries({ queryKey: ["candidates"] })
            qc.invalidateQueries({ queryKey: ["dashboard"] })
          })
          results.push(`⏳ ${file.name} — queued (job #${job_id})`)
        } catch (e) {
          results.push(`❌ ${file.name} → ${e instanceof Error ? e.message : "failed"}`)
        }
        setQueued(list.length - i - 1)
      }
      return results
    },
    onSuccess: (results) => {
      setLog((prev) => [...results, ...prev])
      showSuccessToast("Analysis started — see Agent Activity panel →")
      if (fileRef.current) fileRef.current.value = ""
    },
    onError: handleError.bind(null, showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Upload Resumes</h1>
        <p className="text-muted-foreground">
          HR can upload single or multiple resumes. Digital PDFs, Word documents, and scanned files are supported.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">LLM:</span>
          <Badge variant={health?.using_groq ? "default" : "secondary"}>
            {health?.using_groq ? "Groq (fast)" : "Ollama (slow)"}
          </Badge>
          <span className="text-muted-foreground">Embeddings:</span>
          <Badge variant="outline">Ollama CPU — always local</Badge>
          {usingOllamaDespiteSavedKey && (
            <span className="text-xs text-amber-500">
              Saved Groq key ignored — <Link to="/settings" className="underline">switch to saved key</Link>
            </span>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Supported formats
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 -mt-2">
          {FORMATS.map((f) => (
            <Badge key={f} variant="secondary">{f}</Badge>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 space-y-4">
          <div>
            <Label>Score against</Label>
            <Select value={targetJd} onValueChange={setTargetJd}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All active roles</SelectItem>
                {jds?.map((jd) => (
                  <SelectItem key={jd.id} value={String(jd.id)}>{jd.role} — {jd.title}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-lg border border-dashed p-6 text-center space-y-3">
            <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Select one or more resume files (PDF, Word .docx, TXT, or image scans)
            </p>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
            <p className="text-xs text-muted-foreground">
              Scanned PDFs and photos are read via OCR. Old .doc files: save as .docx or PDF first.
            </p>
          </div>

          {isBusy && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {running.length > 0
                ? `${running.length} resume${running.length > 1 ? "s" : ""} analyzing in background`
                : "Queuing files…"}
              <span className="text-xs">
                — Groq speeds LLM only; embeddings stay on Ollama (~5s). One resume at a time.
              </span>
            </div>
          )}

          <Button
            disabled={uploadMut.isPending}
            className="w-full sm:w-auto"
            onClick={() => fileRef.current?.files?.length && uploadMut.mutate(fileRef.current.files)}
          >
            {uploadMut.isPending || running.length > 0 ? "Analyzing…" : "Analyze Resumes"}
          </Button>
        </CardContent>
      </Card>

      {log.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Results</CardTitle></CardHeader>
          <CardContent className="space-y-1 font-mono text-sm">
            {log.map((l, i) => <p key={`${l}-${i}`}>{l}</p>)}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
