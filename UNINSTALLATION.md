# LQoSync Uninstallation Guide

This guide explains how to stop and remove LQoSync safely.

It covers:

1. Docker installation uninstall
2. Bare-metal Ubuntu/systemd uninstall
3. Git-based install cleanup
4. Optional cleanup of `/opt/lqosync`
5. Optional cleanup of permissions/ACL
6. Optional restore of old `updatecsv.service`

---

## Important Safety Note

Do **not** delete these files unless you are sure LibreQoS no longer needs them:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

These are LibreQoS working files. LQoSync may manage them, but LibreQoS reads them.

Before removing anything, create a backup:

```bash
sudo mkdir -p /root/lqosync_uninstall_backup_$(date +%F_%H%M%S)
BACKUP_DIR=$(ls -td /root/lqosync_uninstall_backup_* | head -1)
sudo cp -a /opt/lqosync "$BACKUP_DIR/opt_lqosync" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/config.json "$BACKUP_DIR/config.json" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/ShapedDevices.csv "$BACKUP_DIR/ShapedDevices.csv" 2>/dev/null || true
sudo cp -a /opt/libreqos/src/network.json "$BACKUP_DIR/network.json" 2>/dev/null || true
echo "Backup saved to: $BACKUP_DIR"
```

---

# A. Docker Uninstall

Use this if you installed with:

```bash
sudo docker compose up -d --build
```

## 1. Go to the Git/project folder

Common locations:

```bash
cd /home/pi/lqos_shaped_sync
```

or:

```bash
cd /home/pi/lqos_docker
```

Confirm Compose file exists:

```bash
ls -lah compose.yaml
```

## 2. Stop and remove the container

```bash
sudo docker compose down
```

Check:

```bash
sudo docker ps -a | grep lqos || true
```

## 3. Optional: remove Docker image

List LQoSync images:

```bash
sudo docker images | grep lqos
```

Remove by image ID:

```bash
sudo docker rmi IMAGE_ID
```

Or try common tags:

```bash
sudo docker image rm lqos_shaped_sync:latest 2>/dev/null || true
sudo docker image rm lqos_shaped_sync:2.17-opt-lqosync 2>/dev/null || true
```

## 4. Optional: remove runtime folder

LQoSync runtime path:

```text
/opt/lqosync
```

Backup then delete:

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

## 5. Optional: remove Git project folder

If installed from Git:

```bash
rm -rf /home/pi/lqos_shaped_sync
```

If using old local folder name:

```bash
rm -rf /home/pi/lqos_docker
```

Only do this after you no longer need local source files.

---

# B. Bare-metal Ubuntu/Systemd Uninstall

Fast path using the bundled uninstall helper:

```bash
cd /opt/lqosync
sudo bash uninstall.sh
```

Remove `/opt/lqosync` too:

```bash
cd /opt/lqosync
sudo REMOVE_RUNTIME=true bash uninstall.sh
```

Restore the entire LibreQoS src tree to root ownership instead of only managed files:

```bash
cd /opt/lqosync
sudo RESTORE_MODE=full bash uninstall.sh
```

Use this if you installed with:

```bash
sudo bash install.sh
```

or:

```bash
sudo LQOSYNC_INIT_POLICY=preserve_existing bash install.sh
```

## 1. Stop and disable service

```bash
sudo systemctl stop lqos_shaped_sync
sudo systemctl disable lqos_shaped_sync
```

Check:

```bash
sudo systemctl status lqos_shaped_sync
```

## 2. Remove systemd service file

