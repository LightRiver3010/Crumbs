"""Item slides with verified comparisons and a self-contained accessible carousel."""
from html import escape
from pathlib import Path

from menu_comparison.restaurant import restaurants, restaurant_items, restaurant_label

PROVIDERS = {"ubereats": "Uber Eats", "doordash": "DoorDash"}


def featured_items(sources, menus):
    # Round-robin restaurants so one large menu cannot dominate the landing page.
    groups = []
    for restaurant_sources in restaurants(sources).values():
        groups.append([
            {"name": item["name"], "restaurant": restaurant_label(restaurant_sources),
             "prices": [{"label": label, "price_cents": item["entries"][provider]["price_cents"]}
                        for provider, label in PROVIDERS.items()],
             "note": item["basis"], "emoji": "\U0001f37d\ufe0f"}
            for item in restaurant_items(restaurant_sources, menus) if item["comparable"]
        ])
    slides = []
    while any(groups) and len(slides) < 15:
        for group in groups:
            if group and len(slides) < 15:
                slides.append(group.pop(0))
    return slides


def carousel_html(slides):
    cards = []
    for index, slide in enumerate(slides):
        valid = [row["price_cents"] for row in slide["prices"] if row["price_cents"] is not None]
        lines = ['<div class="price-row muted"><span>Direct delivery</span><span>Unavailable</span></div>']
        for row in slide["prices"]:
            price = row["price_cents"]
            tone, delta = "", ""
            if price is not None and len(valid) == 2:
                difference = price - (sum(valid) - price)
                tone = "higher" if difference > 0 else "lower" if difference < 0 else ""
                delta = (f'{"+" if difference > 0 else "−"}${abs(difference)/100:.2f} vs other app'
                         if difference else "Same price")
            amount = f"${price/100:.2f}" if price is not None else "Unavailable"
            lines.append(f'<div class="price-row {tone}"><span>{escape(row["label"])}</span>'
                         f'<div><strong>{amount}</strong><small>{delta}</small></div></div>')
        cards.append(f'<article class="slide" role="group" aria-roledescription="slide" aria-label="{index+1} of {len(slides)}">'
                     f'<div class="emoji" aria-hidden="true">{escape(slide["emoji"])}</div>'
                     f'<h2>{escape(slide["name"])}</h2><p class="restaurant">{escape(slide["restaurant"])}</p>'
                     + "".join(lines) + f'<p class="note">{escape(slide["note"])}</p></article>')
    dots = "".join(f'<button class="dot" aria-label="Show item {i+1}" data-index="{i}" aria-current="{str(i == 0).lower()}"></button>' for i in range(len(slides)))
    template = Path(__file__).with_name("item_carousel.html").read_text(encoding="utf-8")
    return template.replace("<!--CARDS-->", "".join(cards)).replace("<!--DOTS-->", dots)
