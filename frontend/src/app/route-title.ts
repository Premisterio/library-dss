import { useMatches } from "react-router"

/** What a route declares in its `handle`. */
export type RouteHandle = { title: string }

function titleOf(handle: unknown): string | undefined {
  return typeof handle === "object" &&
    handle !== null &&
    "title" in handle &&
    typeof handle.title === "string"
    ? handle.title
    : undefined
}

/** The title of the deepest route that has one. */
export function useRouteTitle(): string | undefined {
  return useMatches()
    .map((match) => titleOf(match.handle))
    .findLast((title) => title !== undefined)
}
