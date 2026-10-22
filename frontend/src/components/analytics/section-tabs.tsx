import type { ReactNode } from "react"

import { useLabel } from "@/api/enums"
import type { SectionKey } from "@/api/types"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ANALYTICS_TABS, isAnalyticsTab } from "@/lib/sections"

/** One tab per analytics section; the active one comes from the URL and shows `children`. */
export function SectionTabs({
  active,
  onChange,
  children,
}: {
  active: SectionKey
  onChange: (section: SectionKey) => void
  children: ReactNode
}) {
  const label = useLabel()
  return (
    <Tabs
      value={active}
      onValueChange={(value) => {
        if (isAnalyticsTab(value)) onChange(value)
      }}
      className="gap-4"
    >
      <TabsList className="flex-wrap">
        {ANALYTICS_TABS.map((key) => (
          <TabsTrigger key={key} value={key}>
            {label("analytics_section", key)}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value={active}>{children}</TabsContent>
    </Tabs>
  )
}
