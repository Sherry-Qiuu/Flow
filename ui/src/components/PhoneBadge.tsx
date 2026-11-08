import { useI18n } from "../i18n";
import type { PhoneState } from "../state/types";

export function PhoneBadge({ phone }: { phone: PhoneState }) {
  const { t } = useI18n();
  const label = phone.present
    ? phone.charging
      ? t.phoneBadge.dockedCharging
      : t.phoneBadge.docked
    : t.phoneBadge.away;
  return (
    <div
      className={`phone-badge${phone.present ? " phone-badge--present" : ""}`}
    >
      <span className="phone-badge__dot" />
      <span>{label}</span>
    </div>
  );
}
