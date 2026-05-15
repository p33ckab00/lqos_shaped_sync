# v2.66 Backup / Restore Center Polish

LQoSync v2.66 improves backup operations inside the Operations Center without changing MikroTik collection, policy decisions, scheduler behavior, or LibreQoS apply logic.

## What changed

- Backup rows now include inspect/preview, download zip, restore, and delete actions.
- Backup preview is read-only and compares backup files against live files before restore.
- Backup integrity verifies tracked files and metadata hashes when available.
- Backup download exports the selected backup directory as a zip file.
- Restore still creates a fresh backup of current live files before rollback, keeping restores reversible.
- Retention preview API shows which backups would be kept or pruned according to configured retention.

## Recommended operator workflow

1. Open **Operations Center → Backups**.
2. Click the eye icon to inspect a backup.
3. Review integrity and live file comparison.
4. Download a zip if you need an offline copy.
5. Restore only after confirming the selected backup is the intended rollback point.

## Safety notes

- Preview does not modify files.
- Download does not modify files.
- Restore modifies live `ShapedDevices.csv` and/or `network.json`, but first creates a new backup of current live files.
- Delete is permanent and should be used only after confirming the backup is no longer needed.
