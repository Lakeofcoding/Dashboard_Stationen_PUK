import { useEffect } from "react";

export type ToastKind = "info" | "warn" | "critical";

export function Toast({
  message,
  kind,
  onClose,
}: {
  message: string;
  kind: ToastKind;
  onClose: () => void;
}) {
  useEffect(() => {
    const t = window.setTimeout(onClose, 6000); // auto-close
    return () => window.clearTimeout(t);
  }, [onClose]);

  const bg =
    kind === "critical" ? "#d32f2f" : kind === "warn" ? "#f9a825" : "#1976d2";

  return (
    <div
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        maxWidth: 420,
        padding: "12px 14px",
        borderRadius: 8,
        color: "white",
        background: bg,
        boxShadow: "0 6px 18px rgba(0,0,0,0.25)",
        zIndex: 9999,
        fontFamily: "sans-serif",
      }}
      role="status"
      aria-live="polite"
    >
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{ fontWeight: 700 }}>
          {kind === "critical" ? "KRITISCH" : kind === "warn" ? "WARNUNG" : "INFO"}
        </div>
        <div style={{ flex: 1 }}>{message}</div>
        <button
          onClick={onClose}
          style={{
            background: "transparent",
            color: "white",
            border: 0,
            cursor: "pointer",
            fontSize: 16,
            lineHeight: 1,
          }}
          aria-label="Toast schließen"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
