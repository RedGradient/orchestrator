import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ROBOTS_DIRECTIVES = {"user-agent", "allow", "disallow", "sitemap", "crawl-delay", "host", "clean-param"}
SITEMAP_URL_FIELDS = {"loc", "lastmod", "changefreq", "priority"}
SITEMAP_INDEX_FIELDS = {"loc", "lastmod"}
CHANGEFREQ_VALUES = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}
_ERRNO_PREFIX = re.compile(r"^\[Errno [+-]?\d+\]\s*")


def _strip_errno(error: str) -> str:
    """Убирает префикс [Errno число] из начала текста ошибки."""

    return _ERRNO_PREFIX.sub("", error, count=1)


def _format_issuer(certificate: dict) -> str | None:
    """Собирает строку издателя из атрибутов SSL-сертификата."""

    issuer = certificate.get("issuer")
    if not issuer:
        return None

    parts = [f"{name}={value}" for rdn in issuer for name, value in rdn]
    return ", ".join(parts) or None


def _inspect_robots(text: str) -> tuple[bool, list[str], list[str], list[str]]:
    """Проверяет синтаксис robots.txt и собирает ошибки, предупреждения и ссылки на sitemap."""

    errors: list[str] = []
    warnings: list[str] = []
    sitemaps: list[str] = []
    seen_user_agent = False

    if not text.strip():
        warnings.append("Файл robots.txt пустой")
        return True, errors, warnings, sitemaps

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue

        if ":" not in line:
            errors.append(f"Строка {line_no}: ожидается директива вида «имя: значение»")
            continue

        name, value = line.split(":", 1)
        name = name.strip().lower()
        value = value.strip()
        if not name:
            errors.append(f"Строка {line_no}: пустое имя директивы")
            continue

        if name == "user-agent":
            if not value:
                errors.append(f"Строка {line_no}: пустой User-agent")
            seen_user_agent = True
        elif name in {"allow", "disallow"}:
            if not seen_user_agent:
                warnings.append(f"Строка {line_no}: {name} указан до User-agent")
            if value and not value.startswith("/") and not value.startswith("*"):
                warnings.append(f"Строка {line_no}: путь должен начинаться с /")
        elif name == "sitemap":
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"Строка {line_no}: Sitemap должен быть абсолютным http(s) URL")
            elif value not in sitemaps:
                sitemaps.append(value)
        elif name not in ROBOTS_DIRECTIVES:
            warnings.append(f"Строка {line_no}: неизвестная директива «{name}»")

    if not seen_user_agent:
        warnings.append("Нет директивы User-agent")
    if not sitemaps:
        warnings.append("Нет директивы Sitemap")

    return not errors, errors, warnings, sitemaps


def _local_name(tag: str) -> str:
    """Возвращает локальное имя XML-тега без пространства имён."""

    return tag.rsplit("}", 1)[-1]


_LASTMOD_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:T(?P<clock>\d{2}:\d{2}:\d{2})(?:\.\d+)?"
    r"(?P<zone>Z|[+-]\d{2}:\d{2})?)?$"
)


def _valid_lastmod(value: str) -> bool:
    """Проверяет, что дата lastmod записана в формате W3C Datetime."""

    match = _LASTMOD_RE.fullmatch(value)
    if match is None:
        return False
    try:
        datetime.strptime(match.group("date"), "%Y-%m-%d")
        if match.group("clock"):
            datetime.strptime(match.group("clock"), "%H:%M:%S")
    except ValueError:
        return False
    return True


def _inspect_sitemap(text: str) -> tuple[bool, list[str], list[str], int | None]:
    """Проверяет XML sitemap и собирает ошибки, предупреждения и число адресов."""

    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        return False, ["Пустой sitemap"], warnings, None

    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        return False, [f"Некорректный XML: {error}"], warnings, None

    root_name = _local_name(root.tag)
    if root_name not in {"urlset", "sitemapindex"}:
        return False, [f"Корневой элемент должен быть urlset или sitemapindex, получен «{root_name}»"], warnings, None

    if not root.tag.startswith("{" + SITEMAP_NS + "}"):
        warnings.append(f"Нет пространства имён {SITEMAP_NS}")

    entry_name = "url" if root_name == "urlset" else "sitemap"
    allowed_fields = SITEMAP_URL_FIELDS if root_name == "urlset" else SITEMAP_INDEX_FIELDS
    url_count = 0

    for child in root:
        child_name = _local_name(child.tag)
        if child_name != entry_name:
            warnings.append(f"Неожиданный элемент «{child_name}»")
            continue

        loc = None
        for field in child:
            field_name = _local_name(field.tag)
            field_value = (field.text or "").strip()
            if field_name not in allowed_fields:
                warnings.append(f"Неожиданное поле «{field_name}» в {entry_name}")
                continue
            if field_name == "loc":
                loc = field_value
            elif field_name == "lastmod" and field_value and not _valid_lastmod(field_value):
                warnings.append(f"Некорректный lastmod: {field_value}")
            elif field_name == "changefreq" and field_value.lower() not in CHANGEFREQ_VALUES:
                warnings.append(f"Некорректный changefreq: {field_value}")
            elif field_name == "priority" and field_value:
                try:
                    priority = float(field_value)
                except ValueError:
                    priority = -1
                if not 0.0 <= priority <= 1.0:
                    warnings.append(f"priority должен быть от 0.0 до 1.0: {field_value}")

        if not loc:
            errors.append(f"Элемент {entry_name} без loc")
            continue

        parsed = urlparse(loc)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"loc должен быть абсолютным http(s) URL: {loc}")
            continue
        url_count += 1

    if url_count == 0 and not errors:
        warnings.append("Sitemap не содержит ссылок")
    if url_count > 50_000:
        warnings.append("В sitemap больше 50 000 адресов")

    return not errors, errors, warnings, url_count
