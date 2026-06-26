import { FaGithub, FaLinkedinIn } from "react-icons/fa"
import { FaXTwitter } from "react-icons/fa6"

const socialLinks = [
  { icon: FaGithub, href: "https://github.com/Harish-nika", label: "GitHub" },
  {
    icon: FaLinkedinIn,
    href: "https://www.linkedin.com/in/harish-kumar-s-b0a0472b1/",
    label: "LinkedIn",
  },
  {
    icon: FaXTwitter,
    href: "https://harish-nika.github.io/",
    label: "Portfolio",
  },
]

export function Footer() {
  const currentYear = new Date().getFullYear()
  const appVersion = import.meta.env.VITE_APP_VERSION || "dev"

  return (
    <footer className="border-t py-4 px-6">
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <p className="text-muted-foreground text-sm">
          Data Mining Engine - {appVersion} - {currentYear}
        </p>
        <div className="flex items-center gap-4">
          {socialLinks.map(({ icon: Icon, href, label }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <Icon className="h-5 w-5" />
            </a>
          ))}
        </div>
      </div>
    </footer>
  )
}
