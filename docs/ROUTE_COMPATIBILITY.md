# Route Compatibility Map

LQoSync keeps old routes as compatibility aliases so bookmarks and older links do not break, while canonical UI ownership remains compact.

| Old route | Canonical destination | Purpose |
| --- | --- | --- |
| `/health` | `/` | Dashboard owns live health/status. |
| `/services` | `/operations?tab=services` | Operations Center owns services/journals. |
| `/logs` | `/operations?tab=logs` | Operations Center owns app logs, audit, and backups. |
| `/policy` | `/config?tab=policies` | Config Center owns policy settings. |
| `/notifications` | `/config?tab=notifications` | Config Center owns notification delivery settings. |
| `/routers` | `/config?tab=routers` | Router Insight lives beside router settings to avoid duplicate UX. |

These routes should not become full duplicate pages again.
