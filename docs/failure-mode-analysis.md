# Failure Mode Analysis

| Failure Mode | Cause | Detection | Expected Behavior | Actual Result | Mitigation |
|--------------|-------|-----------|-------------------|---------------|------------|
| 1. Missing required field in dataset | CSV upload contains incomplete rows. | Schema validation detects missing values. | Import rejected with clear row-level error. | Import fails, returning `NEEDS_REVIEW` and highlighting rows. | User can correct CSV and re-upload, or rely on auto-repair if possible. |
| 2. Invalid dependency referenced | Changed file is not in dependency graph. | Test selection logic attempts graph traversal. | Returns safe fallback selection (e.g. baseline or conservative). | Selection completes without crash, running broad subset of tests. | Ensure `data_access` logs missing files and falls back properly. |
| 3. Security-critical change | Module is flagged as security-sensitive. | `is_security_sensitive` flag set in request. | Optimization is overridden; critical tests forced to `RUN`. | All tests in critical module are executed regardless of direct graph link. | Hardcoded `safety_overrides` intercept these flags. |
| 4. Empty database | Tables have been cleared via `DELETE` route. | Query results return empty lists. | Application stays up, API returns 0 tests affected. | Returns gracefully with 0 potentially affected tests. | Upload new dataset or use "Load Demo" route to restore state. |
| 5. Unauthorized API Request | Invalid or missing token for protected routes. | `get_user_from_token` fails token verification. | Request rejected with 403 Forbidden. | Returns `403` status. | Ensure clients send valid JWT token in headers. |
