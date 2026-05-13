# v2.54.1 Smart Reports Route Hotfix

This hotfix restores the missing Flask route wiring for Smart Reports in `app.py`.

Fixed routes:

- `/reports`
- `/api/reports/operator`
- `/reports/export/json`
- `/reports/export/csv`
- `/reports/export/markdown`

The issue was that the Smart Reports engine, template, and navigation existed, but Flask did not register the page/API routes, so the browser returned `404 Not Found`.
