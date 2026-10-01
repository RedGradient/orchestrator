import { Activity, PanelLeft, ServerCog } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"

import { cn } from "@/lib/utils"

const navigation = [
  { label: "Действия", href: "/", icon: PanelLeft, end: true },
  { label: "Проверка сайта", href: "/checks", icon: Activity, end: false },
] as const

export function AppShell() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/85">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-8 px-5 sm:px-8">
          <NavLink
            to="/"
            className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight"
            aria-label="Orchestrator — главная"
          >
            <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ServerCog aria-hidden="true" className="size-4.5" />
            </span>
            <span>Orchestrator</span>
          </NavLink>

          <nav className="flex min-w-0 items-center gap-1" aria-label="Основная навигация">
            {navigation.map(({ label, href, icon: Icon, end }) => (
              <NavLink
                key={href}
                to={href}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isActive && "bg-muted text-foreground",
                  )
                }
              >
                <Icon aria-hidden="true" className="size-4" />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto w-full max-w-[1440px] px-5 py-8 sm:px-8 lg:py-10">
        <Outlet />
      </div>
    </div>
  )
}
