import assert from "node:assert/strict"
import { test } from "node:test"
import { health, uploadStock } from "../lib/api"

const originalFetch = globalThis.fetch

function setFetch(fetcher: typeof fetch) {
  globalThis.fetch = fetcher
}

test("health returns typed success from the API", async () => {
  setFetch(async () => new Response(JSON.stringify({
    status: "ok",
    series_count: 250,
    data_dir: "public/data",
    prophet_available: true,
    version: "0.1.0",
  }), { status: 200 }))

  try {
    const result = await health()
    assert.equal(result.ok, true)
    if (result.ok === true) assert.equal(result.data.series_count, 250)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test("stock upload returns validation details for HTTP 422", async () => {
  setFetch(async (_input, init) => {
    assert.equal(new Headers(init?.headers).has("Content-Type"), false)
    return new Response(JSON.stringify({
      errors: [
        { line: 3, message: "store must be 1-5" },
        { line: 4, message: "Duplicate (store, item)" },
      ],
    }), { status: 422 })
  })

  try {
    const result = await uploadStock(new File(["stock"], "stock.csv", { type: "text/csv" }))
    assert.equal(result.ok, false)
    if (result.ok === false) {
      assert.equal(result.status, 422)
      assert.deepEqual(result.errors, [
        { line: 3, message: "store must be 1-5" },
        { line: 4, message: "Duplicate (store, item)" },
      ])
      assert.match(result.error, /Line 3:/)
    }
  } finally {
    globalThis.fetch = originalFetch
  }
})

test("health converts network failures into a result", async () => {
  setFetch(async () => {
    throw new TypeError("Network unavailable")
  })

  try {
    const result = await health()
    assert.deepEqual(result, { ok: false, error: "Network unavailable" })
  } finally {
    globalThis.fetch = originalFetch
  }
})

test("health converts request timeouts into a result", async () => {
  setFetch((_input, init) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => {
      reject(new DOMException("Aborted", "AbortError"))
    }, { once: true })
  }))

  try {
    const result = await health()
    assert.equal(result.ok, false)
    if (result.ok === false) assert.match(result.error, /timed out after 5 seconds/)
  } finally {
    globalThis.fetch = originalFetch
  }
})
