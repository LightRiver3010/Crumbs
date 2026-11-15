"""Restaurant-wide menus with conservative, explicit cross-platform matching."""
from collections import defaultdict
import json
import re
import unicodedata

from shared.paths import ROOT

PROVIDERS = {"ubereats": "Uber Eats", "doordash": "DoorDash"}


def restaurants(sources):
    grouped = {}
    for source in sources:
        grouped.setdefault(source["restaurant_id"], []).append(source)
    return grouped


def restaurant_label(sources):
    location = sources[0]["restaurant_id"].rsplit("-", 1)[-1].title()
    name = re.sub(r"\s+", " ", sources[0]["expected_heading"]).strip()
    return name if name.casefold().endswith(location.casefold()) else f'{name} · {location}'


def name_key(name):
    # Keep size, count and punctuation: no fuzzy matching or size guessing.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", name or "")).strip().casefold()


def valid_price(row):
    return row is not None and type(row.get("price_cents")) is int and row["price_cents"] >= 0 and row.get("currency") == "USD"


def comparable(entries):
    return (all(valid_price(entries.get(provider)) and not entries[provider].get("variant")
                for provider in PROVIDERS)
            and len({entries[p].get("fulfillment_mode", "DELIVERY") for p in PROVIDERS}) == 1)


def restaurant_items(sources, menus):
    """Curated IDs first; then unique identical names within this restaurant only.

    Every remaining listing is retained separately. Ambiguous duplicates and
    starting prices never receive savings claims.
    """
    if not sources:
        return []
    rows = defaultdict(list)
    for source in sources:
        for original in menus.get(source["id"], []):
            row = dict(original)
            row.setdefault("fulfillment_mode", source.get("fulfillment_mode", "DELIVERY"))
            rows[source["provider"]].append(row)
    used = set()
    result = []
    curated = json.loads((ROOT / "config/item_matches.json").read_text())
    if curated["restaurant_id"] == sources[0]["restaurant_id"]:
        for match in curated["items"]:
            entries = {}
            for provider, target in match["sources"].items():
                candidates = [r for r in rows[provider] if r.get("source_item_id") == target["item_id"]]
                if len(candidates) == 1 and candidates[0].get("item_name") == target["expected_name"]:
                    entries[provider] = candidates[0]
                    used.add((provider, id(candidates[0])))
            if entries:
                result.append({"name": match["name"], "category": match["category"],
                               "entries": entries, "basis": "Reviewed item and size/count match",
                               "comparable": comparable(entries)})
    groups = defaultdict(lambda: defaultdict(list))
    for provider, listings in rows.items():
        for row in listings:
            if (provider, id(row)) not in used:
                groups[name_key(row.get("item_name"))][provider].append(row)
    for key, platforms in groups.items():
        if key and all(len(platforms.get(p, [])) == 1 for p in PROVIDERS):
            entries = {p: platforms[p][0] for p in PROVIDERS}
            result.append({"name": entries["ubereats"]["item_name"], "category": "Other menu items",
                           "entries": entries, "basis": "Exact listed name; options unverified",
                           "comparable": comparable(entries)})
        else:
            for provider, listings in platforms.items():
                for row in listings:
                    result.append({"name": row.get("item_name") or "Unnamed item",
                                   "category": "Other menu items", "entries": {provider: row},
                                   "basis": "No unique matching listing", "comparable": False})
    return sorted(result, key=lambda item: (not item["comparable"], name_key(item["name"])))


def price_label(row):
    if not valid_price(row):
        return "Unavailable"
    return f'${row["price_cents"]/100:.2f}' + ("+" if row.get("variant") else "")


def table_rows(items):
    output = []
    for item in items:
        entries = item["entries"]
        difference = "Not comparable"
        if item["comparable"]:
            uber, door = (entries[p]["price_cents"] for p in PROVIDERS)
            difference = ("Same price" if uber == door else
                          f'{"Uber Eats" if uber < door else "DoorDash"} saves ${abs(uber-door)/100:.2f}')
        notes = item["basis"]
        if any(row.get("variant") for row in entries.values()):
            notes += "; starting price/options unverified"
        output.append({"Item": item["name"],
                       **{label: price_label(entries.get(p)) for p, label in PROVIDERS.items()},
                       "Comparison": difference, "Details": notes})
    return output
