import type * as React from "react"

import { cn } from "@/lib/utils"

export function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      className={cn(
        "h-9 w-full min-w-0 rounded-md border bg-background px-3 py-1 text-sm shadow-xs transition-colors outline-none placeholder:text-muted-foreground/50 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  )
}
