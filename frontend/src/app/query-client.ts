import { MutationCache, QueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiProblem, errorMessage } from "@/api/problem"

declare module "@tanstack/react-query" {
  interface Register {
    /** `silent`: the component shows the mutation's error itself, so no toast. */
    mutationMeta: { silent?: boolean }
  }
}

export const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onError: (error, _variables, _result, mutation) => {
      if (!mutation.meta?.silent) toast.error(errorMessage(error))
    },
  }),
  defaultOptions: {
    queries: {
      // Problems from the API (404, 409, ...) are answers, not network glitches: don't retry them.
      retry: (failures, error) => !(error instanceof ApiProblem) && failures < 2,
      refetchOnWindowFocus: false,
    },
  },
})
