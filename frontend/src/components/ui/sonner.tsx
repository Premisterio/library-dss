"use client"

import { useAppearance } from "@/app/appearance"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import {
  CircleCheckIcon,
  InfoIcon,
  TriangleAlertIcon,
  OctagonXIcon,
  Loader2Icon,
} from "lucide-react"

// Customised: follows the app's appearance and floats on glass (DESIGN.md §4).
const Toaster = ({ ...props }: ToasterProps) => {
  const { resolved } = useAppearance()
  return (
    <Sonner
      theme={resolved}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 motion-safe:animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--glass-fill-thick)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--glass-edge)",
          "--border-radius": "1rem",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
