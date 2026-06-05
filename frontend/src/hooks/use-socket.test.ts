import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSocket } from "./use-socket";

// getMe is the cheap REST call the hook uses to trigger the cookie refresh on 4401.
const { getMeMock } = vi.hoisted(() => ({ getMeMock: vi.fn() }));
vi.mock("@/lib/api/auth", () => ({ getMe: getMeMock }));

/** Minimal controllable WebSocket stand-in. */
class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: ((e: Event) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  // ── test drivers ──
  triggerOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }
  triggerMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
  triggerClose(code: number) {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code });
  }
}

const latest = () => MockWebSocket.instances.at(-1)!;

beforeEach(() => {
  MockWebSocket.instances = [];
  getMeMock.mockReset();
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useSocket", () => {
  it("opens, dispatches parsed frames, and sends", async () => {
    const onEvent = vi.fn();
    const { result } = renderHook(() => useSocket("/ws/trip/5/", { onEvent }));

    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => latest().triggerOpen());
    await waitFor(() => expect(result.current.status).toBe("open"));

    act(() => latest().triggerMessage({ event: "TRIP_COMPLETED" }));
    expect(onEvent).toHaveBeenCalledWith({ event: "TRIP_COMPLETED" });

    let ok = false;
    act(() => {
      ok = result.current.send({ lat: 1 });
    });
    expect(ok).toBe(true);
    expect(latest().sent).toContain(JSON.stringify({ lat: 1 }));
  });

  it("stops on a 4403 close and never reconnects", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useSocket("/ws/fleet/"));

    act(() => latest().triggerClose(4403));
    expect(result.current.status).toBe("forbidden");

    act(() => vi.advanceTimersByTime(60_000));
    expect(MockWebSocket.instances).toHaveLength(1); // no retry
  });

  it("reconnects with backoff after an abnormal close", () => {
    vi.useFakeTimers();
    renderHook(() => useSocket("/ws/trip/5/"));

    act(() => latest().triggerOpen());
    act(() => latest().triggerClose(1006));
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => vi.advanceTimersByTime(1_600)); // base 1s + up to 0.5s jitter
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("refreshes once on 4401 then reconnects; a second 4401 stops", async () => {
    // 4401 is the backend's unauthenticated close code (realtime/consumers.py).
    getMeMock.mockResolvedValue({ id: 1 });
    const { result } = renderHook(() => useSocket("/ws/driver/5/"));

    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => latest().triggerClose(4401));

    await waitFor(() => expect(getMeMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(2));

    // The reconnected socket never opened, so a second 4401 means refresh didn't help.
    act(() => latest().triggerClose(4401));
    await waitFor(() => expect(result.current.status).toBe("forbidden"));
    expect(getMeMock).toHaveBeenCalledTimes(1); // not refreshed again
  });
});
