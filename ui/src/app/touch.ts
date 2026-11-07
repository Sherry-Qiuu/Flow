/** Touchscreen API helpers: same origin as the served UI. */
export async function postJson(
  path: string,
  payload: unknown,
): Promise<unknown> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${path} ${response.status}`);
  }
  return response.json();
}

export function sendIntent(text: string): Promise<unknown> {
  return postJson("/api/intent", { text, source: "touch" });
}

export function confirmPlan(planId: string): Promise<unknown> {
  return postJson(`/api/plan/${planId}/confirm`, {});
}

export function focusControl(
  action: string,
  minutes?: number,
): Promise<unknown> {
  return postJson("/api/focus/control", {
    action,
    ...(minutes === undefined ? {} : { minutes }),
  });
}

export function endPhoneSession(): Promise<unknown> {
  return postJson("/api/phone/session/end", {});
}
