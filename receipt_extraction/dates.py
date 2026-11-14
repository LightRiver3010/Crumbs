"""Resolve visible month/day labels only with an explicitly confirmed year."""
from datetime import date
import re
MONTHS={name: i for i,names in enumerate([
    ("jan","january"),("feb","february"),("mar","march"),("apr","april"),
    ("may",),("jun","june"),("jul","july"),("aug","august"),
    ("sep","sept","september"),("oct","october"),("nov","november"),("dec","december")],1) for name in names}


def resolve_missing_years(extraction, year):
    result=extraction.model_copy(deep=True)
    for order in result.orders:
        if order.order_date is not None or not order.order_date_text:
            continue
        text=order.order_date_text.strip()
        match=re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?",text,re.I)
        if match and match[1].lower() in MONTHS:
            try:
                order.order_date=date(year,MONTHS[match[1].lower()],int(match[2]))
            except ValueError:
                raise ValueError(f"The visible date {text!r} is invalid in {year}. Correct the date or year.") from None
    return result
