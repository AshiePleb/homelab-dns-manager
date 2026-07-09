# HomeLab DNS Manager — External API (for WebHost integration)

**Status:** Integrated with WebHost (Settings → DNS, site domain linking).

**DNS panel:** https://dns.ahlds.uk  
**API base:** `https://dns.ahlds.uk/api/v1`  
**Auth:** `Authorization: Bearer hld_<key>`

Admin creates keys at **API Keys** (admin only) in the DNS Manager sidebar. Key is shown once at creation. Per-key limits (defaults): max 10 DNS records, max 10 services (proxy + SSL provisions). Resources are tagged with `api_key_id` — keys can only manage what they created.

## Known gap: panel-created records are invisible to WebHost

Records created in the DNS Manager **web UI** (e.g. `home.ahlds.uk → 10.10.10.3:9000`) typically have no `api_key_id` (or a different one). WebHost calls:

- `GET /api/v1/records` → `[]` (key-owned only)
- `GET /api/v1/services` → `[]` (key-owned only)
- `GET /api/v1/catalog` → **all linkable hostnames** (read-only; use this for linking)

So the site Domains dropdown and auto-detect should use **`/catalog`**, not `/records` or `/services`.

**WebHost workaround:** manual hostname link (stores assignment locally).

**Implemented DNS Manager fix:**

1. **`GET /api/v1/catalog`** (read-only) — returns all app-managed hostnames for linking:
   ```json
   [
     { "hostname": "home.ahlds.uk", "internal_target": "10.10.10.3:9000", "dns_record_id": 12, "dns_service_id": 8, "managed_by": "panel" }
   ]
   ```
   Integration keys (e.g. WebHost) get read access via `/catalog`; delete/provision still scoped to key-owned resources.

2. **API key flag `can_read_all: true`** — *(not implemented)* `GET /records` and `GET /services` include all records when set.

3. **Backfill `api_key_id`** — *(not implemented)* assign existing panel records to an integration key.

WebHost auto-detect matches `internal_target` (normalized `host:port`) to each site's `proxy_target`.

## Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/info` | Key limits, usage, endpoint list |
| GET | `/api/v1/services/template` | Available zones |
| POST | `/api/v1/services/provision` | DDNS + Caddy SSL for a site |
| DELETE | `/api/v1/services/{id}` | Remove proxy (key-owned only) |
| GET | `/api/v1/records` | List DNS records created by this key |
| DELETE | `/api/v1/records/{id}` | Remove a key-owned record |
| GET | `/api/v1/catalog` | Read-only list of all linkable hostnames + internal targets |

## Example: provision from WebHost

WebHost would call this when exposing a site (target = host IP + site port from site detail):

```bash
curl -X POST https://dns.ahlds.uk/api/v1/services/provision \
  -H "Authorization: Bearer hld_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "subdomain": "mysite",
    "target": "10.10.10.3:9001",
    "create_dns": true,
    "create_proxy": true,
    "skip_port_check": false
  }'
```

## WebHost integration notes (TBD)

- Store DNS API key in admin settings (encrypted), not per-site.
- Site detail UI: subdomain picker + provision / deprovision using site's `proxy_target`.
- Track provisioned service/record IDs on the site model when implemented.
