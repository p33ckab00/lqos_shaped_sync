# Stale Codebase Cleanup Policy

This policy defines how stale LQoSync codebases and runtime remnants should be handled.

## Keep

Always keep these unless a future explicit migration says otherwise:

- `/opt/LQoSync`
- `/opt/libreqos`
- `/usr/local/bin/lqosync-core`
- `/etc/systemd/system/lqosync-core.service`
- `/run/lqosync-core.sock`
- current Git branch `lqosync-in-rust`
- current WebUI/UX/static assets

## Archive candidates

These are usually safe to archive after confirmation and after `/opt/LQoSync` is verified:

- `/home/pi/lqosync_docker`
- `/home/pi/lqosync`
- `/opt/lqosync`
- old timestamped backups of prior working trees

Archiving means moving to `/opt/LQoSync-archive/<timestamp>/`, not deleting.

## Inspect before action

These may be valid depending on deployment:

- `lqosync-website.service`
- `/opt/lqosync-website`
- Gunicorn processes on custom ports such as `9202`
- Docker containers such as `lqos_shaped_sync`
- Nginx reverse proxy config

Do not stop or delete these until you know whether they serve the current UI, an external website, a rollback path, or a separate app.

## Never delete automatically

The cleanup guard must not automatically delete:

- LibreQoS files
- current Rust binary and service
- Nginx configs
- Docker volumes
- WebUI/static assets
- Python rollback code
- transaction journals
- backup/rollback manifests
- audit logs

## Confirmation token

The archive executor requires:

```bash
CONFIRM_STALE_CODEBASE_ARCHIVE=CONFIRM_STALE_CODEBASE_ARCHIVE
```

This prevents accidental archive moves.
