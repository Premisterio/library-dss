import { CalendarClockIcon, ChevronsUpDownIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { useDatasets } from "@/api/datasets"
import type { Dataset } from "@/api/types"
import { paths } from "@/app/paths"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar"
import { formatDay } from "@/lib/format"

/** The dataset's name over the date its numbers describe. */
function NameAndDate({ dataset }: { dataset: Dataset }) {
  return (
    <span className="flex min-w-0 flex-col leading-tight">
      <span className="truncate font-medium">{dataset.name}</span>
      <span className="truncate text-xs text-muted-foreground">
        станом на {formatDay(dataset.as_of)}
      </span>
    </span>
  )
}

/**
 * Which dataset the pages show and the date its numbers describe, with a jump to another ready
 * dataset. Collapsed to icons, the sidebar keeps its icon, its tooltip names the dataset and the
 * date, and the menu opens beside it.
 */
export function DatasetSwitch({ datasetId }: { datasetId: number | undefined }) {
  const datasets = useDatasets()
  const navigate = useNavigate()
  const { isMobile, state } = useSidebar()
  const ready = (datasets.data ?? []).filter((d) => d.status === "ready")
  if (ready.length === 0) return null
  const current = ready.find((d) => d.id === datasetId)
  const snapshot = current ? `${current.name}, станом на ${formatDay(current.as_of)}` : undefined
  return (
    <SidebarMenuItem>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton
            size="lg"
            aria-label={snapshot ? `Датасет: ${snapshot}` : "Оберіть датасет"}
            tooltip={snapshot ?? "Оберіть датасет"}
            // Collapsed, the tooltip names the dataset; a title would add a second tooltip.
            title={
              current && state === "expanded" ? `Часовий пояс: ${current.timezone}` : undefined
            }
            onFocus={(event) => {
              // The menu hands focus back as it closes; only keyboard focus opens the tooltip.
              if (!event.currentTarget.matches(":focus-visible")) event.preventDefault()
            }}
          >
            {/* In the icon rail the tile loses its fill: a fill there marks the current page. */}
            <span
              aria-hidden
              className="flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-fill text-muted-foreground group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:text-inherit"
            >
              <CalendarClockIcon className="size-4" />
            </span>
            {current ? (
              <NameAndDate dataset={current} />
            ) : (
              <span className="truncate text-muted-foreground">Оберіть датасет</span>
            )}
            <ChevronsUpDownIcon className="ml-auto size-4 text-muted-foreground" />
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side={isMobile ? "bottom" : "right"}
          align="start"
          sideOffset={4}
          className="w-64"
        >
          <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
            Датасети
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={datasetId === undefined ? "" : String(datasetId)}
            onValueChange={(value) => {
              // The menu reports the checked item too; picking it again stays on the page.
              const id = Number(value)
              if (id !== datasetId) void navigate(paths.dataset(id))
            }}
          >
            {ready.map((d) => (
              <DropdownMenuRadioItem key={d.id} value={String(d.id)}>
                <NameAndDate dataset={d} />
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  )
}
