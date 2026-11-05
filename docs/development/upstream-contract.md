# Pinned upstream contract

Inspected May source: [v0.44.2](https://github.com/dannymcc/may/tree/v0.44.2),
2026-11-05. Runtime tests use the immutable image digest in
[compose.test.yml](../../compose.test.yml). See [capabilities](../capabilities.md)
for implemented operations and unresolved areas. Compatibility with another
release or complete May integration is not claimed.

## Inspection boundary

Read all 19 blueprint modules under `app/routes/` registered by the upstream
factory, plus `app/models.py`, `app/utils.py` and `app/permissions.py`. An `api`
path is not proof of API-key authentication: inspect its prefix, decorators,
return format, permission hooks and supplied-field behavior together.

The blueprints are main, auth, vehicles, fuel, expenses, api, reminders,
maintenance, documents, stations, recurring, homeassistant, calendar, trips,
charging, notes, allowance, search and tires. `/health` is registered separately.

## Authentication

- Versioned `/api/v1` in [api.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/api.py#L52)
  accepts Bearer or X-API-Key; MCP sends Bearer. It contains five CRUD families
  and category/purpose/charger lookups.
- [Home Assistant](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/homeassistant.py#L45)
  is a separate supported Bearer JSON API at `/api/ha`. Its metadata supplies
  account currency; its vehicle queries are owner-only, unlike shared v1 reads.
- [Calendar](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/calendar.py#L33)
  requires a query token and returns iCalendar; it is outside the JSON-only client.
- Other feature routes generally require Flask sessions and forms/templates/
  redirects, not Bearer CRUD. `/api/reminders/process` has separate Bearer/admin/
  internal-token checks and app-wide notification effects. Public branding
  uploads and `/health` are separate surfaces.

The global [permission hook](https://github.com/dannymcc/may/blob/v0.44.2/app/permissions.py)
resolves Bearer identities and role write scopes. MCP adds an independent write
guard; enabling it never grants upstream access. Current real tests use synthetic
editor accounts and ownership/sharing; all role combinations are not claimed.

## Implemented contract decisions

- REST vehicle types are car/van/motorbike/scooter despite larger web choices.
  POST accepts name/type, make/model/year, registration/VIN, fuel type and tank
  capacity; PATCH also accepts active status. Web extras are not silently sent.
- PATCH uses only supplied model fields, retaining omission versus null/0/false.
  Explicit invalid/null required values fail locally.
- Fuel POST rejects zero odometer; PATCH distinguishes unknown/null from
  confirmed zero. Optional numeric zero values become null in May.
- Expense POST rejects zero cost; PATCH retains cost zero but normalizes
  odometer zero to null. May validates membership using its category catalogue.
- Trips accept start zero and optional fuel percentages 0–100. Null readings
  remain distinct from zero. May's derived distance may be zero for a missing
  end reading; MCP does not reinterpret it as a confirmed reading.
- Charging uses kWh, integer SoC percentages and HH:MM or HH:MM:SS. Optional
  numeric null/zero values persist. May may calculate POST cost, but PATCH does
  not repeat that calculation for a supplied zero.
- Page limits are at most 500, with validated count/total/offset. Fuel orders by
  date/odometer, expenses by date, trips/charging by date/ID. A final page starting
  after zero is not complete history.
- Spending sums recorded totals with Decimal, excludes missing/invalid data,
  keeps currencies separate and never adds included tax again. Currency uses
  owner-only HA account metadata, not historical transaction currency or FX.
- Vehicle deletion cascades beyond the route comment's fuel/expense examples,
  including parts. Tool warnings use non-exhaustive examples. Runtime cascade
  coverage currently exercises a synthetic dependent fuel record.

## Evidence and separate May changes

HTTPX contracts, framed MCP, a real stdio subprocess and disposable persistence
are tested. Source inspection does not prove every additional endpoint at runtime,
all roles, production deployment or named consumer interoperability. See
[testing](testing.md) for isolation and cleanup.

Unsupported capabilities need a separately approved May API and repository/fork
scope, then failing behavior tests before implementation. No form scraping,
session cookies or direct database fallback. Proposed endpoints remain proposals
until implemented and verified. Keep [#13](https://github.com/ivanceba/may-mcp/issues/13)
open until requested gaps are implemented or exclusions explicitly agreed.
