import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800/80 bg-slate-900/75 text-slate-100 shadow-sm backdrop-blur-sm",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col space-y-1.5 p-5", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-base font-semibold leading-none tracking-tight text-slate-100", className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-xs text-slate-400", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  variant?: "default" | "success" | "warning" | "danger" | "outline" | "info";
}) {
  const styles = {
    default: "bg-slate-800 text-slate-200 border-slate-700",
    success: "bg-emerald-950/80 text-emerald-300 border-emerald-700/60",
    warning: "bg-amber-950/80 text-amber-300 border-amber-700/60",
    danger: "bg-rose-950/80 text-rose-300 border-rose-700/60",
    info: "bg-sky-950/80 text-sky-300 border-sky-700/60",
    outline: "bg-transparent text-slate-300 border-slate-700",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium transition-colors",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "outline" | "amber" | "danger";
  size?: "sm" | "md" | "lg";
}) {
  const variants = {
    primary: "bg-emerald-600 hover:bg-emerald-500 text-white border-transparent shadow-sm",
    secondary: "bg-slate-800 hover:bg-slate-700 text-slate-100 border-slate-700",
    outline: "bg-transparent hover:bg-slate-800/60 text-slate-200 border-slate-700",
    amber: "bg-amber-600 hover:bg-amber-500 text-slate-950 font-semibold border-transparent",
    danger: "bg-rose-600 hover:bg-rose-500 text-white border-transparent",
  };
  const sizes = {
    sm: "h-8 px-3 text-xs",
    md: "h-9 px-4 py-2 text-sm",
    lg: "h-10 px-5 text-sm",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
