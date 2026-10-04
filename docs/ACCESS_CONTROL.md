# Access Control

This is a single-company staff application. Roles control actions, not tenant
isolation or confidential-field visibility. All four roles can read quote,
customer and reporting data, including recorded costs.

| Action | Viewer | Staff | Manager | Admin |
|---|---|---|---|---|
| Read records and reports | Yes | Yes | Yes | Yes |
| Create quotes, revisions and customers | No | Yes | Yes | Yes |
| AI extraction and specification review | No | Yes | Yes | Yes |
| Update notes and non-financial outcomes | No | Yes | Yes | Yes |
| Download internal exports | No | Yes | Yes | Yes |
| Preview workbook imports | No | Yes | Yes | Yes |
| Change business status or financial fields | No | No | Yes | Yes |
| Set a manual back-drill fee | No | No | Yes | Yes |
| Generate formal exports | No | No | Yes | Yes |
| Confirm historical imports | No | No | Yes | Yes |
| Delete quotes through API | No | No | No | Yes |

Financial fields are `final_price`, `actual_cost` and `competitor_price`.
Calculated totals remain immutable regardless of role. Extraction review must
still be completed before approval or formal export, even for an Admin.

## Provisioning

Registration always creates Staff accounts, ignoring any submitted role.
Unknown roles fail closed. Existing sessions re-read the user from the database
on each request, so a role change immediately affects the next request.

Trusted operators with deployment/database access may provision an account:

```bash
python scripts/create_user.py <email> <password> --role manager
```

The CLI does not modify an existing account or promote it on repeated execution.
To change an existing role, use the separate audited operation:

```bash
python scripts/set_user_role.py <email> manager --reason "Assigned approval responsibility"
```

Use `admin` only for explicitly designated administrators. No first-user,
email-address or registration-invite rule automatically grants Admin. Role
changes append the old/new role, UTC timestamp, local operator identity and
reason to `users.role_history`. This is an application audit, not a tamper-proof
external log. There is no public HTTP role-management endpoint.

## Migration and Recovery

Back up before deployment. The additive migration gives existing accounts
Manager approval access, preserving their previous ability to approve without
granting Admin deletion rights. New database defaults and new registrations use
Staff. Review legacy account membership before accepting sensitive customer
files. Idempotent startup does not overwrite roles that have already been set.

Snapshots from before roles existed restore those legacy users as Manager.
Snapshots containing roles retain their recorded values and audit histories.
Never use a restore drill against a populated or production database.

## File Access and Limits

Staff can inspect their own uploads and originals linked to saved quotes.
Managers/Admins can inspect retained web originals. Viewers cannot use the image
or export-generation endpoints. A valid, short-lived LINE download token is an
explicit bearer capability, including for an otherwise unauthenticated client.

Admin deletion currently removes the row permanently. There is no browser
deletion control, soft-delete recovery, multi-tenant isolation, second-person
approval rule, or external audit sink. LINE preliminary-quote ingestion remains
a separate webhook workflow; LINE formal generation is redirected to staff
review.
