import { ListChecks, Server } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function ActionsPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Операции"
        title="Действия с VPS"
        description="Выберите хосты и действия, проверьте итоговый набор задач и запустите операцию."
      />

      <div className="mt-7 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <span className="mb-2 flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
              <Server aria-hidden="true" className="size-4.5" />
            </span>
            <CardTitle>Хосты</CardTitle>
            <CardDescription>
              Загрузка, поиск, выбор и регистрация VPS появятся на следующем этапе.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-24 rounded-md border border-dashed bg-muted/30" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <span className="mb-2 flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
              <ListChecks aria-hidden="true" className="size-4.5" />
            </span>
            <CardTitle>Действия</CardTitle>
            <CardDescription>
              Здесь будет множественный выбор команд и preview будущей Operation.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-24 rounded-md border border-dashed bg-muted/30" />
          </CardContent>
        </Card>
      </div>
    </main>
  )
}
