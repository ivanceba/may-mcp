# May capability coverage

Inspected version: **May 0.44.2**, on 2026-11-05. The disposable runtime is pinned
by digest in [compose.test.yml](../compose.test.yml). Inspection covers all 19
blueprints registered by [May's application factory](https://github.com/dannymcc/may/blob/v0.44.2/app/__init__.py).
See the [upstream contract](development/upstream-contract.md) for authentication,
field subsets and verification limits.

This is partial delivery of [#13](https://github.com/ivanceba/may-mcp/issues/13),
which remains open. No unimplemented capability is excluded by default. Full
integration also requires remote authorization, deployment and named client checks.

## Implemented and tested

Default read-only mode exposes **14 tools**; enabling writes adds **15 mutations**,
for 29 tools total. All mutations use the guarded client without automatic retries.
The following capabilities have offline and disposable real-May tests, independently
of production or named consumer verification:

- **Vehicles:** `may_list_vehicles`, `may_get_vehicle`, `may_create_vehicle`,
  `may_update_vehicle`, `may_delete_vehicle`. REST collection `/api/v1/vehicles`
  and detail `/api/v1/vehicles/{id}`. Owned/shared reads; owner-only update/delete.
  Supported REST fields/types are narrower than the web UI.
  [Delivery PR](https://github.com/ivanceba/may-mcp/pull/22).
- **Fuel:** `may_list_fuel_logs`, `may_get_fuel_log`, `may_create_fuel_log`,
  `may_update_fuel_log`, `may_delete_fuel_log`. Collection
  `/api/v1/vehicles/{id}/fuel`, detail `/api/v1/fuel/{id}`.
  [Fields](fuel.md), [delivery PR](https://github.com/ivanceba/may-mcp/pull/23).
- **Expenses:** `may_list_expenses`, `may_get_expense`, `may_create_expense`,
  `may_update_expense`, `may_delete_expense`, `may_list_categories`. Collection
  `/api/v1/vehicles/{id}/expenses`, detail `/api/v1/expenses/{id}` and
  `/api/v1/categories`. [Fields](expenses.md),
  [delivery PR](https://github.com/ivanceba/may-mcp/pull/24).
- **Trips:** `may_list_trips`, `may_get_trip`, `may_create_trip`,
  `may_update_trip`, `may_delete_trip`, `may_list_trip_purposes`. Collection
  `/api/v1/vehicles/{id}/trips`, detail `/api/v1/trips/{id}` and
  `/api/v1/trip-purposes`. [Fields](trips.md),
  [delivery PR](https://github.com/ivanceba/may-mcp/pull/25).
- **Charging:** `may_list_charging_sessions`, `may_get_charging_session`,
  `may_create_charging_session`, `may_update_charging_session`,
  `may_delete_charging_session`, `may_list_charger_types`. Collection
  `/api/v1/vehicles/{id}/charging`, detail `/api/v1/charging/{id}` and
  `/api/v1/charger-types`. [Units and fields](charging.md),
  [delivery PR](https://github.com/ivanceba/may-mcp/pull/26).
- **Recorded spending:** `may_spending_summary` traverses the three monetary
  collections with bounds/checks and uses Decimal recorded totals.
  `/api/ha/vehicles/{id}` supplies configured-account currency for owned vehicles.
  Shared-only metadata absence produces unknown-currency exclusions.
  [Semantics](summary.md), [delivery PR](https://github.com/ivanceba/may-mcp/pull/27).

Versioned operations are in [api.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/api.py).
Fuel, expense, trip and charging mutations permit accessible shared vehicles,
subject to May's role enforcement. Current real tests use two synthetic editor
accounts; they do not prove every role combination.

## Requested capabilities still unresolved

- **Maintenance and service history:** [maintenance.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/maintenance.py#L35)
  provides session-based history/list/new/edit/complete/delete. History combines
  MaintenanceEvent records and legacy maintenance expenses; completion can create
  an expense. No equivalent Bearer CRUD contract. HA alerts are a due subset,
  without full history or stable schedule IDs.
  [Follow-up #28](https://github.com/ivanceba/may-mcp/issues/28).
- **Reminders:** [reminders.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/reminders.py#L12)
  provides session-based CRUD, completion/uncompletion and recurrence generation.
  HA alerts only exposes overdue/upcoming subsets.
  [Follow-up #29](https://github.com/ivanceba/may-mcp/issues/29).
- **Documents:** [documents.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/documents.py#L20)
  provides session-based metadata, upload/download and deletion. HA expiry alerts
  are not document CRUD or authenticated file access. The JSON client does not
  implement file transfer. [Follow-up #30](https://github.com/ivanceba/may-mcp/issues/30).

These propose a separate May API scope. No upstream code change, form scraping,
database bypass or production operation occurred. Implementation or explicit
exclusion is required before #13 can close.

## Other machine-facing surfaces

[Home Assistant](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/homeassistant.py)
uses the same API-key Bearer authentication under `/api/ha`:

- `GET /status`: authenticated user/version/status; no MCP tool.
- `GET /vehicles` and `/vehicles/{id}`: owned-vehicle metadata, units and account
  currency. Only detail currency resolution is used by current MCP tools.
- `GET /vehicles/{id}/stats` and `/summary`: upstream-derived owned-vehicle
  statistics; not used as MCP spending totals or consumption calculations.
- `GET /alerts`: due maintenance, recurring-expense, document-expiry and reminder
  summaries for owned vehicles. It is not a complete record catalogue; vehicle
  names are not stable identifiers. No MCP tool yet.
  [Read-only follow-up #31](https://github.com/ivanceba/may-mcp/issues/31).
- `POST /fuel/add`: an alternative owned-vehicle fuel operation; MCP uses v1.

Owner-only currency is unavailable for a shared-only requested vehicle.
[#32](https://github.com/ivanceba/may-mcp/issues/32) proposes clarifying shared/account
currency access without inventing historical transaction currency or FX conversion.

[Calendar](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/calendar.py#L122)
exposes `/api/calendar/feed` and `/feed.ics`, authenticates by query token and
returns owned-vehicle iCalendar events. This is not metadata CRUD or the JSON/
Bearer boundary used by MCP; no calendar tool exists.

`POST /api/reminders/process` accepts a valid Bearer user, admin session or
configured internal token and triggers app-wide notifications. It is not reminder
CRUD, is not called by MCP and was not exercised by this work.

## Web-only areas awaiting a release-scope decision

Each area below exists upstream but has no complete MCP capability. These remain
unresolved, not implicitly excluded. Decide scope in
[#33](https://github.com/ivanceba/may-mcp/issues/33); approved implementations need
focused contract tests and, where necessary, a separately approved May API.

- [vehicles.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/vehicles.py):
  extended fields/types, specifications, photos, parts, sharing/unsharing,
  archiving and reports beyond the core REST field subset.
- [fuel.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/fuel.py) and
  [expenses.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/expenses.py):
  attachments and web extras/quick entry beyond covered core records.
- [trips.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/trips.py):
  templates and reports. [charging.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/charging.py)
  also has web forms beyond the covered core REST contract.
- [recurring.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/recurring.py):
  recurring-expense CRUD, generation and activation.
- [notes.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/notes.py): notes CRUD.
- [tires.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/tires.py):
  tire sets, fitting/removal and fitment history.
- [stations.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/stations.py):
  stations, favorites, prices, refresh and cheapest views. Even `/stations/api/list`
  requires a web session.
- [allowance.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/allowance.py): mileage allowances.
- [search.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/search.py): session-authenticated search.
- [main.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/main.py):
  dashboard/timeline and public app/offline/service-worker views.
- [auth.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/auth.py):
  login/recovery, preferences, user administration and integration settings.
- [api.py](https://github.com/dannymcc/may/blob/v0.44.2/app/routes/api.py):
  session-based DVLA/Tessie, CSV/JSON exports, backups/imports, internal vehicle
  stats and API-key management. Public uploads serve branding/static files and
  are not a substitute for authenticated document access.

The application factory separately registers public `/health`, used by the
disposable health check. Its success is not MCP or client-interoperability proof.

## Evidence and remaining checks

Latest functional baseline: [PR #27](https://github.com/ivanceba/may-mcp/pull/27),
297 Windows offline and 312 full Linux/WSL tests including disposable May, with
all five CI jobs green and independent review without blockers. No production
writes were used. Source inspection is not runtime proof of extra operations.

Remote OAuth/HTTP, containers and actual ChatGPT/Codex/identified-Claude checks
remain [#14](https://github.com/ivanceba/may-mcp/issues/14),
[#15](https://github.com/ivanceba/may-mcp/issues/15) and
[#16](https://github.com/ivanceba/may-mcp/issues/16). Native fresh-session Ponytail
discovery from #3 also remains unverified. The
[delivery tracker](https://github.com/ivanceba/may-mcp/issues/1) records completed
merges and explicit unresolved limitations.
