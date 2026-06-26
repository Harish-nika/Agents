import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { KeyRound, Zap } from "lucide-react"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import {
  api,
  getGroqLlmMode,
  setGroqLlmMode,
  setGroqSessionKey,
  type GroqLlmMode,
} from "@/lib/api"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/settings")({
  component: SettingsPage,
  head: () => ({ meta: [{ title: "Settings — Recruiting agent RA1" }] }),
})

function modeLabel(mode: GroqLlmMode, hasSaved: boolean) {
  if (mode === "ollama") return "Ollama (local)"
  if (mode === "session") return "Groq — different key (this browser)"
  if (hasSaved) return "Groq — your saved key"
  return "Groq — no saved key yet"
}

function SettingsPage() {
  const qc = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [draftKey, setDraftKey] = useState("")
  const [mode, setMode] = useState<GroqLlmMode>(() => getGroqLlmMode())
  const [showChoice, setShowChoice] = useState(false)

  const { data: saved } = useQuery({
    queryKey: ["groq-settings"],
    queryFn: api.groqSettings,
  })

  const saveServerMut = useMutation({
    mutationFn: (key: string) => api.saveGroqKey(key),
    onSuccess: () => {
      setGroqLlmMode("saved")
      setMode("saved")
      setGroqSessionKey("")
      setDraftKey("")
      setShowChoice(false)
      qc.invalidateQueries({ queryKey: ["groq-settings"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      showSuccessToast("Groq key saved on server for your account")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const deleteMut = useMutation({
    mutationFn: api.deleteGroqKey,
    onSuccess: () => {
      setGroqLlmMode("ollama")
      setMode("ollama")
      setGroqSessionKey("")
      setDraftKey("")
      qc.invalidateQueries({ queryKey: ["groq-settings"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      showSuccessToast("Saved key removed — using Ollama")
    },
    onError: handleError.bind(null, showErrorToast),
  })

  const applySessionKey = () => {
    const key = draftKey.trim()
    if (!key) return
    setGroqSessionKey(key)
    setGroqLlmMode("session")
    setMode("session")
    setDraftKey("")
    setShowChoice(false)
    qc.invalidateQueries({ queryKey: ["dashboard"] })
    showSuccessToast("Using different Groq key for this browser only (not saved)")
  }

  const useSaved = () => {
    if (!saved?.has_saved_key) return
    setGroqLlmMode("saved")
    setMode("saved")
    setGroqSessionKey("")
    setDraftKey("")
    qc.invalidateQueries({ queryKey: ["dashboard"] })
    showSuccessToast("Using your saved Groq key")
  }

  const useOllama = () => {
    setGroqLlmMode("ollama")
    setMode("ollama")
    setGroqSessionKey("")
    setDraftKey("")
    setShowChoice(false)
    qc.invalidateQueries({ queryKey: ["dashboard"] })
    showSuccessToast("Using local Ollama for LLM tasks")
  }

  const onContinue = () => {
    if (!draftKey.trim()) {
      showErrorToast("Paste a Groq API key first")
      return
    }
    setShowChoice(true)
  }

  return (
    <div className="flex flex-col gap-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Groq for speed when Ollama is slow</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Zap className="h-5 w-5 text-primary" />
            LLM provider
          </CardTitle>
          <CardDescription>
            Each person can save their own Groq key on the server, or use a different key temporarily.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Active:</span>
            <Badge variant={mode === "ollama" ? "secondary" : "default"}>
              {modeLabel(mode, !!saved?.has_saved_key)}
            </Badge>
          </div>

          {saved?.has_saved_key && (
            <div className="rounded-lg border bg-muted/40 p-3 flex items-start gap-3">
              <KeyRound className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
              <div className="text-sm space-y-1">
                <p className="font-medium">Saved key on server</p>
                <p className="font-mono text-muted-foreground">{saved.key_mask}</p>
                <p className="text-xs text-muted-foreground">
                  Linked to your login — works on any browser after you choose &quot;Use saved key&quot;.
                </p>
              </div>
            </div>
          )}

          <div>
            <Label htmlFor="groq-key">Groq API key</Label>
            <Textarea
              id="groq-key"
              rows={3}
              className="mt-1.5 font-mono text-sm"
              placeholder="gsk_... (paste a new or different key)"
              value={draftKey}
              onChange={(e) => {
                setDraftKey(e.target.value)
                setShowChoice(false)
              }}
            />
            <p className="text-xs text-muted-foreground mt-2">
              Free key at{" "}
              <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer" className="text-primary underline">
                console.groq.com
              </a>
              . Embeddings still use local Ollama.
            </p>
          </div>

          {!showChoice ? (
            <div className="flex flex-wrap gap-2">
              <Button onClick={onContinue} disabled={!draftKey.trim()}>
                Continue with this key…
              </Button>
              {saved?.has_saved_key && mode !== "saved" && (
                <Button variant="outline" onClick={useSaved}>
                  Use my saved key
                </Button>
              )}
              {mode !== "ollama" && (
                <Button variant="outline" onClick={useOllama}>
                  Use Ollama instead
                </Button>
              )}
              {saved?.has_saved_key && (
                <Button variant="ghost" onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}>
                  Remove saved key
                </Button>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
              <p className="text-sm font-medium">How should we use this key?</p>
              <div className="flex flex-col sm:flex-row flex-wrap gap-2">
                <Button
                  onClick={() => saveServerMut.mutate(draftKey.trim())}
                  disabled={saveServerMut.isPending}
                >
                  Save on server (remember me)
                </Button>
                <Button variant="outline" onClick={applySessionKey}>
                  Use once — different key, don&apos;t save
                </Button>
                <Button variant="ghost" onClick={() => setShowChoice(false)}>
                  Cancel
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                <strong>Save on server</strong> — stored for your account, reused on any device after login.
                <br />
                <strong>Use once</strong> — only this browser, until you clear it or pick another option.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
