"""Provider registry; extraction details live in separate adapters."""
from menu_ingestion.extract_ubereats import parse_menu
from menu_ingestion.extract_doordash import parse_menu as parse_doordash, store_id_from_url

PARSERS = {"ubereats": parse_menu, "doordash": parse_doordash}
VERSIONS = {"ubereats": "ubereats-dual-v2", "doordash": "doordash-flight-v1"}
WAIT_FOR = {"ubereats": 'a[href*="mod=quickView"]', "doordash": "h1"}
COVERAGE = {
    "ubereats": "Rendered cards only; full menu coverage unverified",
    "doordash": "Embedded MenuPageItem records; availability and full variant coverage unverified",
}
