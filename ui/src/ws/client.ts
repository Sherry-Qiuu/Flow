import type { ConnectionStatus, WsMessage } from "../state/types";

export interface WebSocketLike {
  readyState: number;
  send(data: string): void;
  close(): void;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface SocketHandlers {
  onMessage(message: WsMessage): void;
  onStatus(status: ConnectionStatus): void;
}

const OPEN = 1;
const BASE_DELAY_MS = 500;
const MAX_DELAY_MS = 5000;

export function reconnectDelay(attempt: number): number {
  return Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** attempt);
}

export function getWebSocketUrl(
  locationLike: Pick<Location, "protocol" | "host"> = window.location,
): string {
  const scheme = locationLike.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${locationLike.host}/ws`;
}

const defaultFactory: WebSocketFactory = (url) =>
  new WebSocket(url) as unknown as WebSocketLike;

export class FlowSocket {
  private socket: WebSocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  private stopped = false;

  constructor(
    private readonly url: string,
    private readonly handlers: SocketHandlers,
    private readonly factory: WebSocketFactory = defaultFactory,
  ) {}

  connect(): void {
    if (this.stopped) {
      return;
    }
    this.handlers.onStatus("connecting");
    try {
      this.socket = this.factory(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket.onopen = () => {
      this.attempt = 0;
      this.handlers.onStatus("online");
    };
    this.socket.onmessage = (event) => {
      const message = parseMessage(event.data);
      if (message !== null) {
        this.handlers.onMessage(message);
      }
    };
    this.socket.onerror = () => {
      this.handlers.onStatus("offline");
    };
    this.socket.onclose = () => {
      this.socket = null;
      this.handlers.onStatus("offline");
      this.scheduleReconnect();
    };
  }

  send(message: WsMessage): void {
    if (this.socket?.readyState === OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  close(): void {
    this.stopped = true;
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.timer !== null) {
      return;
    }
    const delay = reconnectDelay(this.attempt);
    this.attempt += 1;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.connect();
    }, delay);
  }
}

export function parseMessage(raw: string): WsMessage | null {
  try {
    const value = JSON.parse(raw) as unknown;
    if (value === null || typeof value !== "object") {
      return null;
    }
    const record = value as Record<string, unknown>;
    if (typeof record.type !== "string" || record.type.length === 0) {
      return null;
    }
    return {
      type: record.type,
      payload:
        record.payload !== null && typeof record.payload === "object"
          ? (record.payload as Record<string, unknown>)
          : {},
      seq: typeof record.seq === "number" ? record.seq : undefined,
      ts: typeof record.ts === "string" ? record.ts : undefined,
    };
  } catch {
    return null;
  }
}
