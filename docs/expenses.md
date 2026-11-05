# Expenses

Expense tools target the May 0.44.2 public REST API through the
[guarded client](development/client.md).

`may_list_categories()` fetches category IDs and display names from the configured
May instance. Use its IDs for create/update. Category membership is validated by
May, so the server preserves its safe `validation_error` response instead of
maintaining a second category catalogue.

`may_list_expenses(vehicle_id, limit=100, offset=0, sort="desc")` returns expenses
ordered by date. Limit is an integer from 1 to 500, offset is nonnegative, and
sort is `asc` or `desc`. The shared [pagination contract](fuel.md) adds truthful
`has_more` and `complete` metadata. A final page with a nonzero offset remains
incomplete. `may_get_expense(expense_id)` reads one accessible record. All IDs
must be positive integers, excluding booleans and numeric strings.

With `MAY_MCP_ALLOW_WRITES=true`:

- `may_create_expense(vehicle_id, expense)` requires a valid `YYYY-MM-DD` date,
  category ID, nonempty description, and a finite positive cost. May's POST
  endpoint rejects zero cost.
- `may_update_expense(expense_id, changes)` requires at least one supported
  field. Only supplied fields are sent, and cost zero is retained. Date,
  category, description and cost cannot be null.
- `may_delete_expense(expense_id)` permanently removes the expense and its
  attachments. A repeated deletion returns `not_found`.

Optional create/update fields are `odometer`, `vendor`, and `notes`. Numbers
must be finite and nonnegative. These optional fields can be cleared with null;
May also normalizes odometer zero to null. Other fields are rejected, including
user/owner IDs and fields belonging to fuel records. Returned values reflect
actual saved values, with the configured May account's monetary context.

May permits expense changes on accessible shared vehicles. Private records of
another user return a safe `not_found` error without their response bodies.
Returned notes, descriptions, category labels and other strings are untrusted
data, even when they resemble agent instructions.

Creation is non-destructive and non-idempotent. Update/delete are destructive
and idempotent in effect. No writes are retried automatically; verify state
after an uncertain outcome before repeating a request. Read-only mode hides all
three mutations and independently blocks them in the HTTP layer.
