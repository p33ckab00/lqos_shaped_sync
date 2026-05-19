# Rust Core v2.0.1 Script Permission Hotfix

This hotfix addresses manual ZIP/checkouts where shell script executable bits may be lost.

## Symptom

```bash
scripts/build-rust-core.sh
# bash: scripts/build-rust-core.sh: Permission denied

sudo scripts/install-rust-core.sh
# sudo: scripts/install-rust-core.sh: command not found
```

When this happens, the installed `/usr/local/bin/lqosync-core` may still be the older Rust core version. A successful `self-test` alone is not enough; verify the advertised operations include the new v2.0 operation:

```text
build-routeros-collector-plan
```

## Repair

Run either:

```bash
bash scripts/repair-script-permissions.sh
scripts/build-rust-core.sh
sudo scripts/install-rust-core.sh
sudo scripts/install-rust-core-daemon.sh
```

or bypass executable permissions entirely:

```bash
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
```

Then verify:

```bash
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```

Expected v2.0+ signal:

```text
build-routeros-collector-plan
```

## Safety

This is a packaging/permission hotfix only. It does not change runtime sync/apply behavior.
