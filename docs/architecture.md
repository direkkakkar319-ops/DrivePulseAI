# Architecture status

The working account flow is Android Firebase authentication → verified bearer
token → FastAPI → PostgreSQL profile storage.

The mobile vehicle-health experience currently uses a deterministic, session-only
demo provider. Telemetry ingestion, trained inference, vehicle persistence and
backend reports are planned, not running implementations.

See [Future mobile integration and product workflow](future-mobile-integration.md)
for the current provider boundary, future telemetry/storage/predictor/API flow,
and unresolved contracts. Existing files in `diagrams/` and `screenshots/` are
text placeholders, not actual generated diagrams or screenshots.
