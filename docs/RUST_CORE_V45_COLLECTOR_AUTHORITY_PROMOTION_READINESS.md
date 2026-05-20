# Rust Core v4.5 Collector Authority Promotion Readiness

LQoSync `2.115.0-rc1` / `lqosync-core 4.5.0` adds `build-collector-authority-promotion-readiness`.

This is a non-mutating bridge after the v4.4 pilot result evaluator. It answers whether the Rust collector authority pilot result is good enough to be considered for a future promotion step, without actually promoting Rust collectors to production authority.

## Operation

```text
build-collector-authority-promotion-readiness
```

## Flow

```text
collector authority pilot result evaluation
+ explicit promotion-readiness gates
+ manual confirmation token
+ Python fallback requirement
+ Rust-shadow freshness
+ forbidden side-effect checks
↓
collector authority promotion readiness report
```

## Required confirmation token

```text
CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS
```

The token only allows the readiness report to say `ready`. It does not switch authority.

## Status values

```text
collector_authority_promotion_readiness_shadow_only
collector_authority_promotion_readiness_review
collector_authority_promotion_readiness_ready
blocked
```

## Safety guarantees

v4.5 does not:

```text
open RouterOS sockets
promote Rust collectors
transfer cleanup authority
write generated files
apply LibreQoS
remove Python collector fallback
claim full Rust backend production
```

The result keeps:

```text
full_rust_backend = false
production_collector_authority_switched = false
collector_authority_promotion_supported = false
collector_authority_promotion_executed = false
rust_can_drive_cleanup = false
rust_can_drive_apply = false
rust_can_write_generated_files = false
```

## API endpoint

```text
GET  /api/rust-core/collector-authority-promotion-readiness
POST /api/rust-core/collector-authority-promotion-readiness
```

Example:

```bash
curl -X POST http://YOUR-LQOSYNC/api/rust-core/collector-authority-promotion-readiness \
  -H 'Content-Type: application/json' \
  -d '{
    "confirmation": "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
    "shadow_age_seconds": 10,
    "rust_core": {
      "collector_authority_promotion_readiness_pilot": true,
      "allow_collector_authority_promotion_readiness": true,
      "collector_authority_promotion_readiness_mode": "rust_collector_authority_promotion_readiness"
    },
    "collector_authority_pilot_result_evaluation": {
      "status": "collector_authority_pilot_result_pass",
      "collector_authority_pilot_result_evaluated": true,
      "python_collector_fallback_required": true,
      "production_collector_authority_switched": false
    }
  }'
```

## New config defaults

```json
{
  "rust_core": {
    "collector_authority_promotion_readiness_pilot": false,
    "allow_collector_authority_promotion_readiness": false,
    "collector_authority_promotion_readiness_mode": "readiness_only",
    "collector_authority_promotion_require_pilot_result": true,
    "collector_authority_promotion_require_python_fallback": true,
    "collector_authority_promotion_require_manual_confirmation": true,
    "collector_authority_promotion_require_no_cleanup_apply": true,
    "collector_authority_promotion_max_shadow_age_seconds": 900
  }
}
```

## Commit message

```bash
git add .
git commit -m "rust(core): add collector authority promotion readiness" \
  -m "Add build-collector-authority-promotion-readiness, a non-mutating readiness bridge after pilot result evaluation that requires explicit gates, manual confirmation, fresh Rust-shadow data, and Python fallback before any future collector authority promotion."
git push -u origin lqosync-in-rust
```
