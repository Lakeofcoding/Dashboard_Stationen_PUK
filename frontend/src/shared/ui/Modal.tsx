/**
 * Sehr simples Modal (Dialog).
 *
 * Hinweis:
 * - Für ein MVP reicht das.
 * - In einer reifen App würde man A11y (Fokus-Trap, Escape, ARIA) noch weiter ausbauen.
 */

import { useEffect } from "react";
import type { ReactNode } from "react";

export type ModalProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({ title, open, onClose, children }: ModalProps) {
  // ESC zum Schließen
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      {/* Overlay */}
      <button
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-label="Schließen"
      />

      {/* Inhalt */}
      <div className="relative w-full max-w-lg rounded-2xl bg-white p-5 shadow-xl ring-1 ring-slate-200">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">{title}</h3>
            <p className="mt-1 text-xs text-slate-600">
              Bitte einen Grund auswählen. Das wird protokolliert.
            </p>
          </div>
          <button
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
            onClick={onClose}
            aria-label="Schließen"
          >
            ✕
          </button>
        </div>

        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
