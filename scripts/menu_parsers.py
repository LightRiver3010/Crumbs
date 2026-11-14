"""Website-specific adapters. Add new providers here after validating their HTML."""
from decimal import Decimal
import json
import re
import uuid
from urllib.parse import parse_qs, unquote, urlsplit
from bs4 import BeautifulSoup
PRICE = re.compile(r"^\$(\d[\d,]*\.\d{2})$")

def parse_menu(html, expected_store, expected_heading=None):
    """Only accept unambiguous visible card prices, never ratings or modifiers."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if not heading or not heading.get_text(" ", strip=True):
        raise ValueError("Restaurant heading missing; possible error or block page.")
    if expected_heading and heading.get_text(" ", strip=True).casefold() != expected_heading.casefold():
        raise ValueError("Restaurant heading does not match the configured source.")
    items, rejects, conflicts = {}, [], set()
    cards = soup.select('a[href*="mod=quickView"]')
    for card in cards:
        item_id = None
        try:
            query = parse_qs(urlsplit(card["href"]).query)
            encoded = query.get("modctx", [""])[0]
            context = None
            for _ in range(3):
                try:
                    context = json.loads(encoded)
                    break
                except json.JSONDecodeError:
                    encoded = unquote(encoded)
            if not isinstance(context, dict) or context.get("storeUuid") != expected_store:
                raise ValueError("Missing or unexpected store ID.")
            item_id = str(uuid.UUID(context["itemUuid"]))
            texts = [s.get_text(" ", strip=True) for s in card.select('[data-testid="rich-text"]')]
            prices = [PRICE.fullmatch(t) for t in texts]
            prices = [p for p in prices if p]
            if not texts or not texts[0] or PRICE.fullmatch(texts[0]) or len(prices) != 1:
                raise ValueError("Missing or ambiguous name/price; requires manual review.")
            cents = int(Decimal(prices[0].group(1).replace(",", "")) * 100)
            if not 0 < cents < 2**63:
                raise ValueError("Invalid positive INT64 price.")
            category_heading = card.find_previous("h3")
            item = {
                "source_item_id": item_id, "item_name": texts[0],
                "price_cents": cents,
                "category": category_heading.get_text(" ", strip=True) if category_heading else None,
            }
            if item_id in items and items[item_id] != item:
                conflicts.add(item_id)
                raise ValueError("Conflicting duplicate item ID.")
            items[item_id] = item
        except (ValueError, KeyError, TypeError) as exc:
            rejects.append({"item_id": item_id, "reason": str(exc)})
    for item_id in conflicts:
        items.pop(item_id, None)
    if not items:
        raise ValueError("No valid menu cards found. Do not treat this as an empty menu.")
    return list(items.values()), rejects, len(cards)


PARSERS = {"ubereats": parse_menu}
