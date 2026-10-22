import { useNavigate } from "react-router"

import { useDatasets } from "@/api/datasets"
import { paths } from "@/app/paths"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/** Jump between ready datasets. Always controlled: "" shows the placeholder. */
export function DatasetSwitch({ datasetId }: { datasetId: number | undefined }) {
  const datasets = useDatasets()
  const navigate = useNavigate()
  const ready = (datasets.data ?? []).filter((d) => d.status === "ready")
  if (ready.length === 0) return null
  return (
    <Select
      value={datasetId === undefined ? "" : String(datasetId)}
      onValueChange={(value) => void navigate(paths.dataset(Number(value)))}
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
