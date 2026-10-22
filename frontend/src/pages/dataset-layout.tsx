import { Link, Outlet, useOutletContext } from "react-router"

import { useDataset } from "@/api/datasets"
import type { Dataset } from "@/api/types"
import { paths, useDatasetId } from "@/app/paths"
import { QueryView } from "@/components/common/query-view"
import { DatasetNotReady } from "@/components/datasets/dataset-not-ready"
import { ToolbarSlot } from "@/components/glass/toolbar"
import { SnapshotCapsule } from "@/components/shell/snapshot-capsule"
import { NotFound } from "@/pages/not-found"

function ReadyDataset({ id }: { id: number }) {
  const dataset = useDataset(id)
  return (
    <QueryView
      query={dataset}
      skeletonClassName="h-40"
      errorDetails={
        <Link to={paths.datasets} className="underline">
          До списку датасетів
        </Link>
      }
    >
      {(data) =>
        data.status === "ready" ? (
          <>
            <ToolbarSlot side="trailing">
              <SnapshotCapsule dataset={data} />
            </ToolbarSlot>
            <Outlet context={data} />
          </>
        ) : (
          <DatasetNotReady dataset={data} />
        )
      }
    </QueryView>
  )
}

/** The pages of one dataset: they render only once its import is ready. */
export function DatasetLayout() {
  const id = useDatasetId()
  if (id === undefined) return <NotFound className="" />
  return <ReadyDataset id={id} />
}

/** The ready dataset of the page, from `DatasetLayout`. */
export function useCurrentDataset(): Dataset {
  return useOutletContext<Dataset>()
}
