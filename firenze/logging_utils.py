from __future__ import annotations

import logging
from copy import copy
from datetime import datetime


class CombinedAccessFormatter(logging.Formatter):
    """Format Uvicorn access records in combined log style."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
        **kwargs,
    ) -> None:
        if fmt is None and "format" in kwargs:
            fmt = kwargs.pop("format")
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        try:
            client_addr, method, full_path, http_version, status_code = record.args
        except TypeError, ValueError:
            return super().format(record)

        recordcopy = copy(record)
        recordcopy.__dict__.update(
            {
                "h": client_addr,
                "l": "-",
                "u": "-",
                "t": datetime.fromtimestamp(record.created).astimezone().strftime("[%d/%b/%Y:%H:%M:%S %z]"),
                "r": f"{method} {full_path} HTTP/{http_version}",
                "s": status_code,
                "b": "-",
                "f": "-",
                "a": "-",
            }
        )
        return super().format(recordcopy)
