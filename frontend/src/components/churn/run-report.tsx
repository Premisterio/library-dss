import type { ChurnRunDetail } from "@/api/types"
import { BacktestPanel } from "@/components/churn/backtest-panel"
import { CalibrationPanel } from "@/components/churn/calibration-panel"
import { ImportancePanel } from "@/components/churn/importance-panel"
import { ModelComparison } from "@/components/churn/model-comparison"
import { QualityTiles } from "@/components/churn/quality-tiles"

/** How good a trained run is and what it rests on. */
export function RunReport({ run }: { run: ChurnRunDetail }) {
  return (
    <>
      <QualityTiles run={run} />
      <ModelComparison run={run} />
      <div className="grid gap-6 xl:grid-cols-2">
        <CalibrationPanel run={run} />
        <ImportancePanel run={run} />
      </div>
      <BacktestPanel run={run} />
    </>
  )
}
