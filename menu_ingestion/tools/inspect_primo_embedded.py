"""Inspect a saved no-JS comparison response; no network requests or warehouse writes."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote
from bs4 import BeautifulSoup

folder = Path(sys.argv[1])
soup = BeautifulSoup((folder / "response.html").read_text(encoding="utf-8"), "html.parser")
encoded = soup.select_one("script#__REACT_QUERY_STATE__").get_text().strip()
decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), unquote(encoded))
state = json.loads(decoded)
items = {}
def walk(value):
    if isinstance(value, dict):
        if all(k in value for k in ("uuid", "title", "price")):
            items.setdefault(value["uuid"], set()).add((value["title"], value["price"]))
        for child in value.values():
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)
walk(state)
baseline = json.loads((folder / "baseline.json").read_text(encoding="utf-8"))
expected = {r["source_item_id"]: (r["item_name"], r["price_cents"]) for r in baseline}
result = {
    "warehouse_items": len(expected), "embedded_unique_ids": len(items),
    "missing": sorted(expected.keys() - items.keys()),
    "extra_ids": sorted(items.keys() - expected.keys()),
    "differences": [k for k in expected.keys() & items.keys() if expected[k] not in items[k]],
    "conflicts": [k for k,v in items.items() if len(v)>1],
}
report = json.loads((folder / "comparison.json").read_text(encoding="utf-8"))
report["embedded_comparison"] = result
(folder / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))

