import { describe, expect, it, vi } from "vitest";
import {
  FlowSocket,
  getWebSocketUrl,
  parseMessage,
  reconnectDelay,
  type WebSocketFactory,
  type WebSocketLike,
} from "./client";
import type { ConnectionStatus, WsMessage } from "../state/types";

class FakeSocket implements WebSocketLike {
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  message(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  disconnect(): void {
    this.readyState = 3;
    this.onclose?.();
  }
}

function harness() {
  const sockets: FakeSocket[] = [];
  const factory: WebSocketFactory = () => {
    const socket = new FakeSocket();
    sockets.push(socket);
    return socket;
  };
  const statuses: ConnectionStatus[] = [];
  const messages: WsMessage[] = [];
  const client = new FlowSocket(
    "ws://example/ws",
    {
      onMessage: (message) => messages.push(message),
      onStatus: (status) => statuses.push(status),
    },
    factory,
  );
  return { client, sockets, statuses, messages };
}

describe("websocket client", () => {
  it("uses an exponential reconnect delay capped at five seconds", () => {
    expect(reconnectDelay(0)).toBe(500);
    expect(reconnectDelay(1)).toBe(1000);
    expect(reconnectDelay(2)).toBe(2000);
    expect(reconnectDelay(3)).toBe(4000);
    expect(reconnectDelay(4)).toBe(5000);
    expect(reconnectDelay(10)).toBe(5000);
  });

  it("builds ws and wss URLs", () => {
    expect(
      getWebSocketUrl({ protocol: "http:", host: "127.0.0.1:8000" }),
    ).toBe("ws://127.0.0.1:8000/ws");
    expect(
      getWebSocketUrl({ protocol: "https:", host: "flow.local" }),
    ).toBe("wss://flow.local/ws");
  });

  it("parses valid envelopes and rejects invalid JSON", () => {
    const message = parseMessage(
      '{"type":"phone.changed","payload":{"present":true},"seq":3}',
    );
    expect(message?.type).toBe("phone.changed");
    expect(message?.payload?.present).toBe(true);
    expect(message?.seq).toBe(3);
    expect(parseMessage("{bad")).toBeNull();
    expect(parseMessage('{"payload":{}}')).toBeNull();
    expect(parseMessage("[]")).toBeNull();
  });

  it("reconnects after close and resets backoff after open", () => {
    vi.useFakeTimers();
    const { client, sockets, statuses, messages } = harness();
    client.connect();
    expect(statuses).toEqual(["connecting"]);
    sockets[0].open();
    expect(statuses).toContain("online");
    sockets[0].message({
      type: "ui.phase",
      payload: { phase: "listening" },
      seq: 1,
    });
    expect(messages[0].type).toBe("ui.phase");

    sockets[0].disconnect();
    expect(statuses[statuses.length - 1]).toBe("offline");
    vi.advanceTimersByTime(499);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);

    sockets[1].disconnect();
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(3);
    client.close();
    vi.useRealTimers();
  });

  it("sends only when open", () => {
    const { client, sockets } = harness();
    client.connect();
    client.send({ type: "ui.action", payload: { action: "x" } });
    expect(sockets[0].sent).toHaveLength(0);
    sockets[0].open();
    client.send({ type: "ui.action", payload: { action: "x" } });
    expect(sockets[0].sent).toHaveLength(1);
    client.close();
  });
});
