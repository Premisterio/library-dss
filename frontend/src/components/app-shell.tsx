import {
  BarChart3Icon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  LogOutIcon,
  MonitorIcon,
  MoonIcon,
  SunIcon,
} from "lucide-react"
import { Link, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useTheme } from "@/components/theme-provider"
import { useAuth } from "@/lib/auth"
import { useDatasets } from "@/lib/queries"

const THEMES = [
  { value: "light", icon: SunIcon, title: "Світла тема" },
  { value: "dark", icon: MoonIcon, title: "Темна тема" },
  { value: "system", icon: MonitorIcon, title: "Як у системі" },
] as const

function ThemeSwitch() {
  const { theme, setTheme } = useTheme()
  const index = THEMES.findIndex((t) => t.value === theme)
  const current = THEMES[index] ?? THEMES[2]
  const next = THEMES[(index + 1) % THEMES.length] ?? THEMES[0]
  const Icon = current.icon
  return (
    <Button
      variant="ghost"
      size="icon"
      title={`${current.title} (натисніть для: ${next.title.toLowerCase()})`}
      onClick={() => setTheme(next.value)}
    >
      <Icon />
    </Button>
  )
}

function DatasetSwitch({ datasetId }: { datasetId: number | undefined }) {
  const datasets = useDatasets()
  const navigate = useNavigate()
  const ready = (datasets.data ?? []).filter((d) => d.status === "ready")
  if (ready.length === 0) return null
  return (
    <Select
      value={datasetId ? String(datasetId) : undefined}
      onValueChange={(value) => void navigate(`/d/${value}`)}
    >
      <SelectTrigger className="w-full" aria-label="Датасет">
        <SelectValue placeholder="Оберіть датасет" />
      </SelectTrigger>
      <SelectContent>
        {ready.map((d) => (
          <SelectItem key={d.id} value={String(d.id)}>
            {d.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function NavItem({
  to,
  icon: Icon,
  children,
  end = false,
}: {
  to: string
  icon: typeof DatabaseIcon
  children: string
  end?: boolean
}) {
  const active = useMatch({ path: to, end }) !== null
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={children}>
        <Link to={to}>
          <Icon />
          <span>{children}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppShell() {
  const { analyst, logout } = useAuth()
  const params = useParams()
  const location = useLocation()
  const datasetId = params.datasetId ? Number(params.datasetId) : undefined
  const title = location.pathname.includes("/analytics")
    ? "Аналітика"
    : location.pathname.includes("/reports")
      ? "Звіти"
      : datasetId
        ? "Огляд"
        : "Датасети"

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild>
                <Link to="/datasets">
                  <LibraryIcon />
                  <div className="flex flex-col leading-tight">
                    <span className="font-semibold">СППР бібліотеки</span>
                    <span className="text-xs text-muted-foreground">library-dss</span>
                  </div>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Дані</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItem to="/datasets" icon={DatabaseIcon}>
                  Датасети
                </NavItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarGroup>
            <SidebarGroupLabel>Датасет</SidebarGroupLabel>
            <SidebarGroupContent className="flex flex-col gap-2">
              <div className="px-2 group-data-[collapsible=icon]:hidden">
                <DatasetSwitch datasetId={datasetId} />
              </div>
              {datasetId !== undefined && (
                <SidebarMenu>
                  <NavItem to={`/d/${datasetId}`} icon={LayoutDashboardIcon} end>
                    Огляд
                  </NavItem>
                  <NavItem to={`/d/${datasetId}/analytics`} icon={BarChart3Icon}>
                    Аналітика
                  </NavItem>
                  <NavItem to={`/d/${datasetId}/reports`} icon={FileTextIcon}>
                    Звіти
                  </NavItem>
                </SidebarMenu>
              )}
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col">
            <div className="min-w-0 flex-1 px-2 group-data-[collapsible=icon]:hidden">
              <p className="truncate text-sm font-medium">{analyst?.name ?? "…"}</p>
              <p className="truncate text-xs text-muted-foreground">{analyst?.email}</p>
            </div>
            <ThemeSwitch />
            <Button variant="ghost" size="icon" title="Вийти" onClick={() => void logout()}>
              <LogOutIcon />
            </Button>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <h1 className="text-sm font-medium">{title}</h1>
        </header>
        <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
