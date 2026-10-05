from __future__ import annotations

from datetime import date, datetime, time, timezone


def normalize_as_of(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("as_of datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def is_available(availability_date: datetime, as_of: date | datetime) -> bool:
    if availability_date.tzinfo is None:
        raise ValueError("availability_date must be timezone-aware")
    return availability_date.astimezone(timezone.utc) <= normalize_as_of(as_of)


def require_pit_safe(availability_date: datetime, as_of: date | datetime) -> None:
    if not is_available(availability_date, as_of):
        raise ValueError(
            f"LOOK_AHEAD_BLOCKED: availability={availability_date.isoformat()} "
            f"> as_of={normalize_as_of(as_of).isoformat()}"
        )
