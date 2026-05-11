# Existing Installation Handling / Smart Adoption

This document preserves the original planning notes for how LQoSync should handle an existing installation regardless of how it was first installed.

---

Yes, exactly. Dapat ang installer natin hindi lang pang-fresh install. Dapat may **Existing Installation Handling** siya, regardless kung paano na-install dati:

```text
ZIP install
manual copy
Git clone
Docker version before
bare-metal version before
partial/broken install
```

Ang tamang approach ay **smart adopt / preserve / replace options**, hindi automatic delete.

# Best approach

Kapag nag-install from GitHub, unang gagawin ng installer:

```text
Detect existing LQoSync installation
Detect existing LibreQoS files
Detect existing users/config/logs/state
Ask operator what to do
```

## Existing install detection

Check:

```text
/opt/lqosync
/opt/lqosync/.git
/etc/systemd/system/lqos_shaped_sync.service
/etc/sudoers.d/lqosync
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/lqosync/users.json
/opt/lqosync/.env
/opt/lqosync/state/
/opt/lqosync/logs/
```

Then installer shows:

```text
Existing LQoSync installation detected.

Choose action:

[1] Adopt and update existing install  (recommended)
[2] Update code only, preserve all data
[3] Repair install, preserve all data
[4] Backup and replace app files
[5] Remove existing LQoSync then fresh install
[6] Abort
```

# Option 1: Adopt and update existing install

This is the **best default**.

Use case:

```text
May existing /opt/lqosync, pero hindi Git repo
Installed from ZIP/manual copy
Gusto mo maging GitHub-managed na without losing config/users/logs
```

Behavior:

```text
1. Stop lqos_shaped_sync
2. Backup /opt/lqosync
3. Preserve local files:
   - users.json
   - .env
   - state/
   - logs/
   - backups/
4. Preserve LibreQoS live files:
   - /opt/libreqos/src/config.json
   - /opt/libreqos/src/ShapedDevices.csv
   - /opt/libreqos/src/network.json
5. Clone GitHub repo to temp folder
6. Replace app code from repo
7. Restore preserved local files
8. Run config migration
9. Reapply ACL/sudoers/systemd
10. Start service
11. Health check
```

Meaning: **repo code updates, local data stays**.

# Option 2: Update code only

Use case:

```text
Minor UI/code update lang
Ayaw mong galawin config/users/runtime files
```

Behavior:

```text
Update:
- app.py
- templates/
- static/
- engine/
- applier/
- collectors/
- scripts/
- docs/

Preserve:
- config.json
- ShapedDevices.csv
- network.json
- users.json
- .env
- state/
- logs/
- backups/
```

This is safe, but kung may new required config keys, baka hindi ma-add unless may startup migration.

# Option 3: Repair install

Use case:

```text
May missing service file
Wrong permissions
Missing sudoers
Broken ACL
App files okay
```

Behavior:

```text
No Git code replace unless needed
Recreate systemd service
Recreate sudoers
Reapply /opt/libreqos/src ACL
Normalize .env
Run config migration
Restart service
```

Useful ito kapag live system na, ayaw mong galawin app code.

# Option 4: Backup and replace app files

Use case:

```text
Gusto mong clean code refresh
Pero preserve user/config/data
```

Behavior:

```text
Backup /opt/lqosync
Delete/replace app code
Restore:
- users.json
- .env
- state/
- logs/
- backups/
Preserve LibreQoS files
Run migration
Restart
```

This is good kung may messy old code files.

# Option 5: Remove then fresh install

Use case:

```text
Lab system
Bad install
Gusto mo clean start
```

But still should ask:

```text
Preserve LibreQoS files? YES by default
Preserve users.json? YES by default
Preserve logs? optional
```

Never delete these by default:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
```

Full purge should require explicit confirmation:

```bash
CONFIRM_FULL_PURGE=yes
```

# Recommended environment variables

Para pwede non-interactive:

```bash
sudo EXISTING_INSTALL_ACTION=adopt bash install-from-github.sh
```

Allowed:

```text
adopt
code_only
repair
replace_app
remove_fresh
abort
```

Additional preservation flags:

```bash
PRESERVE_CONFIG=true
PRESERVE_USERS=true
PRESERVE_LOGS=true
PRESERVE_STATE=true
PRESERVE_GENERATED_FILES=true
RUN_CONFIG_MIGRATION=true
```

Default production values:

```text
PRESERVE_CONFIG=true
PRESERVE_USERS=true
PRESERVE_LOGS=true
PRESERVE_STATE=true
PRESERVE_GENERATED_FILES=true
RUN_CONFIG_MIGRATION=true
```

# Concrete recommended workflow

For your system, safest default should be:

```bash
cd /opt
curl -fsSL https://raw.githubusercontent.com/p33ckab00/lqos_shaped_sync/main/install-from-github.sh -o /tmp/install-lqosync.sh
sudo EXISTING_INSTALL_ACTION=adopt bash /tmp/install-lqosync.sh
```

Then future updates:

```bash
cd /opt/lqosync
sudo bash upgrade.sh
```

Default `upgrade.sh` should be:

```text
preserve_and_migrate
```

Meaning:

```text
Pull code from GitHub
Preserve config/users/logs/state
Preserve ShapedDevices.csv/network.json
Add missing safe config defaults
Restart service
Run health check
```

# Important principle

The installer should treat these as **operator-owned/live files**:

```text
/opt/libreqos/src/config.json
/opt/libreqos/src/ShapedDevices.csv
/opt/libreqos/src/network.json
/opt/lqosync/users.json
/opt/lqosync/.env
/opt/lqosync/state/
/opt/lqosync/logs/
```

GitHub should update only the **application source**, not destroy live operational data.

# Best naming for this feature

```text
Existing Install Adoption
Smart Existing Install Handler
Git-managed adoption mode
Production-safe install adoption
```

For LQoSync:

```text
LQoSync Smart Existing Install Adoption
```

# Commit description

```bash
git commit -m "Add smart existing install adoption flow" -m "Improves the GitHub source installer so it can safely handle existing LQoSync installations regardless of whether they were installed from ZIP, manual copy, Docker, or Git.

Adds operator choices to adopt and update, update code only, repair install, replace app files with backup, remove and fresh install, or abort when /opt/lqosync already exists.

Preserves live operator-owned files by default, including /opt/libreqos/src/config.json, ShapedDevices.csv, network.json, /opt/lqosync/users.json, .env, state, logs, and backups while allowing application code to become Git-managed and safely migrated.

This keeps LibreQoS integrity intact while making future GitHub-based updates cleaner, safer, and easier to operate in production."
```
