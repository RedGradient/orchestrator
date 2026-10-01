import { StatePanel } from "@/components/state-panel"
import { PageHeader } from "@/components/page-header"

export function SiteChecksPage() {
  return (
    <main>
      <PageHeader
        eyebrow="Мониторинг"
        title="Проверка сайта"
        description="Проверка HTTP, TLS, robots.txt и sitemap с сохранением истории запусков."
      />
      <StatePanel
        className="mt-7"
        kind="empty"
        title="Раздел готовится к переносу"
        description="Существующий интерфейс проверки сайта будет перенесён в React без изменения backend API."
      />
    </main>
  )
}
