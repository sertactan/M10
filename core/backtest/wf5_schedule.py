from __future__ import annotations

import calendar
from datetime import date


def monthly_snapshot_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end must be >= start")
    out=[]
    year,month=start.year,start.month
    while (year,month) <= (end.year,end.month):
        last=calendar.monthrange(year,month)[1]
        d=date(year,month,last)
        if start <= d <= end:
            out.append(d)
        if month==12:
            year,month=year+1,1
        else:
            month+=1
    return out
