import { Link } from "@tanstack/react-router"
import { cn } from "@/lib/utils"

interface LogoProps {
  className?: string
  asLink?: boolean
}

export function Logo({ className, asLink = true }: LogoProps) {
  const content = (
    <div className={cn("font-bold text-xl tracking-tight", className)}>
      <span className="text-primary">Recruiting</span> Agent
    </div>
  )
  return asLink ? <Link to="/">{content}</Link> : content
}
