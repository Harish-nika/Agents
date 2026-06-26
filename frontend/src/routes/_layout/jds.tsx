import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useAgentJobs from "@/hooks/useAgentJobs"
import useCustomToast from "@/hooks/useCustomToast"
import { api, type JD, type JDInput, type JDParsed } from "@/lib/api"
import { handleError } from "@/utils"

const SENIORITY = ["Junior", "Mid", "Senior", "Lead", "Manager"]

export const Route = createFileRoute("/_layout/jds")({
  component: JDsPage,
  head: () => ({ meta: [{ title: "JDs — Recruiting agent RA1" }] }),
})

function JDsPage() {
  const qc = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { trackJob, jobs } = useAgentJobs()
  const { data: jds } = useQuery({ queryKey: ["jds"], queryFn: () => api.jds(false) })
  const [editing, setEditing] = useState<number | "new" | null>(null)
  const [activeTab, setActiveTab] = useState("paste")
  const [rawPaste, setRawPaste] = useState("")
  const [parseSeconds, setParseSeconds] = useState(0)
  const [form, setForm] = useState<JDInput>({
    title: "", role: "", department: "", seniority: "Mid", content: "", skills: [],
  })

  const parseMut = useMutation({
    mutationFn: () => api.parseJdAsync(rawPaste),
    onSuccess: ({ job_id }) => {
      trackJob(job_id, (job) => {
        if (job.status === "completed" && job.result) {
          const p = job.result as unknown as JDParsed
          setForm({
            title: p.title || "",
            role: p.role || "",
            department: p.department || "",
            seniority: SENIORITY.includes(p.seniority) ? p.seniority : "Mid",
            content: p.content || "",
            skills: p.skills || [],
          })
          setActiveTab("form")
          showSuccessToast("JD parsed — review fields and save")
        } else if (job.status === "failed") {
          showErrorToast(job.error || "JD parse failed")
        }
      })
      showSuccessToast("Parsing started — see Agent Activity panel →")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const jdParseRunning = jobs.some(
    (j) => j.job_type === "jd_parse" && (j.status === "pending" || j.status === "running"),
  )
  const parsePending = parseMut.isPending || jdParseRunning
  const appliedParseJobs = useRef<Set<number>>(new Set())

  useEffect(() => {
    if (editing === null) return
    for (const job of jobs) {
      if (job.job_type !== "jd_parse" || job.status !== "completed" || !job.result) continue
      if (appliedParseJobs.current.has(job.id)) continue
      appliedParseJobs.current.add(job.id)
      const p = job.result as unknown as JDParsed
      setForm({
        title: p.title || "",
        role: p.role || "",
        department: p.department || "",
        seniority: SENIORITY.includes(p.seniority) ? p.seniority : "Mid",
        content: p.content || "",
        skills: p.skills || [],
      })
      setActiveTab("form")
      showSuccessToast("JD parsed — review fields and save")
    }
  }, [jobs, editing, showSuccessToast])

  useEffect(() => {
    if (!parsePending) {
      setParseSeconds(0)
      return
    }
    const t = setInterval(() => setParseSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [parsePending])

  const saveMut = useMutation({
    mutationFn: () =>
      editing && editing !== "new" ? api.updateJd(editing, form) : api.createJd(form),
    onSuccess: async (jd) => {
      qc.invalidateQueries({ queryKey: ["jds"] })
      setEditing(null)
      setRawPaste("")
      try {
        const { job_id } = await api.indexJdAsync(jd.id)
        trackJob(job_id)
      } catch {
        /* indexing viz is best-effort */
      }
      showSuccessToast("JD saved — see vector indexing in Agent Activity →")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteJd(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["jds"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      qc.invalidateQueries({ queryKey: ["candidates"] })
      if (editing === id) setEditing(null)
      showSuccessToast("Job description deleted")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const confirmDelete = (jd: JD) => {
    const msg = jd.is_active
      ? `Permanently delete "${jd.role}"? This removes the role and any candidate scores against it.`
      : `Permanently delete archived role "${jd.role}"?`
    if (window.confirm(msg)) deleteMut.mutate(jd.id)
  }

  const openNew = () => {
    setEditing("new")
    setActiveTab("paste")
    setRawPaste("")
    setForm({ title: "", role: "", department: "", seniority: "Mid", content: "", skills: [] })
  }

  const openEdit = (jd: JD) => {
    setForm({
      title: jd.title,
      role: jd.role,
      department: jd.department,
      seniority: jd.seniority,
      content: jd.content,
      skills: jd.skills,
    })
    setEditing(jd.id)
    setActiveTab("form")
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold">Job Descriptions</h1>
          <p className="text-muted-foreground">Paste a JD and let AI extract role, skills & requirements</p>
        </div>
        <Button onClick={openNew}>New Role</Button>
      </div>

      {editing !== null && (
        <Card>
          <CardHeader>
            <CardTitle>{editing === "new" ? "Create Role" : "Edit Role"}</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList>
                <TabsTrigger value="paste">Paste & AI Parse</TabsTrigger>
                <TabsTrigger value="form">Review & Save</TabsTrigger>
              </TabsList>

              <TabsContent value="paste" className="space-y-4 mt-4">
                <Textarea
                  placeholder="Paste full job description here…"
                  rows={14}
                  value={rawPaste}
                  onChange={(e) => setRawPaste(e.target.value)}
                  disabled={parsePending}
                />
                {parsePending && (
                  <div className="flex items-start gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-primary shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">AI is parsing your job description…</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        This uses local Ollama and typically takes <strong>1–3 minutes</strong>.
                        Elapsed: {parseSeconds}s — you can switch tabs; parsing continues in background.
                      </p>
                    </div>
                  </div>
                )}
                <Button
                  onClick={() => parseMut.mutate()}
                  disabled={parsePending || !rawPaste.trim()}
                >
                  {parsePending ? `Parsing… (${parseSeconds}s)` : "Parse with AI"}
                </Button>
              </TabsContent>

              <TabsContent value="form" className="space-y-4 mt-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label>Role *</Label>
                    <Input value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} />
                  </div>
                  <div>
                    <Label>Job Title *</Label>
                    <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                  </div>
                  <div>
                    <Label>Department</Label>
                    <Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
                  </div>
                  <div>
                    <Label>Seniority</Label>
                    <Select value={form.seniority} onValueChange={(v) => setForm({ ...form, seniority: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {SENIORITY.map((s) => (
                          <SelectItem key={s} value={s}>{s}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label>Skills (comma-separated)</Label>
                  <Input
                    value={form.skills.join(", ")}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        skills: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                      })
                    }
                  />
                </div>
                <div>
                  <Label>Job Description *</Label>
                  <Textarea rows={12} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} />
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !form.role || !form.title || !form.content}>
                    {saveMut.isPending ? "Saving…" : "Save & Re-index"}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {jds?.map((jd) => (
          <Card key={jd.id}>
            <CardContent className="pt-4 flex justify-between items-start gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-semibold">{jd.role}</p>
                  <Badge variant={jd.is_active ? "default" : "secondary"}>
                    {jd.is_active ? "Active" : "Archived"}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {jd.title} · {jd.department || "No dept"} · {jd.seniority}
                </p>
                <p className="text-sm mt-1 text-muted-foreground">{jd.skills.join(", ")}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                {jd.is_active && (
                  <Button size="sm" variant="outline" onClick={() => openEdit(jd)}>Edit</Button>
                )}
                {jd.is_active ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => api.archiveJd(jd.id).then(() => qc.invalidateQueries({ queryKey: ["jds"] }))}
                  >
                    Archive
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => api.restoreJd(jd.id).then(() => qc.invalidateQueries({ queryKey: ["jds"] }))}
                  >
                    Restore
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={deleteMut.isPending}
                  onClick={() => confirmDelete(jd)}
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
