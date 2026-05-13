import json
import time
from pathlib import Path

from engine.config_loader import load_config
from engine.context import SyncContext
from engine.result import SyncResult
from engine.diff import diff_rows, diff_network
from engine.hash_utils import sha256_text
from engine.state import update_state, load_state
from engine.logging_utils import log_event

from collectors.mikrotik_client import connect_to_router
from collectors.pppoe import process_pppoe_users
from collectors.hotspot import process_hotspot_users
from collectors.dhcp import process_dhcp_leases

from builders.shaped_devices import read_shaped_devices_csv, render_shaped_devices_csv, count_by_comment
from builders.network_json import read_network_json, render_network_json, ensure_router_root, ensure_router_node, count_nodes
from rules.network_mode import get_network_mode, is_deep_hierarchy
from rules.cleanup import remove_inactive_entries, remove_inactive_entries_by_source
from validators.preflight import run_preflight
from applier.backup import create_backup
from applier.atomic_writer import atomic_write_text
from applier.libreqos_runner import run_libreqos_update
from engine.lockfile import InterProcessLock, LockBusy
from engine.audit import write_audit
from engine.change_summary import build_client_change_summary
from engine.collector_cache import cache_path as collector_cache_path, load_cache as load_collector_cache, save_cache as save_collector_cache
from engine.policy_state import load_policy_state, save_policy_state, prune_expired, cleanup_queue_remove
from engine.policy_engine import (
    build_cleanup_candidates, evaluate_cleanup_policy, evaluate_apply_guards,
    existing_source_counts, update_successful_source_counts,
)


class Timeline:
    def __init__(self, result: SyncResult):
        self.result = result

    def record(self, name: str, start: float, status: str = "ok", details: dict | None = None):
        ms = round((time.perf_counter() - start) * 1000, 3)
        self.result.timings[name] = ms
        self.result.timeline.append({"step": name, "duration_ms": ms, "status": status, "details": details or {}})
        return ms


