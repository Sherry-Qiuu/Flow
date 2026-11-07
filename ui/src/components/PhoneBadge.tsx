import type { PhoneState } from "../state/types";

export function PhoneBadge({ phone }: { phone: PhoneState }) {
  const label = phone.present
    ? phone.charging
      ? "手机在架 · 充电中"
      : "手机在架"
    : "手机不在架";
  return (
    <div
      className={`phone-badge${phone.present ? " phone-badge--present" : ""}`}
    >
      <span className="phone-badge__dot" />
      <span>{label}</span>
    </div>
  );
}
