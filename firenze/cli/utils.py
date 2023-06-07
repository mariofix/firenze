import logging.config
from typing import Any

import pystrix
import typer

from firenze.config import LOGGING_CONFIG_CLI

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")


def verbose(agi: Any, msg: str) -> None:
    if agi:
        try:
            agi.execute(pystrix.agi.core.Verbose(msg))
        except Exception as e:
            logger.error(e)
            raise typer.Exit(code=1)


def set_asterisk_var(agi: Any, name: str, value: str) -> None:
    if agi:
        try:
            logger.debug(f"{name=}, {value=}")
            agi.execute(pystrix.agi.core.SetVariable(name, value))
        except Exception as e:
            logger.error(e)
            raise typer.Exit(code=1)
