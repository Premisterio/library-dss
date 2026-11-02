import {
  BarChart3Icon,
  BookPlusIcon,
  DatabaseIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  UserMinusIcon,
} from "lucide-react"
import { Link, Outlet } from "react-router"

import { useDataset } from "@/api/datasets"
import { paths, useDatasetId } from "@/app/paths"
import { useRouteTitle } from "@/app/route-title"
import { GlassToolbar, ToolbarProvider } from "@/components/glass/toolbar"
import { AccountMenu } from "@/components/shell/account-menu"
import { DatasetSwitch } from "@/components/shell/dataset-switch"
import { NavItem } from "@/components/shell/nav-item"
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
import { supportsContent, supportsRetention } from "@/lib/status"

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

/**
 * The pages of the dataset in the URL. Churn and acquisition appear only when the ready dataset
 * supports them; while it loads, or is not ready, every page is listed.
 */
function DatasetPages({ datasetId }: { datasetId: number }) {
  const dataset = useDataset(datasetId)
  const known = dataset.data?.status === "ready" ? dataset.data : undefined
  return (
    <>
      <NavItem to={paths.dataset(datasetId)} icon={LayoutDashboardIcon} end>
        Огляд
      </NavItem>
      <NavItem to={paths.analytics(datasetId)} icon={BarChart3Icon}>
        Аналітика
      </NavItem>
      {(!known || supportsRetention(known)) && (
        <NavItem to={paths.churnModel(datasetId)} icon={UserMinusIcon}>
          Відтік
        </NavItem>
      )}
      {(!known || supportsContent(known)) && (
        <NavItem to={paths.content(datasetId)} icon={BookPlusIcon}>
          Закупівля
        </NavItem>
      )}
      <NavItem to={paths.reports(datasetId)} icon={FileTextIcon}>
        Звіти
      </NavItem>
    </>
  )
}

function DatasetNav({ datasetId }: { datasetId: number | undefined }) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Датасет</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          <DatasetSwitch datasetId={datasetId} />
          {datasetId !== undefined && <DatasetPages datasetId={datasetId} />}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

/**
 * The signed-in layout. The sidebar (navigation, the dataset switch, the account menu in its
 * footer) and the toolbar float on glass above the content, which scrolls beneath the toolbar;
 * pages add their view switching to the toolbar through `ToolbarSlot`.
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
        <SidebarFooter>
          <AccountMenu />
        </SidebarFooter>
      </Sidebar>
      {/* min-w-0: the content shrinks beside the sidebar, so a wide table scrolls in its card. */}
      <SidebarInset className="min-w-0 bg-transparent">
        <ToolbarProvider>
          <GlassToolbar leading={<SidebarTrigger aria-label="Бічна панель" />} title={title} />
          <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
            <Outlet />
          </main>
        </ToolbarProvider>
      </SidebarInset>
    </SidebarProvider>
  )
}
