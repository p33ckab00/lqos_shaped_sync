# Rust Core v7.0 Full Rust Backend Production Cutover

`VERSION = 2.140.0-rc1`  
`rust/lqosync-core = 7.0.0`

## Phase

This is the first actual full-Rust-backend production cutover package.

The Rust core operation declares whether all final gates are satisfied and whether production cutover is allowed. OS-level service mutation is still executed only by operator-supervised scripts with rollback ready.

## Operation

```text
build-full-rust-backend-production-cutover
```

## Confirmation token

```text
CONFIRM_FULL_RUST_BACKEND_PRODUCTION_CUTOVER
```

## What must pass

```text
v6.6 full backend removal rehearsal ready
WebUI/UX unchanged
WebUI static assets preserved
server cargo tests passed
self-test passed
rollback test passed
Python fallback backup ready
operator acknowledgment
rollback path present
```

## What can become true

When all gates pass, Rust may report:

```text
cutover_allowed = true
full_rust_backend = true
full_rust_backend_production_enabled = true
rust_service_runtime_authoritative = true
api_traffic_switch_allowed = true
python_backend_removable = true
python_removal_allowed = true
```

## What still remains false inside the core decision

The Rust core decision itself does not perform OS-level changes:

```text
python_backend_removed = false
python_removal_executed = false
flask_routes_disabled = false
api_traffic_switched_to_rust = false
```

Those are performed only by the supervised cutover script after this contract reports ready.

## WebUI/UX

WebUI/UX and static assets remain as-is. The backend may change to Rust, but the user-facing UI remains unchanged.

## Endpoint

```text
GET  /api/rust-core/full-rust-backend-production-cutover
POST /api/rust-core/full-rust-backend-production-cutover
```

## Validation

```bash
bash scripts/repair-script-permissions.sh
bash scripts/build-rust-core.sh
sudo bash scripts/install-rust-core.sh
sudo bash scripts/install-rust-core-daemon.sh
printf '{"version":"1","op":"self-test","payload":{}}' | lqosync-core
```
