# Local stdio server

Install the locked [development environment](../README.md#development-setup).
Set the variables documented in [the HTTP guide](development/client.md) in the
environment of the process that launches the server. The server does not load
`.env` automatically.

From the repository root, the executable is:

```sh
uv run --frozen may-mcp
```

`python -m may_mcp` is an equivalent launch when using the installed project
environment. The command waits for MCP messages on stdin; it is not an HTTP
endpoint or an interactive shell. Protocol output goes to stdout, logs and
configuration errors go to stderr. Invalid configuration exits with status 2
without printing supplied credentials.

A local MCP client needs the following process launch values, expressed here as
generic data rather than a client-specific configuration format:

```json
{
  "command": "uv",
  "args": ["--directory", "/absolute/path/to/may-mcp", "run", "--frozen", "may-mcp"],
  "env": {
    "MAY_BASE_URL": "https://may.example.invalid",
    "MAY_API_KEY": "replace-with-your-may-api-key",
    "MAY_MCP_ALLOW_WRITES": "false"
  }
}
```

Replace the clone path, instance URL and key locally; keep real credentials out
of Git. Map these launch values to your client's supported configuration.
ChatGPT remote access and specific Codex/Claude connection verification belong
to later integration tasks and are not demonstrated by this example.

The default read-only catalogue contains thirteen tools:

- `may_list_vehicles()`: all vehicles the configured May account can access,
  with the API's `vehicles` array and `count`.
- `may_get_vehicle(vehicle_id)`: one accessible vehicle. The ID must be a
  positive integer; zero, negative values, booleans and numeric strings fail
  validation before any upstream request.

- `may_list_fuel_logs(vehicle_id, limit=100, offset=0, sort="desc")`: a bounded
  page with truthful coverage metadata.
- `may_get_fuel_log(log_id)`: one accessible fuel log.
- `may_list_expenses(vehicle_id, limit=100, offset=0, sort="desc")`,
  `may_get_expense(expense_id)`, and `may_list_categories()`: expense reads and
  live category discovery.
- `may_list_trips(vehicle_id, limit=100, offset=0, sort="desc")`,
  `may_get_trip(trip_id)`, and `may_list_trip_purposes()`: trip reads and live
  purpose discovery.
- `may_list_charging_sessions(vehicle_id, limit=100, offset=0, sort="desc")`,
  `may_get_charging_session(session_id)`, and `may_list_charger_types()`: charging
  reads and live charger discovery.

These tools declare read-only, non-destructive, idempotent behavior and external
data access. Returned vehicle fields are untrusted data. May failures become
safe tool errors with the HTTP boundary's code; errors do not close the MCP
connection. The server lifespan closes its May HTTP client, including an injected
client, on shutdown.

With `MAY_MCP_ALLOW_WRITES=true`, fifteen additional tools are registered:

- `may_create_vehicle(vehicle)`: requires `name` and `vehicle_type` (`car`, `van`,
  `motorbike`, or `scooter`). Optional fields are `make`, `model`, `year`,
  `registration`, `vin`, `fuel_type`, and `tank_capacity`. Omitted fields retain
  upstream defaults. Creation is non-destructive and non-idempotent.
- `may_update_vehicle(vehicle_id, changes)`: a nonempty object containing any of
  those fields, plus `is_active`. Only supplied fields are sent in PATCH. Nullable
  fields can be cleared with `null`; zero and false are retained. Name, vehicle
  type and active status cannot be null. Updates are destructive and idempotent.
- `may_delete_vehicle(vehicle_id)`: permanently removes an owned vehicle. May
  cascades deletion to associated records, including fuel logs, expenses,
  attachments, specifications, trips, charging sessions, and vehicle parts.
  Deletion is destructive and idempotent in its effect; a repeated delete returns
  `not_found` rather than another success response.
- `may_create_fuel_log(vehicle_id, fuel)`, `may_update_fuel_log(log_id, changes)`,
  `may_delete_fuel_log(log_id)`: explicit fuel CRUD. See the [fuel guide](fuel.md)
  for fields, odometer semantics and the pinned API's normalization behavior.
- `may_create_expense(vehicle_id, expense)`, `may_update_expense(expense_id, changes)`,
  `may_delete_expense(expense_id)`: expense CRUD. See [expenses](expenses.md) for
  supported fields, amount semantics and shared access.
- `may_create_trip(vehicle_id, trip)`, `may_update_trip(trip_id, changes)`, and
  `may_delete_trip(trip_id)`: see [trips](trips.md) for readings, optional fuel
  levels, purpose validation and shared access.
- `may_create_charging_session(vehicle_id, session)`,
  `may_update_charging_session(session_id, changes)`, and
  `may_delete_charging_session(session_id)`: see [charging](charging.md) for kWh,
  costs, SoC percentages and time formats.

All writes declare external data access, use explicit typed fields and reject
unknown fields in the vehicle/changes object. IDs must be positive integers.
May 0.44.2 permits shared reads but requires ownership for vehicle update/delete;
these tools preserve its permission errors. May's supported REST fields are a
subset of its web application's vehicle fields.

For example, `may_update_vehicle` accepts
`{"vehicle_id": 1, "changes": {"make": null, "tank_capacity": 0, "is_active": false}}`.
The name and model remain unchanged. No mutation is retried automatically;
verify saved state after an uncertain outcome before repeating a request.
Disabling writes removes these tools on reconnect and the HTTP client also
blocks mutations before any network request.
There is no remote HTTP transport or consumer authorization in this delivery.

The locked official MCP SDK is used for both the server and test client. Protocol
tests force JSON-RPC framing in memory; the real-May integration separately
spawns and shuts down the actual stdio process, tests list/detail and checks that
a missing-record error leaves subsequent calls usable. See [testing](development/testing.md).