def read_text(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def _drift_check(config: dict, state: dict, current_csv_text: str, current_network_text: str, result: SyncResult) -> bool:
    """Return True if apply may continue. Drift is only enforced when previous hashes exist."""
    policy = config.get("app", {}).get("file_drift_policy", "overwrite_with_backup")
    last_hashes = state.get("last_file_hashes") or {}
    if not last_hashes:
        return True
    current_hashes = {
        "csv": sha256_text(current_csv_text),
        "network": sha256_text(current_network_text),
    }
    drifted = []
    if last_hashes.get("csv") and last_hashes.get("csv") != current_hashes["csv"]:
        drifted.append("ShapedDevices.csv")
    if last_hashes.get("network") and last_hashes.get("network") != current_hashes["network"]:
        drifted.append("network.json")
    if not drifted:
        return True
    msg = "External file drift detected: " + ", ".join(drifted)
    if policy == "block":
        result.errors.append(msg + "; apply blocked by file_drift_policy=block")
        return False
    if policy == "warn_only":
        result.warnings.append(msg + "; continuing by policy warn_only")
        return True
    result.warnings.append(msg + "; current files will be backed up before overwrite")
    return True


def _libreqos_should_apply(config: dict, state: dict, result: SyncResult, mode: str) -> tuple[bool, str]:
    """Decide whether LibreQoS.py should run after a non-dry-run cycle.

    Policy:
      - Dry-run never applies.
      - If app.auto_apply is enabled and files changed, apply immediately.
      - If the last LibreQoS apply failed, keep a pending apply marker and retry
        even when files are unchanged. This closes the gap where files were
        written successfully but LibreQoS.py failed on the first apply attempt.
      - Manual force_apply mode always applies.
    """
    if mode == "dry_run":
        return False, "dry_run"
    lib = config.get("libreqos", {})
    if mode == "force_apply":
        return True, "force_apply"
    if not bool(config.get("app", {}).get("auto_apply", True)):
        return False, "auto_apply_disabled"
    if result.files_changed:
        return True, "files_changed"
    retry_failed = bool(lib.get("retry_if_last_apply_failed", True))
    pending = bool(state.get("pending_libreqos_apply") or state.get("last_libreqos_apply_failed"))
    if retry_failed and pending:
        return True, "retry_pending_failed_apply"
    return False, "no_changes"


def _mark_libreqos_state(state_path: str, result: SyncResult, ok: bool, reason: str):
    update_state(
        state_path,
        last_libreqos_apply_success=bool(ok),
        last_libreqos_apply_failed=not bool(ok),
        pending_libreqos_apply=not bool(ok),
        last_libreqos_apply_reason=reason,
        last_libreqos_exit_code=result.libreqos_exit_code,
    )


def _run_libreqos_apply(config: dict, state_path: str, result: SyncResult, timeline: Timeline, reason: str):
    t = time.perf_counter()
    lq = run_libreqos_update(config)
    timeline.record("libreqos_apply", t, status="ok" if lq.get("ok") else "failed", details={"exit_code": lq.get("exit_code"), "run_id": lq.get("run_id"), "reason": reason, "working_dir": lq.get("working_dir")})
    result.libreqos_triggered = True
    result.libreqos_exit_code = lq["exit_code"]
    result.libreqos_stdout = lq["stdout"]
    result.libreqos_stderr = lq["stderr"]
    result.diff["libreqos_command"] = lq.get("command")
    result.diff["libreqos_run_id"] = lq.get("run_id")
    result.diff["libreqos_duration_ms"] = lq.get("duration_ms")
    result.diff["libreqos_apply_reason"] = reason
    result.diff["libreqos_working_dir"] = lq.get("working_dir")
    if lq["ok"]:
        _mark_libreqos_state(state_path, result, True, reason)
    else:
        _mark_libreqos_state(state_path, result, False, reason)
    return lq


def _run_cycle_unlocked(mode="apply", config_path=None):
    cycle_start = time.perf_counter()
    result = SyncResult(mode=mode)
    timeline = Timeline(result)
    t = time.perf_counter()
    config = load_config(config_path)
    timeline.record("config_load", t)
    paths = config["paths"]
    state_path = paths.get("runtime_state", "state/runtime_state.json")
    t = time.perf_counter()
    state_before = load_state(state_path)
    timeline.record("state_load", t)

    t = time.perf_counter()
    cache_file = collector_cache_path(config)
    collector_cache = load_collector_cache(cache_file)
    timeline.record("collector_cache_load", t, details={"path": cache_file})

    t = time.perf_counter()
    policy_state = load_policy_state(config)
    prune_expired(policy_state)
    timeline.record("policy_state_load", t, details={"pending_confirmations": len(policy_state.get("pending_confirmations", [])), "queued_cleanup": len(policy_state.get("cleanup_queue", []))})

    log_event(config, "info", f"Starting sync cycle mode={mode}")
    write_audit(config, "sync_started", details={"mode": mode})
    try:
        update_state(state_path, sync_running=True, scheduler_state="running")
    except Exception:
        pass

    try:
        csv_path = paths["shaped_devices_csv"]
        network_path = paths["network_json"]

        t = time.perf_counter()
        current_csv_text = read_text(csv_path)
        timeline.record("csv_read_text", t, details={"path": csv_path})

        t = time.perf_counter()
        current_network_text = read_text(network_path)
        timeline.record("network_read_text", t, details={"path": network_path})

        t = time.perf_counter()
        current_rows = read_shaped_devices_csv(csv_path)
        existing_data = {k: dict(v) for k, v in current_rows.items()}
        timeline.record("csv_parse", t, details={"rows": len(existing_data)})

        t = time.perf_counter()
        current_network = read_network_json(network_path)
        timeline.record("network_parse", t)

        t = time.perf_counter()
        network_mode = get_network_mode(config)
        preserve_network = bool(config.get("preserve_network_config", False))
        if network_mode == "flat_no_parent":
            network_config = json.loads(json.dumps(current_network)) if preserve_network else {}
        elif network_mode == "flat_router_root":
            network_config = json.loads(json.dumps(current_network)) if preserve_network else {}
        else:
            network_config = json.loads(json.dumps(current_network))
        timeline.record("network_mode_prepare", t, details={"network_mode": network_mode})

        ctx = SyncContext(config=config, existing_data=existing_data, network_config=network_config, network_mode=network_mode)
        ctx.cache = collector_cache
        ctx.cache_path = cache_file
        enabled_routers = [r for r in config.get("routers", []) if r.get("enabled", True)]
        if not enabled_routers:
            result.warnings.append("No enabled routers configured. Nothing to sync.")

        t_routers = time.perf_counter()
        for router in enabled_routers:
            router_t = time.perf_counter()
            if network_mode != "flat_no_parent":
                router_node = ensure_router_node(ctx.network_config, router, allow_parent=is_deep_hierarchy(config))
                ctx.router_nodes[router["name"]] = router_node
                if network_mode == "flat_router_root":
                    router_node["children"] = {}
            connect_t = time.perf_counter()
            pool, api, err = connect_to_router(router)
            timeline.record(f"router.{router.get('name','unknown')}.connect", connect_t, status="ok" if api else "failed")
            if not api:
                result.router_errors.append({"router": router.get("name"), "error": err})
                ctx.errors.append(f"Router {router.get('name')} failed: {err}")
                timeline.record(f"router.{router.get('name','unknown')}.total", router_t, status="failed")
                continue
            try:
                router_active = set()
                router_updated = False
                source_success = set()
                for pname, processor in (("pppoe", process_pppoe_users), ("hotspot", process_hotspot_users), ("dhcp", process_dhcp_leases)):
                    pt = time.perf_counter()
                    try:
                        active_codes, updated = processor(api, router, ctx)
                        source_label = {"pppoe": "PPP", "dhcp": "DHCP", "hotspot": "HS"}.get(pname, pname.upper())
                        source_success.add(source_label)
                        timeline.record(f"router.{router.get('name','unknown')}.{pname}", pt, details={"active": len(active_codes), "updated": bool(updated), "source_success": True})
                        router_active.update(active_codes)
                        router_updated = router_updated or updated
                    except Exception as source_error:
                        source_label = {"pppoe": "PPP", "dhcp": "DHCP", "hotspot": "HS"}.get(pname, pname.upper())
                        result.router_errors.append({"router": router.get("name"), "source": source_label, "error": str(source_error)})
                        ctx.errors.append(f"Router {router.get('name')} {source_label} processing error: {source_error}")
                        timeline.record(f"router.{router.get('name','unknown')}.{pname}", pt, status="failed", details={"error": str(source_error), "source_success": False})
                ctx.active_codes.update(router_active)
                ctx.active_codes_by_router[router["name"]] = router_active
                ctx.source_success_by_router[router["name"]] = source_success
                if source_success:
                    ctx.router_success_names.add(router["name"])
                result.routers_processed += 1
                timeline.record(f"router.{router.get('name','unknown')}.total", router_t, details={"active": len(router_active), "updated": bool(router_updated), "source_success": sorted(source_success)})
            except Exception as e:
                result.router_errors.append({"router": router.get("name"), "error": str(e)})
                ctx.errors.append(f"Router {router.get('name')} processing error: {e}")
                timeline.record(f"router.{router.get('name','unknown')}.total", router_t, status="failed", details={"error": str(e)})
            finally:
                try:
                    pool.disconnect()
                except Exception:
                    pass
        timeline.record("routers_total", t_routers, details={"processed": result.routers_processed})

        t = time.perf_counter()
        enabled_names = {r.get("name") for r in enabled_routers}
        cleanup_sources = set()
        if enabled_names:
            for source in ("PPP", "DHCP", "HS"):
                if all(source in ctx.source_success_by_router.get(name, set()) for name in enabled_names):
                    cleanup_sources.add(source)
        else:
            result.warnings.append("Skipping inactive cleanup: no enabled routers.")

        active_counts_by_source = {src: len(ctx.active_codes_by_source.get(src, set())) for src in ("PPP", "DHCP", "HS")}
        existing_counts_before_cleanup = existing_source_counts(ctx.existing_data, config["defaults"].get("static_comment_value", "static"))
        cleanup_candidates = build_cleanup_candidates(ctx.existing_data, ctx.active_codes_by_source, cleanup_sources, config["defaults"].get("static_comment_value", "static"))
        policy_decision = evaluate_cleanup_policy(config, policy_state, cleanup_candidates, cleanup_sources, active_counts_by_source, existing_counts_before_cleanup)
        remove_codes = set(policy_decision.remove_codes)
        if remove_codes:
            for code in list(remove_codes):
                if code in ctx.existing_data:
                    del ctx.existing_data[code]
            cleanup_queue_remove(policy_state, remove_codes)
            result.files_changed = True
        cleanup_stats = {
            "sources": sorted(cleanup_sources),
            "candidates": len(cleanup_candidates),
            "removed": len(remove_codes),
            "queued": len(policy_decision.queued_codes),
            "preserved": len(policy_decision.preserve_codes),
            "verdict": policy_decision.verdict,
            "risk_level": policy_decision.risk_level,
        }
        ctx.collector_metrics["cleanup"] = cleanup_stats
        skipped_sources = sorted(set(["PPP", "DHCP", "HS"]) - cleanup_sources)
        if skipped_sources:
            result.warnings.append(f"Source-aware cleanup skipped for: {', '.join(skipped_sources)} because not all enabled routers scanned those sources successfully.")
        timeline.record("cleanup_policy", t, details=cleanup_stats)

        t = time.perf_counter()
        proposed_csv_text = render_shaped_devices_csv(ctx.existing_data)
        timeline.record("csv_render", t, details={"rows": len(ctx.existing_data)})

        t = time.perf_counter()
        proposed_network_text = render_network_json(ctx.network_config)
        timeline.record("network_render", t, details={"nodes": count_nodes(ctx.network_config)})

        t = time.perf_counter()
        result.csv_changed = current_csv_text != proposed_csv_text
        result.network_changed = current_network_text != proposed_network_text
        result.files_changed = result.csv_changed or result.network_changed
        result.diff = {
            "csv": diff_rows(current_rows, ctx.existing_data),
            "network": diff_network(current_network, ctx.network_config),
        }
        client_change_summary = build_client_change_summary(result.diff.get("csv", {}), ctx.meta)
        result.diff["client_change_summary"] = client_change_summary
        result.diff["client_changes"] = client_change_summary.get("changes", [])
        timeline.record("diff", t, details={"csv_changed": result.csv_changed, "network_changed": result.network_changed, "client_changes": client_change_summary.get("counts", {})})

        t = time.perf_counter()
        result.warnings.extend(ctx.warnings)
        result.errors.extend(ctx.errors)
        result.counts.update(ctx.counts)
        result.counts["csv_rows"] = len(ctx.existing_data)
        result.counts["nodes"] = count_nodes(ctx.network_config)
        result.counts.update({f"rows_{k}": v for k, v in count_by_comment(ctx.existing_data).items()})
        result.meta = ctx.meta
        result.node_math = ctx.node_math
        result.diff["collector_metrics"] = ctx.collector_metrics
        result.diff["speed_source_breakdown"] = ctx.speed_source_counts
        result.diff["cache_metrics"] = ctx.cache_metrics
        result.counts["cache_hits"] = int(ctx.cache_metrics.get("hits", 0))
        result.counts["cache_misses"] = int(ctx.cache_metrics.get("misses", 0))
        result.file_hashes = {
            "current_csv": sha256_text(current_csv_text),
            "current_network": sha256_text(current_network_text),
            "proposed_csv": sha256_text(proposed_csv_text),
            "proposed_network": sha256_text(proposed_network_text),
        }
        timeline.record("metadata_hashes", t)

        t = time.perf_counter()
        try:
            save_collector_cache(cache_file, ctx.cache)
            ctx.cache_metrics["writes"] = ctx.cache_metrics.get("writes", 0) + 1
        except Exception as cache_error:
            result.warnings.append(f"Collector cache save failed: {cache_error}")
        timeline.record("collector_cache_save", t, details={"path": cache_file, "cache_metrics": ctx.cache_metrics})

        t = time.perf_counter()
        preflight = run_preflight(ctx.existing_data, ctx.network_config, config)
        result.warnings.extend(preflight["warnings"])
        result.errors.extend(preflight["errors"])
        timeline.record("preflight", t, status="failed" if result.errors else "ok", details={"warnings": len(preflight["warnings"]), "errors": len(preflight["errors"])})

        t = time.perf_counter()
        policy_decision = evaluate_apply_guards(config, policy_decision, preflight, result)
        result.diff["policy_decision"] = policy_decision.to_dict()
        policy_state["last_policy_decision"] = policy_decision.to_dict()
        for w in policy_decision.warnings:
            msg = w.get("message") or w.get("title")
            if msg:
                result.warnings.append(f"Policy: {msg}")
        if policy_decision.blocked_reasons:
            for b in policy_decision.blocked_reasons:
                result.errors.append(f"Policy blocked: {b.get('message') or b.get('title')}")
        save_policy_state(config, policy_state)
        timeline.record("policy_evaluation", t, status="blocked" if not policy_decision.write_allowed else policy_decision.verdict, details={"verdict": policy_decision.verdict, "risk_level": policy_decision.risk_level, "risk_score": policy_decision.risk_score})

        if mode == "dry_run":
            result.finish("dry_run_complete")
            result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
            log_event(config, "info", f"Dry-run complete: csv_changed={result.csv_changed} network_changed={result.network_changed} policy={policy_decision.verdict}")
            write_audit(config, "dry_run_complete", details={"csv_changed": result.csv_changed, "network_changed": result.network_changed, "status": result.status, "policy_decision": policy_decision.to_dict(), "timings": result.timings})
            update_state(state_path, sync_running=False, scheduler_state="idle", last_dry_run=result.to_dict(), last_error=None)
            return result

        if not policy_decision.write_allowed:
            result.finish("policy_blocked")
            result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
            log_event(config, "error", f"Policy blocked sync: {policy_decision.verdict} risk={policy_decision.risk_level}")
            write_audit(config, "policy_blocked", details={"policy_decision": policy_decision.to_dict(), "timings": result.timings})
            update_state(state_path, sync_running=False, scheduler_state="error", last_run=result.to_dict(), last_error="policy_blocked")
            return result

        if result.errors:
            result.finish("preflight_failed")
            result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
            log_event(config, "error", f"Preflight failed: {result.errors}")
            update_state(state_path, sync_running=False, scheduler_state="error", last_run=result.to_dict(), last_error="preflight_failed")
            return result

        files_were_written = False
        if result.files_changed:
            t = time.perf_counter()
            if not _drift_check(config, state_before, current_csv_text, current_network_text, result):
                timeline.record("drift_check", t, status="blocked")
                result.finish("file_drift_blocked")
                result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
                update_state(state_path, sync_running=False, scheduler_state="error", last_run=result.to_dict(), last_error="file_drift_blocked")
                return result
            timeline.record("drift_check", t)

            if config.get("app", {}).get("backup_before_apply", True):
                t = time.perf_counter()
                result.diff["backup_path"] = create_backup(config, reason=mode)
                timeline.record("backup", t, details={"path": result.diff.get("backup_path")})
                write_audit(config, "backup_created", details={"path": result.diff.get("backup_path"), "reason": mode})

            t = time.perf_counter()
            atomic_write_text(csv_path, proposed_csv_text)
            timeline.record("csv_write", t, details={"path": csv_path, "changed": result.csv_changed})

            t = time.perf_counter()
            atomic_write_text(network_path, proposed_network_text)
            timeline.record("network_write", t, details={"path": network_path, "changed": result.network_changed})
            write_audit(config, "files_written", details={"csv_changed": result.csv_changed, "network_changed": result.network_changed, "client_change_summary": result.diff.get("client_change_summary"), "client_changes": result.diff.get("client_changes", []), "timings": result.timings})
            if result.diff.get("client_change_summary", {}).get("counts", {}).get("total", 0):
                write_audit(config, "client_changes", details={"summary": result.diff.get("client_change_summary"), "changes": result.diff.get("client_changes", []), "timings": result.timings})
            files_were_written = True

            # Mark a pending apply immediately after successful file writes. If
            # LibreQoS.py fails, later cycles can retry even when files are no
            # longer changed.
            update_state(state_path, pending_libreqos_apply=True, last_file_write_success=True)

        should_run_lq, apply_reason = _libreqos_should_apply(config, state_before, result, mode)
        result.diff["libreqos_apply_decision"] = apply_reason
        if should_run_lq:
            lq = _run_libreqos_apply(config, state_path, result, timeline, apply_reason)
            write_audit(config, "libreqos_apply", details={"ok": lq.get("ok"), "exit_code": lq.get("exit_code"), "run_id": lq.get("run_id"), "reason": apply_reason})
            if not lq["ok"]:
                result.errors.append("LibreQoS update failed")
                result.finish("libreqos_failed")
                result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
                log_event(config, "error", f"LibreQoS failed: reason={apply_reason} exit={result.libreqos_exit_code} stderr={result.libreqos_stderr[:500]}")
                update_state(state_path, sync_running=False, scheduler_state="error", last_run=result.to_dict(), last_error="libreqos_failed")
                return result
        elif files_were_written:
            # This can only happen when app.auto_apply=false. Keep pending state
            # visible so the operator knows a manual/force apply is needed.
            update_state(state_path, pending_libreqos_apply=True, last_libreqos_apply_reason=apply_reason)

        result.finish("success")
        result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
        try:
            update_successful_source_counts(policy_state, cleanup_sources, active_counts_by_source, {k: int(v.get("active_count", 0) or 0) for k, v in (ctx.node_math or {}).items() if isinstance(v, dict)})
            save_policy_state(config, policy_state)
        except Exception as policy_state_error:
            result.warnings.append(f"Policy state save failed: {policy_state_error}")
        log_event(config, "info", f"Sync success: files_changed={result.files_changed} libreqos_triggered={result.libreqos_triggered} duration_ms={result.timings.get('cycle_total')}")
        write_audit(config, "sync_finished", details={"status": result.status, "files_changed": result.files_changed, "libreqos_triggered": result.libreqos_triggered, "libreqos_exit_code": result.libreqos_exit_code, "client_change_summary": result.diff.get("client_change_summary"), "policy_decision": result.diff.get("policy_decision"), "timings": result.timings})
        update_state(
            state_path,
            sync_running=False,
            scheduler_state="idle",
            last_run=result.to_dict(),
            last_error=None,
            last_file_hashes={"csv": result.file_hashes["proposed_csv"], "network": result.file_hashes["proposed_network"]},
        )
        return result
    except Exception as e:
        result.errors.append(str(e))
        result.finish("failed")
        result.timings["cycle_total"] = round((time.perf_counter() - cycle_start) * 1000, 3)
        try:
            log_event(config if "config" in locals() else {}, "error", f"Sync failed: {e}")
            write_audit(config if "config" in locals() else {}, "sync_failed", details={"error": str(e), "mode": mode, "timings": result.timings})
        except Exception:
            pass
        try:
            update_state(state_path, sync_running=False, scheduler_state="error", last_run=result.to_dict(), last_error=str(e))
        except Exception:
            pass
        return result
    finally:
        if not result.duration_seconds:
            result.duration_seconds = round((time.perf_counter() - cycle_start), 3)


def run_cycle(mode="apply", config_path=None):
    """Run one sync cycle with an inter-process lock."""
    cfg = load_config(config_path)
    state_path = cfg["paths"].get("runtime_state", "state/runtime_state.json")
    lock_path = cfg["paths"].get("lock_file") or str(Path(state_path).with_name("lqosync.lock"))
    try:
        with InterProcessLock(lock_path):
            return _run_cycle_unlocked(mode=mode, config_path=config_path)
    except LockBusy as e:
        result = SyncResult(mode=mode)
        result.warnings.append(str(e))
        result.finish("already_running")
        try:
            update_state(state_path, sync_running=True, scheduler_state="running", last_error=str(e))
        except Exception:
            pass
        return result
