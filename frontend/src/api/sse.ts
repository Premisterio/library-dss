/** Server-Sent Events over fetch(): EventSource cannot send an Authorization header. */

const EVENT_END = "\n\n"

function dataOf(event: string): string {
  return event
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""))
    .join("\n")
}

/** The `data` payloads of an event stream, as they arrive. */
export async function* eventData(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    for (;;) {
      // oxlint-disable-next-line no-await-in-loop -- a stream is read one chunk after another
      const { value, done } = await reader.read()
      if (done) break
      // Normalise on the whole buffer: a CRLF may be split across two chunks.
      buffer = (buffer + decoder.decode(value, { stream: true })).replaceAll("\r\n", "\n")
      let end = buffer.indexOf(EVENT_END)
      while (end !== -1) {
        const data = dataOf(buffer.slice(0, end))
        if (data) yield data
        buffer = buffer.slice(end + EVENT_END.length)
        end = buffer.indexOf(EVENT_END)
      }
    }
  } finally {
    // Also runs when the consumer stops early: close the connection, not just the lock.
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
