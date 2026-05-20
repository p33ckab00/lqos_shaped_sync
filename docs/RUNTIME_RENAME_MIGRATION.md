# Runtime Rename Migration — lqosync

LQoSync now uses `lqosync` as the canonical runtime name.

## Canonical runtime names

```text
systemd service: lqosync
sudoers file:    /etc/sudoers.d/lqosync
app log:         /opt/LQoSync/logs/lqosync.log
system log:      /var/log/lqosync.log
Docker name:     lqosync
repo:            https://github.com/p33ckab00/LQoSync.git
```

## Update behavior from older installs

The installer and updater perform a one-time safety migration:

1. back up operator-owned files and LibreQoS input files
2. stop and disable the previous runtime service when present
3. remove the previous sudoers drop-in when present
4. move the previous `/var/log` file to the canonical log name when safe
5. install and start the canonical `lqosync` service

## Operator command after migration

```bash
sudo systemctl status lqosync
sudo journalctl -u lqosync -n 100 --no-pager
sudo systemctl restart lqosync
```

## What remains unchanged

```text
/opt/LQoSync
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

These are preserved and backed up before install/update actions.
