import {
  BarChart3Icon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  LogOutIcon,
} from "lucide-react"
import { Link, Outlet, useNavigate } from "react-router"

import { useAuth, useLogout } from "@/api/auth"
import { paths, useDatasetId } from "@/app/paths"
import { useRouteTitle } from "@/app/route-title"
import { IconButton } from "@/components/common/icon-button"
import { DatasetSwitch } from "@/components/shell/dataset-switch"
import { NavItem } from "@/components/shell/nav-item"
import { ThemeSwitch } from "@/components/shell/theme-switch"
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

function Brand() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size="lg" asChild>
          <Link to={paths.datasets}>
            <LibraryIcon />
            <div className="flex flex-col leading-tight">
              <span className="font-semibold">СППР бібліотеки</span>
              <span className="text-xs text-muted-foreground">library-dss</span>
            </div>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function DatasetNav({ datasetId }: { datasetId: number | undefined }) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Датасет</SidebarGroupLabel>
      <SidebarGroupContent className="flex flex-col gap-2">
        <div className="px-2 group-data-[collapsible=icon]:hidden">
          <DatasetSwitch datasetId={datasetId} />
        </div>
        {datasetId !== undefined && (
          <SidebarMenu>
            <NavItem to={paths.dataset(datasetId)} icon={LayoutDashboardIcon} end>
              Огляд
            </NavItem>
            <NavItem to={paths.analytics(datasetId)} icon={BarChart3Icon}>
              Аналітика
            </NavItem>
            <NavItem to={paths.reports(datasetId)} icon={FileTextIcon}>
              Звіти
            </NavItem>
          </SidebarMenu>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

function AccountFooter() {
  const { analyst } = useAuth()
  const logout = useLogout()
  const navigate = useNavigate()
  // An explicit sign-out starts the next session from the dataset list, not from this page.
  // (mutateAsync: the shell unmounts as the session ends, which would drop a mutate callback.)
  async function signOut() {
    await logout.mutateAsync().catch(() => undefined)
    void navigate(paths.login, { replace: true })
  }
  return (
    <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col">
      <div className="min-w-0 flex-1 px-2 group-data-[collapsible=icon]:hidden">
        <p className="truncate text-sm font-medium">{analyst?.name ?? "…"}</p>
        <p className="truncate text-xs text-muted-foreground">{analyst?.email}</p>
      </div>
      <ThemeSwitch />
      <IconButton
        icon={LogOutIcon}
        label="Вийти"
        disabled={logout.isPending}
        onClick={() => void signOut()}
      />
    </div>
  )
}

/** The signed-in layout: sidebar navigation, a header with the page title, and the page. */
export function AppShell() {
  const datasetId = useDatasetId()
  const title = useRouteTitle()
  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <Brand />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Дані</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <NavItem to={paths.datasets} icon={DatabaseIcon}>
                  Датасети
                </NavItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <DatasetNav datasetId={datasetId} />
        </SidebarContent>
        <SidebarFooter>
          <AccountFooter />
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
