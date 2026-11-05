# Recorded spending summary

`may_spending_summary(vehicle_id, start_date=null, end_date=null)` is always
read-only. Optional dates must be valid `YYYY-MM-DD` values; both bounds are
inclusive and a reversed range is rejected before HTTP. Vehicle IDs must be
positive integers excluding booleans and numeric strings.

The summary uses only recorded fuel `total_cost`, expense `cost`, and charging
`total_cost`. It never derives missing totals from volume/energy and unit prices,
or adds included sales tax again. The aggregation helper uses Decimal arithmetic,
keeps verified currencies separate, and returns amounts as exact decimal strings
with at least two decimal places. Additional recorded decimal places are retained.
No consumption, distance/hours totals or private notes appear in the result.

## Currency limitation in May 0.44.2

The inspected public REST contract exposes neither a currency on these records
nor a supported account-currency endpoint. Although May has an account currency
internally, the MCP server cannot verify it through this API. It does not assume
EUR, scrape web sessions or trust undocumented currency fields.

Consequently, current real-May records produce `currency_status="unknown"`,
`currency_source=null`, empty monetary `totals`, and an `unknown_currency`
exclusion for each matching record. `complete=false` when matching records are
excluded. This does **not** mean no spending was recorded. A supported upstream
currency source is an integration gap that must be resolved before verified
real-May monetary totals can be offered. Exact mixed-currency aggregation is
tested with explicit verified synthetic currency inputs at the helper boundary.

Exclusions contain only source, numeric record ID and reason codes. Missing or
invalid totals and invalid dates are also excluded. `counts` counts included
monetary records, while `coverage` reports retrieved rows independently. An empty
matching history may be complete even though the account currency is unknown.

## Coverage

Each source starts at offset zero and is traversed in ascending order with pages
of 100 records, up to 100 pages (10,000 rows per source). The internal collector
also accepts bounded page sizes up to May's maximum of 500. Exhausting the page
budget returns incomplete coverage with reason `page_limit`; a partial subtotal
must not be presented as a complete total.

Inconsistent totals, missing/repeated IDs, missing rows, malformed metadata and
unexpected offsets fail safely instead of reporting a complete history. Each
page is an API snapshot; traversal is not an atomic transaction, and concurrent
changes that do not alter detectable IDs/counts may be invisible. Date filtering
is local after bounded collection, so coverage can be incomplete even for a
narrow requested range. Upstream access errors remain safe MCP errors.
