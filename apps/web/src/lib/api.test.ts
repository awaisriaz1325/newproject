import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, humanize, readCookie } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("readCookie", () => {
  it("finds a cookie among many", () => {
    expect(readCookie("cb_csrf", "a=1; cb_csrf=tok%3D1; b=2")).toBe("tok=1");
    expect(readCookie("missing", "a=1")).toBeNull();
  });
});

describe("api", () => {
  it("sends CSRF header on mutations and JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "cb_csrf=abc";
    await api("/x", { json: { a: 1 } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/x");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("abc");
    expect(init.body).toBe('{"a":1}');
  });

  it("maps structured API errors to readable messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { code: "x", message: "Readable" } }), { status: 409 })),
    );
    await expect(api("/y")).rejects.toMatchObject({ status: 409, code: "x", message: "Readable" });
  });

  it("humanizes known codes", () => {
    expect(humanize("email_not_verified")).toContain("verify your email");
    expect(new ApiError(401, "a", "b")).toBeInstanceOf(Error);
  });
});
