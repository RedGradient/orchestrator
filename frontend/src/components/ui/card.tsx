import type * as React from "react"

import { cn } from "@/lib/utils"

function Card({ className, ...props }: React.ComponentProps<"section">) {
  return <section className={cn("rounded-lg border bg-card text-card-foreground", className)} {...props} />
}

function CardHeader({ className, ...props }: React.ComponentProps<"header">) {
  return <header className={cn("flex flex-col gap-1.5 p-5", className)} {...props} />
}

function CardTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return <h2 className={cn("font-semibold tracking-tight", className)} {...props} />
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-sm leading-6 text-muted-foreground", className)} {...props} />
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 pb-5", className)} {...props} />
}

export { Card, CardContent, CardDescription, CardHeader, CardTitle }
