/** Server-Sent Events over fetch(): EventSource cannot send an Authorization header. */

const EVENT_END = "\n\n"

/** The `data` payloads of an event stream, as they arrive. */
export async function* eventData(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n")
      let end = buffer.indexOf(EVENT_END)
      while (end !== -1) {
        const data = buffer
          .slice(0, end)
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).replace(/^ /, ""))
          .join("\n")
        if (data) yield data
        buffer = buffer.slice(end + EVENT_END.length)
        end = buffer.indexOf(EVENT_END)
      }
    }
  } finally {
    reader.releaseLock()
  }
}
