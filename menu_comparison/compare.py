"""Curated item matches only; no fuzzy matching or assumed in-store prices."""
from datetime import timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo

PROVIDERS={"ubereats":"Uber Eats Menu Price","doordash":"DoorDash Menu Price"}


def comparison_rows(match, menus):
    result=[]
    for provider,label in PROVIDERS.items():
        target=match["sources"][provider]
        candidates=[r for r in menus.get(provider,[]) if r["source_item_id"]==target["item_id"]]
        row=candidates[0] if len(candidates)==1 else None
        valid=row is not None and row["item_name"]==target["expected_name"] and row.get("variant") is None and row.get("currency")=="USD" and isinstance(row.get("price_cents"),int) and row["price_cents"]>=0
        result.append({"source":label,"price_cents":row["price_cents"] if valid else None})
    prices=[r["price_cents"] for r in result if r["price_cents"] is not None]
    for row in result:
        price=row["price_cents"]
        row["price"]="Unavailable" if price is None else f"${price/100:.2f}"
        if price is None or len(prices)<2:
            row["difference"]="Not comparable"
        elif len(set(prices))==1:
            row["difference"]="Same price"
        elif price==min(prices):
            row["difference"]="Lowest price"
        else:
            difference=price-min(prices)
            pct=(Decimal(difference)*100/Decimal(min(prices))).quantize(Decimal('1'),rounding=ROUND_HALF_UP) if min(prices)>0 else None
            row["difference"]=f"+${difference/100:.2f}"+(f" (+{pct}%)" if pct is not None else "")
    return result


def last_scraped(menus):
    # One honest timestamp: freshness is limited by the older platform snapshot.
    if any(not menus.get(p) for p in PROVIDERS):
        return None
    return min(min(r["observed_at"] for r in menus[p]) for p in PROVIDERS)


def timestamp_label(value):
    if value.tzinfo is None:
        value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("America/New_York")).strftime("%b %d, %Y at %I:%M %p %Z")


def render_table(item_name, rows):
    body="".join(f'<tr><th scope="row">{escape(r["source"])}</th><td>{escape(r["price"])}</td><td>{escape(r["difference"])}</td></tr>' for r in rows)
    return '<style>\n.menu-price-card {border:1px solid #ddd;border-radius:16px;overflow:hidden;width:100%;color:var(--text-color,#222);}\n.menu-price-card table {width:100%;border-collapse:collapse;table-layout:fixed;font-family:inherit;font-size:1rem;}\n.menu-price-card th,.menu-price-card td {padding:14px 12px;text-align:left;vertical-align:middle;overflow-wrap:anywhere;border-bottom:1px solid #ddd;border-right:1px solid #ddd;}\n.menu-price-card thead {background:rgba(128,128,128,.17);}\n.menu-price-card tbody th {font-weight:500;}\n.menu-price-card td:last-child {font-weight:600;}\n.menu-price-card tr:last-child td,.menu-price-card tr:last-child th {border-bottom:0;}\n.menu-price-card th:last-child,.menu-price-card td:last-child {border-right:0;}\n@media(max-width:480px){.menu-price-card table {font-size:.82rem}.menu-price-card th,.menu-price-card td {padding:10px 7px;}}\n</style>' + f'<div class="menu-price-card"><table aria-label="Menu price comparison"><colgroup><col style="width:34%"><col style="width:30%"><col style="width:36%"></colgroup><thead><tr><th scope="col">Source</th><th scope="col">{escape(item_name)}</th><th scope="col">Difference vs. lowest</th></tr></thead><tbody>{body}</tbody></table></div>'
