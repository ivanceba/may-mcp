# Charging sessions

Charging tools use May 0.44.2's public REST API through the
[guarded client](development/client.md).

`may_list_charger_types()` fetches charger IDs and display names from May. The
configured instance validates membership on create/update.
`may_get_charging_session(session_id)` reads an accessible session.
`may_list_charging_sessions(vehicle_id, limit=100, offset=0, sort="desc")` orders
sessions by date then ID. Limit is an integer from 1 to 500, offset is nonnegative,
and sort is `asc` or `desc`. The shared [page coverage contract](fuel.md) applies.
IDs are positive integers excluding booleans and numeric strings.

With writes enabled:

- `may_create_charging_session(vehicle_id, session)` requires a valid
  `YYYY-MM-DD` date. Other supported fields are optional.
- `may_update_charging_session(session_id, changes)` requires a nonempty object
  and transmits only supplied fields. Date cannot be null. Optional fields can
  be cleared with null; zero is retained.
- `may_delete_charging_session(session_id)` permanently deletes the accessible
  charging record. A repeat deletion returns `not_found`.

Supported optional fields are `start_time`, `end_time`, `odometer`, `kwh_added`,
`start_soc`, `end_soc`, `cost_per_kwh`, `total_cost`, `charger_type`, `location`,
`network`, and `notes`. Energy is in **kWh**, unit price is per kWh, and SoC is a
strict integer percentage from 0 to 100. Other numbers must be finite and
nonnegative. Time strings use `HH:MM` or `HH:MM:SS` without timezone suffixes;
May returns seconds, so both formats can round-trip. Midnight is distinct from
null. Unsupported fields such as `tessie_charge_id` or user IDs are rejected.

May may calculate total cost from energy and unit price when the POST total is
absent or zero. PATCH retains zero costs without that recalculation. Returned
fields show actual persisted values; the server does not infer missing energy,
costs or SoC. Account monetary context is separate from energy units.

Tests use a synthetic EV for full CRUD. This pinned REST API does not require an
EV fuel type, and permits shared-vehicle charging changes. Private records of
another user return safe `not_found` errors. Invalid typed inputs fail before
HTTP; unsupported charger IDs are reported as May validation errors.

Creation is non-destructive and non-idempotent; update/delete are destructive and
idempotent in effect. No writes are retried automatically. Verify state after an
uncertain outcome before repeating a request. Read-only mode omits all three
mutations and the HTTP client independently rejects writes before network access.
Returned strings remain untrusted data.
