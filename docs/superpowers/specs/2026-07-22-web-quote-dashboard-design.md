# Web Quote Dashboard — Design Spec

Date: 2026-07-22

## Background

The business currently quotes PCB jobs through a LINE bot: staff chat with the
bot, paste a spec description or a photo, and the bot replies with a computed
quote. The owner wants quoting to move to an internal web app instead, because
chat-based interaction is too slow for day-to-day sales work. The web app
becomes the primary channel; the LINE bot stays in place as a secondary
channel (mainly so a photo can still be sent in from the field), and both
must produce identical quotes because they share the same calculation engine.

## Goals

- Staff can create, review, edit, and track PCB quotes from a web UI, faster
  than doing it over LINE chat.
- The web app and the LINE bot share one quote engine, one AI parser, one
  database — no duplicated business logic, no drift between channels.
- Every quote records who created it and who last edited it.
- Internal use only: multiple named accounts, no role tiers (yet).

## Non-goals (explicitly out of scope for this spec)

- No external/customer-facing self-service portal. (May be revisited later;
  it is a much bigger scope — anti-abuse, review workflow — and was
  explicitly deferred by the owner.)
- No role-based permissions. Every logged-in account has equal access.
- No retroactive translation of existing Chinese comments/docs in the repo.
  That is a separate follow-up project, tracked independently.
- Visual styling (colors, typography, "tech" look and feel) is not finalized
  here. This spec only records the direction (light background, tech
  aesthetic) as a note for whoever does the visual pass later.

## Architecture

Single FastAPI application, extended in place — no new repo, no separate
frontend build:

- **Server-rendered HTML** via Jinja2 templates, progressively enhanced with
  HTMX (partial page updates without full reloads) and Alpine.js (small
  client-side interactivity). Tailwind CSS via CDN/pre-built stylesheet —
  no Node build pipeline.
- **Session-cookie auth** (signed cookie, e.g. `itsdangerous`), not JWT —
  there's no separate frontend origin, so a plain server session is simpler.
- New router `app/web.py`, mirroring the existing `app/api.py` router
  pattern, mounted alongside it in `app/main.py`.
- New `templates/` directory for Jinja2 templates, `static/` for CSS/JS.
- LINE bot code in `app/main.py` is untouched apart from calling the same
  (slightly extended) `save_quote` used by the new web flow.

Rationale: this is a single-developer-plus-AI-maintained internal tool. A
split frontend (e.g. Next.js talking to a JSON API) would add a second repo,
a build pipeline, CORS, and cross-stack type duplication for no benefit this
project needs today. Server-rendered HTML keeps one codebase, one deploy
target (same Docker/Fargate setup already in place), and keeps "change one
thing, change it in one place" true for the quote engine.

## Data model changes

Current `QuoteHistory` (`app/core/database.py`) only stores a handful of
scalar fields (layer, material, dimensions, qty, total, unit_price,
created_at) and uses `customer_id` to mean the LINE `user_id` — not an
actual customer/company. This is insufficient for a quote detail page that
needs to show full spec + full price breakdown, and conflates "who sent
this" with "which customer this is for."

Changes:

1. **New `Customer` table**: `id`, `company_name`, `contact`, `phone`,
   `email`, `common_specs` (JSON), `created_at`. Feeds off the existing PCB
   photo company-name recognition already implemented.

2. **New `User` table** (web login): `id`, `email`, `password_hash`,
   `created_at`. No role column — all accounts are equal.

