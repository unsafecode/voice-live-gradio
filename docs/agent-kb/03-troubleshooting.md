# Troubleshooting common errors

## `401 Unauthorized`

Your API token is missing, expired, or revoked.

- Verify the `Authorization: Bearer <token>` header is present.
- Tokens expire after 60 minutes. Refresh with the `/oauth/token`
  endpoint or rotate via the portal under *Settings → API tokens*.
- If you rotated a token recently, deploy the new value to all
  environments and restart your workloads.

## `429 Too Many Requests`

You hit the per-plan rate limit:

| Plan       | Requests per minute | Burst |
| ---------- | ------------------- | ----- |
| Free       | 60                  | 90    |
| Pro        | 600                 | 900   |
| Enterprise | 6,000               | 9,000 |

Respect the `Retry-After` response header. Sustained overage on Pro and
Enterprise plans triggers a friendly email from billing, not a
shut-off.

## `503 Service Unavailable`

A regional component is degraded. Check **status.contoso.cloud** for
the current incident. If no incident is listed, retry with exponential
backoff (start at 1 second, cap at 30 seconds) and open a ticket if
the error persists for more than five minutes.

## "My deployment is stuck"

A deployment that stays in `Pending` for more than ten minutes is
almost always blocked by quota. Open *Settings → Quotas* and request
an increase; quota requests are auto-approved on Pro and Enterprise
plans for the first three increases per month.
