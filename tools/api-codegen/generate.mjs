// Generates packages/api-client/src/schema.ts from packages/api-client/openapi.json.
// Run via `npm run api:generate` (after `dss openapi --out packages/api-client/openapi.json`).
import { readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"

import openapiTS, { astToString } from "openapi-typescript"

const clientDir = new URL("../../packages/api-client/", import.meta.url)
const spec = JSON.parse(await readFile(new URL("openapi.json", clientDir), "utf8"))

const ast = await openapiTS(spec, { alphabetize: true, exportType: true })
const header = "// Generated from openapi.json by tools/api-codegen. Do not edit by hand.\n\n"
const target = new URL("src/schema.ts", clientDir)
await writeFile(target, header + astToString(ast), "utf8")
console.log(`wrote ${fileURLToPath(target)}`)
