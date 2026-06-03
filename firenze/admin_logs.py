"""SQLAdmin view for browsing Firenze API logs."""

from __future__ import annotations

import asyncio
import datetime as dt
import gzip
import re
from pathlib import Path

from sqladmin import BaseView, expose
from sqladmin.authentication import login_required

from firenze.config import settings

LOGS_DIR = Path(settings.BASE_DIR) / "logs"
LOG_FILE_NAME = "firenze-api.log"
LOG_FILE_PATTERN = f"{LOG_FILE_NAME}*"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
    r"(?P<logger>[^.]+)\.(?P<level>[A-Z]+) "
    r"(?P<source>[^()]+)\((?P<line>\d+)\) (?P<message>.*)$"
)


def _read_log_lines(path: Path) -> list[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


def _parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S,%f")


def _discover_log_files() -> list[dict]:
    if not LOGS_DIR.exists():
        return []

    files = [path for path in LOGS_DIR.glob(LOG_FILE_PATTERN) if path.is_file()]
    files.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return [
        {
            "name": path.name,
            "path": path,
            "size": path.stat().st_size,
            "modified_at": dt.datetime.fromtimestamp(path.stat().st_mtime),
        }
        for path in files
    ]


def _parse_log_file(path: Path) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None

    for line_number, line in enumerate(_read_log_lines(path), start=1):
        match = LOG_LINE_RE.match(line)
        if match:
            if current:
                records.append(current)
            current = {
                "file_name": path.name,
                "file_path": str(path),
                "file_mtime": path.stat().st_mtime,
                "line_number": line_number,
                "timestamp": _parse_timestamp(match.group("timestamp")),
                "timestamp_raw": match.group("timestamp"),
                "logger": match.group("logger"),
                "level": match.group("level"),
                "source_file": match.group("source"),
                "source_line": int(match.group("line")),
                "message": match.group("message"),
                "raw": line,
            }
            continue

        if current is None:
            current = {
                "file_name": path.name,
                "file_path": str(path),
                "file_mtime": path.stat().st_mtime,
                "line_number": line_number,
                "timestamp": None,
                "timestamp_raw": "",
                "logger": "",
                "level": "INFO",
                "source_file": "",
                "source_line": 0,
                "message": line,
                "raw": line,
            }
            continue

        current["raw"] += f"\n{line}"
        current["message"] += f"\n{line}"

    if current:
        records.append(current)

    return records


def _normalize_query(value: str | None) -> str:
    return (value or "").strip()


def _normalize_level(value: str | None) -> str:
    normalized = (value or "ALL").strip().upper()
    return normalized if normalized in {"ALL", *LOG_LEVELS} else "ALL"


def _parse_filter_datetime(value: str | None) -> dt.datetime | None:
    normalized = _normalize_query(value)
    if not normalized:
        return None
    try:
        if "T" in normalized:
            return dt.datetime.fromisoformat(normalized)
        return dt.datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        return None


def collect_api_log_data(
    selected_files: list[str] | None = None,
    level: str = "ALL",
    query: str = "",
    after: dt.datetime | None = None,
    before: dt.datetime | None = None,
    limit: int = 250,
) -> dict:
    available_files = _discover_log_files()
    available_names = {entry["name"] for entry in available_files}
    selected_names = [name for name in (selected_files or []) if name in available_names]
    if not selected_names:
        selected_names = [entry["name"] for entry in available_files]

    level = _normalize_level(level)
    query = _normalize_query(query).lower()
    limit = max(1, min(int(limit), 1000))

    file_lookup = {entry["name"]: entry for entry in available_files}
    selected_file_entries = [file_lookup[name] for name in selected_names if name in file_lookup]

    records: list[dict] = []
    for file_entry in selected_file_entries:
        records.extend(_parse_log_file(file_entry["path"]))

    filtered_records = []
    for record in records:
        record_level = str(record["level"]).upper()
        if level != "ALL" and record_level != level:
            continue

        if after and record["timestamp"] and record["timestamp"] < after:
            continue
        if before and record["timestamp"] and record["timestamp"] > before:
            continue

        if query:
            haystack = "\n".join(
                [
                    record.get("message", ""),
                    record.get("raw", ""),
                    record.get("source_file", ""),
                    record.get("file_name", ""),
                    record.get("logger", ""),
                ]
            ).lower()
            if query not in haystack:
                continue

        filtered_records.append(record)

    filtered_records.sort(
        key=lambda record: (record["timestamp"] or dt.datetime.min, record["file_mtime"], record["line_number"]),
        reverse=True,
    )

    for record in filtered_records:
        record["display_timestamp"] = (
            record["timestamp"].strftime("%Y-%m-%d %H:%M:%S,%f")[:-3] if record["timestamp"] else "—"
        )

    return {
        "available_files": available_files,
        "selected_files": selected_names,
        "level": level,
        "query": query,
        "after": after,
        "before": before,
        "limit": limit,
        "total_records": len(filtered_records),
        "entries": filtered_records[:limit],
    }


class FirenzeApiLogViewer(BaseView):
    name = "API Logs"
    icon = "fa fa-file-lines"
    category = "Sistema"
    category_icon = "fa-solid fa-server"

    @expose("/api-logs", methods=["GET"], identity="api-logs")
    @login_required
    async def index(self, request):
        selected_files = request.query_params.getlist("files")
        level = request.query_params.get("level", "ALL")
        query = request.query_params.get("q", "")
        after = _parse_filter_datetime(request.query_params.get("after"))
        before = _parse_filter_datetime(request.query_params.get("before"))

        try:
            limit = int(request.query_params.get("limit", "250"))
        except ValueError:
            limit = 250

        data = await asyncio.to_thread(
            collect_api_log_data,
            selected_files or None,
            level,
            query,
            after,
            before,
            limit,
        )

        return await self.templates.TemplateResponse(
            request,
            "admin_log_view.html",
            context={
                "title": "API Logs",
                "subtitle": "Firenze API log explorer",
                "log_files": data["available_files"],
                "selected_files": set(data["selected_files"]),
                "selected_level": data["level"],
                "query": request.query_params.get("q", ""),
                "after": request.query_params.get("after", ""),
                "before": request.query_params.get("before", ""),
                "limit": data["limit"],
                "total_records": data["total_records"],
                "entries": data["entries"],
                "log_levels": ("ALL", *LOG_LEVELS),
            },
        )
