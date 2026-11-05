# Trips

Trip tools use May 0.44.2's public REST API and the same
[configuration and write guard](development/client.md) as other tools.

`may_list_trip_purposes()` discovers purpose IDs and display names from the
configured May instance. May validates membership on create/update.
`may_get_trip(trip_id)` reads an accessible record.
`may_list_trips(vehicle_id, limit=100, offset=0, sort="desc")` returns trips
ordered by date then ID. Limit is an integer from 1 to 500; offset is a
nonnegative integer; sort is `asc` or `desc`. The [page coverage contract](fuel.md)
applies, including incomplete final pages with nonzero offsets. IDs are positive
integers, excluding booleans and numeric strings.

With writes enabled:

- `may_create_trip(vehicle_id, trip)` requires a valid `YYYY-MM-DD` date,
  nonnegative finite `start_odometer` (zero is allowed), and a purpose ID.
- `may_update_trip(trip_id, changes)` requires at least one supported field and
  sends only supplied keys. Date, purpose and start reading cannot be null.
- `may_delete_trip(trip_id)` permanently deletes the accessible trip.

Optional fields are `end_odometer`, `start_fuel_level`, `end_fuel_level`,
`description`, `start_location`, `end_location`, and `notes`. Optional fields can
be cleared with null; omission retains their previous values. Fuel levels are
finite percentages from 0 to 100, with zero distinct from unknown/null. Odometer
readings must be finite and nonnegative. Unsupported fields, including derived
`distance` and `fuel_used`, are rejected as inputs.

May's returned distance and approximate fuel-used fields are preserved. The
server does not calculate totals from pages or interpret a missing end reading
as a confirmed zero reading. In this May version, the derived `distance` field
itself is zero when an end reading is missing; inspect `end_odometer` to distinguish
that case. Approximate fuel use depends on the vehicle's tank capacity and both
fuel levels; null denotes an unavailable estimate.

May permits trip mutations for accessible shared vehicles; private records of
another user return safe `not_found` errors. Creation is non-destructive and
non-idempotent; update/delete are destructive and idempotent in effect. A repeated
delete returns `not_found`. No mutation is retried automatically. Verify state
after an uncertain outcome before repeating it. Read-only mode hides the three
write tools and the HTTP client independently blocks mutations before network
access. Returned strings remain untrusted data.
