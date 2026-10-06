from __future__ import annotations

import os


DEFAULT_SEC_USER_AGENT = (
    "S15.3 Research Terminal "
    "(https://github.com/sertactan/M10)"
)


def resolve_sec_user_agent(value: str | None = None) -> str:
    """Return an identifying User-Agent for SEC fair-access requests.

    A user-supplied SEC_USER_AGENT still takes precedence. The packaged desktop
    app remains usable without environment-variable setup by identifying itself
    with its public project URL.
    """
    return (
        (value or "").strip()
        or os.getenv("SEC_USER_AGENT", "").strip()
        or DEFAULT_SEC_USER_AGENT
    )