```bash
sudo rm -f /etc/systemd/system/lqos_shaped_sync.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

## 3. Remove sudoers rules

```bash
sudo rm -f /etc/sudoers.d/lqosync
sudo rm -f /etc/sudoers.d/lqos_shaped_sync
```

## 4. Backup and remove app/runtime folder

```bash
sudo tar -czf /root/lqosync_runtime_backup_$(date +%F_%H%M%S).tar.gz /opt/lqosync 2>/dev/null || true
sudo rm -rf /opt/lqosync
```

## 5. Remove log file, optional

```bash
sudo rm -f /var/log/lqos_shaped_sync.log
```

## 6. Remove Linux user, optional

```bash
sudo userdel lqosync 2>/dev/null || true
sudo rm -rf /home/lqosync 2>/dev/null || true
```

## 7. Restore LibreQoS permissions to root

Bare-metal LQoSync grants ACL write access to the `lqosync` user so it can create atomic temp files under `/opt/libreqos/src`. During uninstall, restore these permissions so LibreQoS returns to a normal root-owned state.

Recommended managed restore:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --managed
```

This restores only the directory and files managed by LQoSync:

```text
/opt/libreqos/src
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Expected result:

```text
/opt/libreqos/src                       root:root 755
/opt/libreqos/src/config.json           root:root 600
/opt/libreqos/src/ShapedDevices.csv     root:root 644
/opt/libreqos/src/network.json          root:root 644
```

Optional full restore if you intentionally want everything under `/opt/libreqos/src` returned to root ownership:

```bash
sudo bash /opt/lqosync/scripts/restore_libreqos_permissions.sh --full
```

Manual fallback if the script is already gone:

```bash
sudo setfacl -x u:lqosync /opt/libreqos/src 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/config.json 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/ShapedDevices.csv 2>/dev/null || true
sudo setfacl -x u:lqosync /opt/libreqos/src/network.json 2>/dev/null || true
sudo setfacl -d -x u:lqosync /opt/libreqos/src 2>/dev/null || true

sudo chown root:root /opt/libreqos/src
sudo chown root:root /opt/libreqos/src/config.json /opt/libreqos/src/ShapedDevices.csv /opt/libreqos/src/network.json
sudo chmod 755 /opt/libreqos/src
sudo chmod 600 /opt/libreqos/src/config.json
sudo chmod 644 /opt/libreqos/src/ShapedDevices.csv /opt/libreqos/src/network.json
```

## 8. Optional: remove Git project folder

If installed from Git:

```bash
rm -rf /home/pi/lqos_shaped_sync
```

If using old extracted package folder:

```bash
rm -rf /home/pi/lqos_docker
```

---

# C. What Not To Remove By Default

Normally, keep:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

These files may still be required by LibreQoS.

Only remove them if you intentionally want to remove LQoSync-managed LibreQoS output:

```bash
sudo cp -a /opt/libreqos/src/config.json /root/config.json.backup.$(date +%F_%H%M%S) 2>/dev/null || true
sudo cp -a /opt/libreqos/src/ShapedDevices.csv /root/ShapedDevices.csv.backup.$(date +%F_%H%M%S) 2>/dev/null || true
sudo cp -a /opt/libreqos/src/network.json /root/network.json.backup.$(date +%F_%H%M%S) 2>/dev/null || true

sudo rm -f /opt/libreqos/src/config.json
sudo rm -f /opt/libreqos/src/ShapedDevices.csv
sudo rm -f /opt/libreqos/src/network.json
```

---

# D. Restore Old updatecsv.service

If you want to return to the old script workflow:

```bash
sudo systemctl enable --now updatecsv.service
sudo systemctl status updatecsv.service
journalctl -u updatecsv.service -f
```

Make sure LQoSync is stopped/removed first to avoid two writers touching `ShapedDevices.csv` and `network.json`.

---

# E. Verify Removal

```bash
systemctl status lqos_shaped_sync
ls -lah /opt/lqosync
sudo docker ps -a | grep lqos || true
```

Expected after full uninstall:

```text
Unit lqos_shaped_sync.service could not be found
/opt/lqosync: No such file or directory
no lqos_shaped_sync container
```

---

## Related In-App Manual

The web UI includes an About page with the latest uninstall and permission-restore guide:

```text
http://<server-ip>:9202/about
```

See also:

```text
docs/ABOUT_MODULE_OPERATOR_GUIDE.md
```
