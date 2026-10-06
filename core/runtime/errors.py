from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Callable


def install_exception_handler(
    *,
    user_notifier: Callable[[str], None] | None = None,
) -> None:
    logger = logging.getLogger("s153.unhandled")

    def handle(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if user_notifier is not None:
            user_notifier(
                "Beklenmeyen bir hata oluştu. Ayrıntılar uygulama loguna kaydedildi."
            )

    sys.excepthook = handle


def format_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
