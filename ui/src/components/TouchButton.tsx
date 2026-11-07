interface Props {
  label: string;
  onClick: () => void | Promise<unknown>;
  variant?: "primary" | "quiet";
  disabled?: boolean;
}

export function TouchButton({
  label,
  onClick,
  variant = "quiet",
  disabled = false,
}: Props) {
  return (
    <button
      type="button"
      className={`touch-button touch-button--${variant}`}
      disabled={disabled}
      onClick={() => {
        void onClick();
      }}
    >
      {label}
    </button>
  );
}
