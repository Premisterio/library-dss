import { QueryClient } from "@tanstack/react-query"

import { ApiProblem } from "@/lib/api"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Problems from the API (404, 409, ...) are answers, not network glitches: don't retry them.
      retry: (failures, error) => !(error instanceof ApiProblem) && failures < 2,
      refetchOnWindowFocus: false,
    },
  },
})
