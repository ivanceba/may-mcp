# Fuel logs

Fuel tools target May 0.44.2's public REST API and use the same
[configuration and write guard](development/client.md) as vehicle tools.

`may_list_fuel_logs(vehicle_id, limit=100, offset=0, sort="desc")` returns the
upstream `fuel_logs`, `total`, `count`, `limit`, and `offset`, plus `has_more` and
`complete`. The limit must be an integer from 1 to 500; offset must be a
nonnegative integer; sort is `asc` or `desc`, ordered by date then odometer.
IDs are positive integers. Booleans and numeric strings are not integer inputs.

For three matching logs and limit two, offset zero has `has_more=true` and
`complete=false`. Offset two has `has_more=false` and `complete=false`, since
earlier rows are absent. Only a page starting at zero and covering all matching
rows is complete. An empty history at offset zero is complete. Inconsistent
upstream metadata returns a safe error instead of claiming coverage. Pages are
individual API snapshots, not a transaction across multiple requests.

`may_get_fuel_log(log_id)` preserves upstream fields including `odometer`,
`odometer_confirmed`, `sales_tax`, and `consumption`. The server does not derive
consumption or totals from a partial page or substitute unknown readings with
confirmed zero. May itself may compute per-record consumption using its database
history; that returned value is retained.

When writes are enabled:

- `may_create_fuel_log(vehicle_id, fuel)` requires `date` (`YYYY-MM-DD`, a valid
  calendar date) and `odometer` greater than zero. May's POST endpoint rejects
  zero or unknown readings. To record confirmed zero or an unknown reading,
  use the update operation on an existing log.
- `may_update_fuel_log(log_id, changes)` sends only supplied fields from a
  nonempty object. Omitted fields remain unchanged. `odometer: null` marks the
  reading unknown; `odometer: 0` confirms zero. Supported readings are finite
  numbers between zero and 9,999,999; creation requires a nonzero value.
- `may_delete_fuel_log(log_id)` permanently deletes the record and attachments.

Optional create/update fields are `volume`, `price_per_unit`, `total_cost`,
`sales_tax`, `fuel_type`, `fuel_distance`, `is_full_tank`, `is_missed`, `station`,
and `notes`. Numbers must be finite and nonnegative. Dates and booleans cannot be
null. Other optional fields can be sent as null. Unknown fields are rejected;
read-only fields such as `consumption`, `odometer_confirmed`, and the currently
unsupported REST write field `discount_per_unit` cannot be submitted. Omitted
booleans use May's defaults (`is_full_tank=true`, `is_missed=false`) on creation.

Payloads retain zero, false and null, but May normalizes zero optional numeric
values to null. POST may also calculate a total when it is absent or zero.
An empty/null fuel type falls back to the vehicle's fuel type in responses.
Returned fields reflect saved upstream behavior; do not assume every sent zero
or null is stored verbatim. A positive supplied tax and total round-trip.

May allows fuel mutation for vehicles accessible to the account, including
shared vehicles; this differs from owner-only vehicle update/delete. Creation
is non-destructive and non-idempotent; update/delete are destructive and
idempotent in effect. A repeat delete returns `not_found`. No mutation is retried
automatically. Verify state after an uncertain outcome before repeating it.
Disabling writes hides all three tools and the HTTP layer independently rejects
mutations before network access.
