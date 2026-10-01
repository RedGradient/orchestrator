import { Check } from "lucide-react"
import type * as React from "react"

import { cn } from "@/lib/utils"

export function Checkbox({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <span className="relative inline-flex size-4 shrink-0">
      <input
        type="checkbox"
        className={cn(
          "peer size-4 appearance-none rounded border bg-background outline-none transition-colors checked:border-primary checked:bg-primary focus-visible:ring-[3px] focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      <Check
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 hidden size-4 stroke-[3] p-0.5 text-primary-foreground peer-checked:block"
      />
    </span>
  )
}
