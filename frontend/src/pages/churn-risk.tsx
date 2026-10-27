import { useState } from "react"

import { SCORES_PAGE_SIZE, useActiveChurnRun, useChurnScore, useChurnScores } from "@/api/churn"
import type { ChurnRun } from "@/api/types"
import { ChurnNav } from "@/components/churn/churn-nav"
import { MemberCard } from "@/components/churn/member-card"
import { NoActiveRun } from "@/components/churn/no-active-run"
import { NoRetention } from "@/components/churn/no-retention"
import { RiskTable } from "@/components/churn/risk-table"
import { RiskTiles } from "@/components/churn/risk-tiles"
import { Pager } from "@/components/common/pager"
import { PanelCard } from "@/components/common/panel-card"
import { QueryView } from "@/components/common/query-view"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { supportsRetention } from "@/lib/status"
import { useCurrentDataset } from "@/pages/dataset-layout"

function RiskGroup({ run, timezone }: { run: ChurnRun; timezone: string }) {
  const [offset, setOffset] = useState(0)
  const [member, setMember] = useState<string>()
  const scores = useChurnScores(run.id, offset)
  const score = useChurnScore(run.id, member)
  return (
    <>
      <RiskTiles run={run} />
      <PanelCard
        title="Читачі під ризиком"
        description="Від найвищого ризику. Причини — ознаки, з типовим значенням яких ризик був би найнижчим, і на скільки вони його підвищують."
      >
        <QueryView query={scores} skeletonClassName="h-64">
          {(page) => (
            <div className="flex flex-col gap-4">
              <RiskTable scores={page.items} timezone={timezone} onOpen={setMember} />
              <Pager
                offset={offset}
                limit={SCORES_PAGE_SIZE}
                total={page.total}
                onChange={setOffset}
              />
            </div>
          )}
        </QueryView>
      </PanelCard>
      <Sheet open={member !== undefined} onOpenChange={(open) => !open && setMember(undefined)}>
        <SheetContent className="overflow-y-auto data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>Читач {member}</SheetTitle>
            <SheetDescription>Усе, що модель знала про читача на дату зрізу.</SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            <QueryView query={score} skeletonClassName="h-96">
              {(detail) => <MemberCard score={detail} timezone={timezone} />}
            </QueryView>
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}

export function ChurnRiskPage() {
  const dataset = useCurrentDataset()
  const active = useActiveChurnRun(dataset.id)
  return (
    <>
      <ChurnNav datasetId={dataset.id} />
      {supportsRetention(dataset) ? (
        <QueryView query={active} skeletonClassName="h-40">
          {(run) =>
            run ? (
              <RiskGroup key={run.id} run={run} timezone={dataset.timezone} />
            ) : (
              <NoActiveRun datasetId={dataset.id} />
            )
          }
        </QueryView>
      ) : (
        <NoRetention />
      )}
    </>
  )
}
