import { describe, expect, it } from "vitest"

import { eventData } from "@/api/sse"

function streamOf(chunks: string[], onCancel?: () => void) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk))
      if (!onCancel) controller.close()
    },
    cancel: onCancel,
  })
}

async function collect(body: ReadableStream<Uint8Array>): Promise<string[]> {
  const seen: string[] = []
  for await (const data of eventData(body)) seen.push(data)
  return seen
}

describe("eventData", () => {
  it("yields data payloads across chunk boundaries and skips comments", async () => {
    const chunks = ['data: {"a":1}\n\n: ping\n\nda', 'ta: {"a":2}\r\n\r\n']
    expect(await collect(streamOf(chunks))).toEqual(['{"a":1}', '{"a":2}'])
  })

  it("handles a CRLF split between two chunks", async () => {
    const chunks = ['data: {"a":1}\r', '\n\r\ndata: {"a":2}\r\n\r\n']
    expect(await collect(streamOf(chunks))).toEqual(['{"a":1}', '{"a":2}'])
  })

  it("closes the connection when the reader stops early", async () => {
    let cancelled = false
    const body = streamOf(["data: 1\n\ndata: 2\n\n"], () => {
      cancelled = true
    })
    for await (const data of eventData(body)) {
      expect(data).toBe("1")
      break
    }
    expect(cancelled).toBe(true)
  })
})
