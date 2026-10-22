import { QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import { AuthProvider } from "@/api/auth"
import { queryClient } from "@/app/query-client"
import { AppRouter } from "@/app/router"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"

const root = document.getElementById("root")
if (!root) throw new Error("#root element is missing in index.html")

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <AppRouter />
          <Toaster position="top-right" />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>
)
