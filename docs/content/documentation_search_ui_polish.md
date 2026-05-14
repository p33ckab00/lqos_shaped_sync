# v2.59 Documentation Search + UI/Mobile Polish

LQoSync v2.59 adds a local Documentation Search Center and small global UI consistency helpers.

## Documentation Search Center

The `/docs/search` page indexes bundled local Markdown documentation, including `docs/content/*.md`, the Smart Policy Center guides, setup/repair guides, README, full documentation, installation guides, and release documentation.

The search is local and read-only. Queries are not sent to external services.

Operators can use it to quickly find topics such as:

- policy cleanup
- backup_before_apply
- LibreQoS working_dir
- GitHub update
- fresh install
- Telegram notifications
- MikroTik API setup
- DHCP identity
- Smart Defaults Repair

## Routes

```text
/docs
/docs/search
/docs/view/<doc_id>
/api/docs/search
/api/docs/index
```

## UI consistency helpers

v2.59 adds reusable layout helpers for future templates:

- `responsive-grid`
- `content-stack`
- `empty-state`
- `section-card`
- `action-strip`
- `mobile-sticky-actions`
- `kbd-hint`

These helpers support cleaner desktop layout and better mobile stacking, especially for action buttons, cards, and empty states.

## Product direction

About / Documentation remains the long-form manual source of truth. Setup & Repair remains diagnostic/action focused. Documentation Search connects both by helping operators find the correct guide quickly.