3. **`QuoteHistory` changes**:
   - Rename existing `customer_id` column to `source_channel_id` (it holds
     the LINE `user_id` or an equivalent "who/what submitted this" token,
     not a business customer).
   - Add `customer_id` (FK → `Customer`, nullable — LINE-submitted quotes
     may not be linked to a customer record).
   - Add `status` (enum-like string: `pending` / `approved` / `ordered`,
     default `pending`), `notes` (text), `quote_no` (formatted id, e.g.
     `PCB-20260722-001`).
   - Add `spec_json` and `breakdown_json` (JSON columns) holding the full
     parsed spec dict (from `ai_parser`/`image_parser`/the web form) and the
     full `quote_engine.calculate_quote()` result dict, respectively.
     Rationale: the parsed spec and price breakdown each have a dozen-plus
     fields that change whenever the quote engine or parser is extended.
     Storing them as JSON avoids a migration every time a new field is
     added, while the handful of columns used for filtering/sorting
     (layer, material, total, status, created_at, customer_id) stay as
     indexed columns.
   - Add `created_by_user_id` and `updated_by_user_id` (FK → `User`,
     nullable — null for LINE-submitted quotes since there's no web login
     involved on that path).

4. Existing rows (LINE-submitted, pre-migration) will have null
   `customer_id`, `created_by_user_id`, `spec_json`, `breakdown_json`. Pages
   reading these fields must handle null/missing gracefully rather than
   erroring.

## Pages and flow

All routes below require login except `/login` itself; unauthenticated
requests redirect to `/login`. `app/api.py`'s existing JSON endpoints
currently have no auth at all — this is a pre-existing gap that gets closed
as part of this work (same session-based auth guard applied there too).

1. **`/login`** — email + password form.
2. **`/` (dashboard home)** — stat cards (today/month/all-time quote counts,
   average price), reusing `app/api.py`'s `/api/stats/summary`.
3. **`/quotes/new`** — the core page:
   - An "AI assist" panel: paste free-text spec description or upload a PCB
     photo; an HTMX request calls the existing `ai_parser.parse_pcb_text` /
     `image_parser.parse_pcb_image` and swaps the parsed fields into the
     form below, without a full page reload.
   - A structured form below with explicit fields (layer, material,
     dimensions, qty, surface finish, VIP/impedance/back-drill/BVH,
     delivery days, etc.) that staff can review and correct.
   - Submitting runs `quote_engine.calculate_quote()` — the same function
     the LINE bot calls — and shows the computed breakdown before the user
     confirms and saves it (creating/linking a `Customer` as needed).
4. **`/quotes`** — list with filters (date range, layer, material, customer,
   status) and search, extending the query logic already in `app/api.py`.
5. **`/quotes/{id}`** — detail page rendering `spec_json`/`breakdown_json` in
   full, plus `status`, `notes`, `created_by`/`updated_by`. Actions: change
   status, edit notes, download Excel (`export_excel.py`), generate a formal
   quote document (`formal_quote_export.py`).
6. **`/customers`** — list + create/edit form for the `Customer` table.
7. **`/stats`** — charts (Chart.js via CDN) for quote volume trend, layer
   distribution, material distribution, backed by `app/api.py`'s
   `/api/stats/by-layer` and `/api/stats/by-material`.

## Error handling

- AI parse failure (OpenAI timeout/quota): the form keeps whatever the user
  already typed, shows a warning, and lets them fill fields manually — same
  degrade-gracefully behavior the LINE bot already has for "quote could not
  be completed."
- All new page routes and the existing `app/api.py` routes require a valid
  session; missing/invalid session → redirect (pages) / 401 (API).
- Detail/list pages must not error on quotes with null `customer_id`,
  `created_by_user_id`, `spec_json`, or `breakdown_json` (pre-migration
  LINE-submitted rows).

## Testing

- Parity test: given the same input spec, `calculate_quote()` invoked via
  the web flow and via the LINE flow produce the same `total` — proves both
  channels share one engine with no divergent logic.
- Auth: protected routes redirect/401 when logged out; login persists a
  valid session; `app/api.py` routes now also require auth.
- Migration safety: existing pre-migration `QuoteHistory` rows render on the
  list/detail pages without errors despite missing new columns' data.

## Language convention

Per standing project convention: all code, comments, docstrings, and
documentation (including this spec) are in English. User-facing text (LINE
bot replies, web UI labels/buttons/messages) stays in Traditional Chinese —
the business's staff and clients are Chinese-speaking.
