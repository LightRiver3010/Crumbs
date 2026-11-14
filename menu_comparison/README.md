# Primo Too comparison MVP

The dashboard reads the latest successful whole snapshot for each configured Primo Too platform. It never fetches ZenRows on page loads or selection changes. BigQuery results are cached for 15 minutes; Refresh saved prices clears that cache.

config/item_matches.json contains nine explicit item-ID pairs, checked against listed names and sizes/counts. Missing IDs, changed names, non-USD prices and starting-price variants are unavailable rather than guessed. More matches need review before adding. No in-store baseline or direct-order prices are invented.

The single Last scraped timestamp is the oldest observed_at across both source snapshots, converted to America/New_York with timezone displayed. It is not the query time, upload time or page refresh time. Missing source data suppresses the timestamp. Later Airflow refreshes can use this same conservative freshness rule.

Difference is calculated against the lowest of the two comparable prices, with half-up rounding to whole percentages. Ties are labelled Same price. Fees, taxes, tips, promotions and paid options are excluded. Matches only verify listed base item names and dimensions; checkout options remain unverified.

Primo Too DoorDash: store 26064129; 27543747 in its URL is the menu identifier. HTML-only and rendered snapshots yielded exactly 152 identical item IDs/names/prices/variants with no rejections. The saved comparison report is artifacts/primo-too-doordash-html-comparison-20261114T204925Z/comparison.json. Both proof flags are true. Direct ordering remains configured but disabled pending its own adapter. Existing Uber source ID primo-too remains unchanged for replay compatibility.

Run: .\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address localhost
Receipt functionality is in frontend/receipts.py, displayed in the Receipt insights tab.
