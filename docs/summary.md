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

## Currency source in May 0.44.2

The v1 record API has no currency field. The documented Home Assistant Bearer
API does: `GET /api/ha/vehicles/{vehicle_id}` returns the configured account's
`currency` for an owned vehicle. The summary validates the returned vehicle ID
and a three-letter uppercase currency, reports `currency_status="verified_account"`
and the endpoint as `currency_source`, and interprets recorded numeric amounts
in that account's current monetary context. It uses no web session or database
bypass and ignores undocumented per-record currency extras.

This is account-context currency, not independently verified historical transaction
currency. The pinned schema does not retain a currency per record; the summary
does not perform foreign-exchange conversion or prove that amounts entered by
different contributors originally used the same currency. Exact mixed-currency
aggregation is tested separately with explicit verified synthetic currency inputs.

The Home Assistant metadata endpoint requires ownership, while v1 record reads
allow shared access. For a shared-only vehicle, an absent endpoint, or unusable
currency metadata, the result reports `currency_status="unknown"`,
`currency_source=null`, empty monetary totals and `unknown_currency` exclusions
for matching records. Matching exclusions make `complete=false`; they do not
mean zero spending. Other upstream authentication/network failures remain errors.

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
