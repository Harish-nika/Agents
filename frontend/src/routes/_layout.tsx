import { createFileRoute, Link, Outlet, redirect, useRouterState } from "@tanstack/react-router"
import { Briefcase, ClipboardList, HelpCircle, LayoutDashboard, LogOut, Settings, Upload } from "lucide-react"
import AgentNetworkPanel from "@/components/AgentNetworkPanel"
import { Button } from "@/components/ui/button"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jds", label: "Job Descriptions", icon: Briefcase },
  { to: "/upload", label: "Upload Resumes", icon: Upload },
  { to: "/results", label: "Analysis Results", icon: ClipboardList },
  { to: "/hr-questions", label: "HR Questions", icon: HelpCircle },
  { to: "/settings", label: "Settings", icon: Settings },
] as const

export const Route = createFileRoute("/_layout")({
  beforeLoad: () => { if (!isLoggedIn()) throw redirect({ to: "/login" }) },
  component: AppLayout,
  head: () => ({ meta: [{ title: "Recruiting Agent" }] }),
})

function AppLayout() {
  const { logout, user } = useAuth()
  const { location } = useRouterState()

  return (
    <div className="flex min-h-svh bg-background">
      <aside className="w-64 border-r bg-card flex flex-col shrink-0">
        <div className="p-5 border-b">
          <h1 className="font-bold text-lg leading-tight">Recruiting Agent</h1>
          <p className="text-xs text-muted-foreground">Recruiting Agent</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = location.pathname === to
            return (
              <Link key={to} to={to} className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${active ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
                <Icon className="h-4 w-4" />{label}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t">
          <p className="text-xs text-muted-foreground mb-2 px-1">{user?.username}</p>
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />Logout
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto min-w-0">
        <div className="p-8 max-w-5xl mx-auto">
          <Outlet />
        </div>
      </main>
      <AgentNetworkPanel />
    </div>
  )
}
