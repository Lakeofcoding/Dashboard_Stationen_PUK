/**
 * Einheitlicher Button.
 *
 * Warum:
 * - Konsistentes Look & Feel
 * - Weniger Copy/Paste von Tailwind-Klassen
 * - Varianten (primary/secondary/danger) an einer Stelle
 */

import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Button({
  variant = "secondary",
  size = "md",
  className,
  disabled,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center rounded-md font-medium transition focus:outline-none focus:ring-2 focus:ring-slate-400/40 disabled:cursor-not-allowed disabled:opacity-60";

  const sizing = size === "sm" ? "px-3 py-2 text-xs" : "px-4 py-2 text-sm";

  const styles: Record<Variant, string> = {
    primary: "bg-slate-900 text-white hover:bg-slate-800",
    secondary: "bg-white text-slate-800 ring-1 ring-slate-200 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-500",
    ghost: "bg-transparent text-slate-700 hover:bg-slate-100",
  };

  return (
    <button
      className={cx(base, sizing, styles[variant], className)}
      disabled={disabled}
      {...rest}
    />
  );
}
