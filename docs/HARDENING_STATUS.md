# Guardrail Verification

## Implemented

- Web and API use the same approval and extraction-review guard.
- Calculated totals are immutable through PATCH. Negotiated prices use `final_price`.
- Export downloads require a staff session or a filename-bound signed token valid for one hour.
- Legacy AI endpoints require authentication; the image test endpoint is unavailable outside debug mode.
- Browser cross-site writes are rejected using Origin and Fetch Metadata checks. Session cookies are HttpOnly, SameSite=Lax, and Secure over HTTPS.
- For platform TLS termination, configure `PUBLIC_BASE_URL` to the environment's exact HTTPS URL. Cookie and Origin checks use that trusted origin only when the request host matches; arbitrary forwarded headers are not trusted.
- Image uploads validate actual JPEG/PNG/WebP bytes, upload size and pixel count.
- Web image evidence is retained in `UPLOAD_DIR`. Authorized staff can access their own originals and images linked to saved quotes; Managers/Admins can inspect retained web originals.
- AI network calls in the async web route run in a thread pool; SDK requests have explicit timeout and retry limits.
- JSON mode is enabled. Unrelated numeric units no longer overwrite extracted ENIG values in post-processing.
- LINE formal exports redirect operators to the staff review workflow.
- Login, registration and AI requests are rate limited with `Retry-After`. Enable `REDIS_ENABLED` and configure `REDIS_URL` for atomic shared counters across workers. Without Redis, limits are process-local. Redis failures fail closed with 503.
- Excel imports support optional currency, pricing version, technical specs and outcome costs. Missing values remain unknown and are shown in preview warnings.
- Exact-file/row import keys have a database unique index. Repeated imports skip existing rows; changed mappings require an explicit revision. This is not semantic deduplication of re-saved workbooks or legacy imports.
- Workbook uploads are bounded by compressed size, uncompressed size, row count and column count. Parsing runs outside the async event loop.
- Numeric validation rejects non-finite values and boolean values; fractional numeric quantities are rejected rather than truncated.
- Restore verification supports older snapshots missing new nullable columns, while rejecting unexpected non-null data.
- Viewer/Staff/Manager/Admin permissions protect web and API actions, including legacy AI endpoints and import confirmation. Registration cannot grant elevated roles; role changes revoke permissions on existing sessions and are audited through a trusted-operator CLI.
- A read-only extraction evaluation CLI grades labelled text/image cases, critical errors and false high confidence. Private datasets/results are excluded from Git and Docker. See [Extraction Evaluation](EXTRACTION_EVALUATION.md).

## Not Yet Guaranteed

- Tenant isolation, confidential-field filtering, soft-delete recovery and external tamper-proof audit logging are not implemented. This remains a single-company staff tool; see [Access Control](ACCESS_CONTROL.md).
- The Redis integration requires a real deployment check; local tests exercise concurrency and mocked Redis error/counter behavior, not a live Redis service.
- Image retention, deletion, storage quotas and orphan-upload cleanup require a policy and implementation.
- PDF/multi-page extraction is not supported.
- Semantic import deduplication and legacy import reconciliation remain future work.
- Native scheduled backups, alerting and database/storage readiness must be verified in the deployed environment; source changes do not enable them.
- JSON mode is not full schema validation and does not establish extraction accuracy. Real anonymized RFQ evaluation remains necessary.

## Live API Verification

Use synthetic inputs without customer identifiers. Check both text and vision extraction using the existing configured model and credentials. Never include secrets in reports or commit the inputs/results if they contain customer data.

Local success does not verify Railway variables, network access, account limits or a deployed revision. Deployment verification is a separate step.

## Deployment Notes

`import_key` is a nullable additive column with a unique index. Back up the database before deploying. Existing records are not assigned guessed import keys or reference metadata. Test both schema migration and old-snapshot restoration before release.

Rate limits default to 10 login attempts, 5 registration attempts and 10 AI requests per 60 seconds (`LOGIN_RATE_LIMIT`, `REGISTER_RATE_LIMIT`, `AI_RATE_LIMIT`). AI limits are shared by user across web and legacy text endpoints. Configure trusted proxy IP handling; never accept arbitrary forwarded client-IP headers. LINE webhook AI requests are not yet included in these web limits.
