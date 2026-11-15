"""Website-specific adapters. Add new providers here after validating their HTML."""
from decimal import Decimal
import json
import re
import uuid
from urllib.parse import parse_qs, unquote, urlsplit
from bs4 import BeautifulSoup
PRICE = re.compile(r"^\$(\d[\d,]*\.\d{2})$")

def parse_rendered(html, store_id, expected_heading=None):
    """Only accept unambiguous visible card prices, never ratings or modifiers."""
    if not isinstance(store_id, str) or not store_id.strip():
        raise ValueError("store_id must be a nonempty string.")
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    soup = BeautifulSoup(text, "html.parser")
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
            if not isinstance(context, dict) or context.get("storeUuid") != store_id:
                raise ValueError("Missing or unexpected store ID.")
            item_id = str(uuid.UUID(context["itemUuid"]))
            texts = [s.get_text(" ", strip=True) for s in card.select('[data-testid="rich-text"]')]
            prices = [PRICE.fullmatch(t) for t in texts]
            prices = [p for p in prices if p]
            if texts and texts[0] and not prices and "Priced by add-ons" in texts[1:]:
                rejects.append({"item_id": item_id, "reason": "Priced by add-ons; no standalone displayed price", "severity": "excluded"})
                continue
            if not texts or not texts[0] or PRICE.fullmatch(texts[0]) or len(prices) != 1:
                raise ValueError("Missing or ambiguous name/price; requires manual review.")
            cents = int(Decimal(prices[0].group(1).replace(",", "")) * 100)
            if not 0 <= cents < 2**63:
                raise ValueError("Invalid nonnegative INT64 price.")
            category_heading = card.find_previous("h3")
            item = {
                "source_item_id": item_id, "item_name": texts[0],
                "price_cents": cents,
                "category": category_heading.get_text(" ", strip=True) if category_heading else None,
            }
            if item_id in items and any(items[item_id][k] != item[k] for k in ("item_name", "price_cents")):
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


def parse_html_only(html, store_id, expected_heading=None):
    """Read menu JSON already delivered in the HTML; execute no JavaScript."""
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    soup = BeautifulSoup(text, "html.parser")
    script = soup.select_one("script#__REACT_QUERY_STATE__")
    if not script:
        raise ValueError("Embedded Uber Eats menu state missing.")
    encoded = script.get_text().strip()
    try:
        state = json.loads(encoded)
    except json.JSONDecodeError:
        # Uber's HTML serializer percent-escapes backslashes and Unicode-escapes quotes.
        decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), unquote(encoded))
        state = json.loads(decoded)
    matches = []
    for query in state.get("queries", []):
        data = query.get("state", {}).get("data")
        if isinstance(data, dict) and data.get("uuid") == store_id and "catalogSectionsMap" in data:
            matches.append(data)
    if len(matches) != 1:
        raise ValueError("Expected one embedded menu matching store_id.")
    data = matches[0]
    if expected_heading and data.get("title", "").casefold() != expected_heading.casefold():
        raise ValueError("Unexpected embedded restaurant name.")
    items, rejects, conflicts = {}, [], set()
    count = 0
    for sections in data["catalogSectionsMap"].values():
        for section in sections:
            payload = section.get("payload", {}).get("standardItemsPayload", {})
            category = payload.get("title")
            if isinstance(category, dict):
                category = category.get("text")
            for record in payload.get("catalogItems", []):
                count += 1
                item_id = record.get("uuid")
                try:
                    item_id = str(uuid.UUID(item_id))
                    name, cents = record.get("title"), record.get("price")
                    if not isinstance(name, str) or not name.strip():
                        raise ValueError("Missing item name.")
                    if type(cents) is not int or not 0 < cents < 2**63:
                        raise ValueError("Invalid price cents.")
                    display = record.get("priceTagline", {}).get("text", "")
                    match = PRICE.fullmatch(display)
                    if not match or int(Decimal(match.group(1).replace(",", "")) * 100) != cents:
                        raise ValueError("Embedded price does not reconcile with displayed price.")
                    item = {"source_item_id":item_id, "item_name":name, "price_cents":cents, "category":category}
                    previous = items.get(item_id)
                    if previous and any(previous[k]!=item[k] for k in ("item_name", "price_cents")):
                        conflicts.add(item_id)
                        raise ValueError("Conflicting duplicate item.")
                    items[item_id] = item
                except (ValueError, KeyError, TypeError) as exc:
                    rejects.append({"item_id":item_id, "reason":str(exc)})
    for item_id in conflicts:
        items.pop(item_id, None)
    if not items:
        raise ValueError("No valid embedded menu items.")
    return list(items.values()), rejects, count


def parse_menu(html, store_id, expected_heading=None, *, html_only=False):
    if type(html_only) is not bool:
        raise ValueError("html_only must be a boolean.")
    if not isinstance(store_id, str) or not store_id.strip():
        raise ValueError("store_id must be a nonempty string.")
    parser = parse_html_only if html_only else parse_rendered
    return parser(html, store_id, expected_heading)
