# Documentation Consolidation and Source of Truth

LQoSync documentation is consolidated so operators and GitHub readers see one consistent manual instead of repeated explanations across many pages.

## Documentation model

```text
README.md
  Compact GitHub landing page: what LQoSync is, install/update commands, and links.

FULL_DOCUMENTATION.md
  Complete single-file manual compiled from the documented topics below.

docs/DOCUMENTATION_INDEX.md
  GitHub-friendly table of contents that points to the canonical topic files.

docs/content/*.md
  Topic-level documentation source used by WebUI Documentation Center and GitHub docs.

docs/docs_manifest.json
  Documentation index: title, file, anchor, and summary for search/rendering order.

WebUI Documentation Center
  Searchable/readable view of the same local documentation files.

About page
  Lightweight project/version/AI disclosure entry point with links to Documentation Center.

Setup & Repair
  Diagnostics and repair actions; it should link to documentation instead of duplicating long manual text.
```

## Operator rule

Use the Documentation Center or `FULL_DOCUMENTATION.md` as the manual. Use Setup & Repair when something is failing. Use Dashboard for live status. Use Operations Center for logs, services, journals, backups, and apply history.

## GitHub rule

Keep `README.md` short. Put detailed guides in `docs/content/*.md` and let `FULL_DOCUMENTATION.md` act as the single-file export.

## Maintenance rule

When adding a new feature:

1. Add or update one topic file under `docs/content/`.
2. Add the topic to `docs/docs_manifest.json`.
3. Regenerate or update `FULL_DOCUMENTATION.md`.
4. Keep README concise.
5. Link from WebUI pages to the documentation topic instead of duplicating long explanations.

## Why this matters

A compact documentation model prevents conflicting instructions, reduces UI clutter, improves search quality, and makes the project easier to maintain as LQoSync grows.
