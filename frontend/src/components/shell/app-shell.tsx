import {
  BarChart3Icon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  UserMinusIcon,
} from "lucide-react"
import { Link, Outlet } from "react-router"

import { paths, useDatasetId } from "@/app/paths"
import { useRouteTitle } from "@/app/route-title"
import { GlassToolbar, ToolbarProvider } from "@/components/glass/toolbar"
import { AccountMenu } from "@/components/shell/account-menu"
import { DatasetSwitch } from "@/components/shell/dataset-switch"
import { NavItem } from "@/components/shell/nav-item"
import {
  Sidebar,
  SidebarContent,
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
            <span className="flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-primary text-primary-foreground">
              <LibraryIcon className="size-4" />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="font-semibold">СППР бібліотеки</span>
              <span className="text-xs text-muted-foreground">Аналітика й рішення</span>
            </span>
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
            <NavItem to={paths.churnModel(datasetId)} icon={UserMinusIcon}>
              Відтік
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

/**
 * The signed-in layout. The sidebar and the toolbar float on glass above the content, which
 * scrolls beneath the toolbar; pages add their own toolbar controls through `ToolbarSlot`.
 */
export function AppShell() {
  const datasetId = useDatasetId()
  const title = useRouteTitle()
  return (
    <SidebarProvider>
      <Sidebar variant="floating" collapsible="icon">
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
      </Sidebar>
      <SidebarInset className="bg-transparent">
        <ToolbarProvider>
          <GlassToolbar
            leading={<SidebarTrigger aria-label="Бічна панель" />}
            title={title}
            actions={<AccountMenu />}
          />
          <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
            <Outlet />
          </main>
        </ToolbarProvider>
      </SidebarInset>
    </SidebarProvider>
  )
}
