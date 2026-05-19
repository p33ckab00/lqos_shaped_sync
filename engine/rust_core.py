"""Optional Python wrapper for the LQoSync Rust safety core.

The Rust core is introduced as an optional sidecar. If the binary is missing or
returns malformed output, Python keeps the existing sync path and records a
non-blocking unavailable/fallback result. This allows the `lqosync-in-rust`
branch to harden deterministic validation without breaking current installs.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1"
DEFAULT_SOCKET = "/run/lqosync-core.sock"



def _python_collector_contract(envelope: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Local fallback for the collector trust contract.

    This mirrors the Rust `validate-collector-output` behavior so the safety
    semantics are available even before the Rust binary is built. The Rust core
    remains the preferred implementation when available.
    """
    started = started or time.perf_counter()
    router = str(envelope.get("router") or "unknown")
    source = str(envelope.get("source") or "unknown")
    status = str(envelope.get("status") or "ok")
    rows = envelope.get("rows") if isinstance(envelope.get("rows"), list) else []
    row_count = len(rows)
    try:
        previous_success_count = int(envelope.get("previous_success_count") or 0)
    except Exception:
        previous_success_count = 0
    failed_reads = envelope.get("failed_reads") if isinstance(envelope.get("failed_reads"), list) else []
    safe_for_cleanup = True
    errors = []
    warnings = []
    if status in {"failed", "partial"} or failed_reads:
        safe_for_cleanup = False
        errors.append({
            "code": "collector_not_trusted",
            "severity": "error",
            "path": f"collector.{router}.{source}",
            "message": f"Collector output for {router}/{source} is not trusted: status={status}, failed_reads={len(failed_reads)}",
            "safe_for_cleanup": False,
        })
    if row_count == 0 and previous_success_count > 0 and status != "zero_valid":
        safe_for_cleanup = False
        warnings.append({
            "code": "collector_zero_suspicious",
            "severity": "warning",
            "path": f"collector.{router}.{source}.rows",
            "message": f"Collector returned zero rows for {router}/{source} after previous successful non-zero run",
            "value": row_count,
            "safe_for_cleanup": False,
        })
    return {
        "version": PROTOCOL_VERSION,
        "op": "validate-collector-output",
        "request_id": envelope.get("request_id"),
        "available": False,
        "ok": not errors,
        "result": {
            "router": router,
            "source": source,
            "status": status,
            "row_count": row_count,
            "safe_for_cleanup": safe_for_cleanup,
            "write_allowed": not errors,
            "apply_allowed": not errors,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {
            "engine": "python-wrapper",
            "mode": "python_contract_fallback",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }


def collector_output_envelope(router: dict | str, source: str, active_codes, *, previous_success_count: int = 0, status: str = "ok", failed_reads: list[str] | None = None, read_counts: dict[str, Any] | None = None, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    router_name = router.get("name") if isinstance(router, dict) else router
    rows = sorted(str(code) for code in (active_codes or []))
    # A never-before-seen zero result can be legitimate on a fresh source, but a
    # zero result after prior success must be classified by the validator as
    # suspicious unless the caller explicitly marks it zero_valid.
    effective_status = status
    if not rows and int(previous_success_count or 0) <= 0 and status == "ok":
        effective_status = "zero_valid"
    return {
        "router": str(router_name or "unknown"),
        "source": str(source or "unknown"),
        "status": effective_status,
        "rows": rows,
        "previous_success_count": int(previous_success_count or 0),
        "failed_reads": failed_reads or [],
        "read_counts": read_counts or {},
        "metrics": metrics or {},
    }


def rust_diff_files(config: dict, *, current_csv_text: str, proposed_csv_text: str, current_network_text: str, proposed_network_text: str) -> dict[str, Any]:
    payload = {
        "current_csv_text": current_csv_text or "",
        "proposed_csv_text": proposed_csv_text or "",
        "current_network_text": current_network_text or "{}",
        "proposed_network_text": proposed_network_text or "{}",
    }
    return call_rust_core("diff-files", payload, config=config)


def _risk_level(score: int) -> str:
    if score >= 81:
        return "critical"
    if score >= 51:
        return "high"
    if score >= 21:
        return "medium"
    return "low"


def _python_policy_shadow(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust `evaluate-policy` shadow mode.

    Python remains authoritative in v0.5. This fallback mirrors the Rust shadow
    payload shape so Dry Run and reports stay stable when the binary/daemon is
    unavailable.
    """
    started = started or time.perf_counter()
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    collector_trust = payload.get("collector_trust") if isinstance(payload.get("collector_trust"), list) else []
    cleanup = payload.get("cleanup") if isinstance(payload.get("cleanup"), dict) else {}
    rust_validation = payload.get("rust_validation") if isinstance(payload.get("rust_validation"), dict) else {}
    python_decision = payload.get("python_policy_decision") if isinstance(payload.get("python_policy_decision"), dict) else {}
    apply_guard = (config.get("policies") or {}).get("apply_guard") or {}

    blocked = []
    warnings = []
    trace = []
    recommendations = []
    risk_score = 0
    cleanup_allowed = True
    write_allowed = True
    apply_allowed = True

    errors_text = "\n".join(str(e) for e in (preflight.get("errors") or [])).lower()
    if errors_text:
        if apply_guard.get("block_apply_on_duplicate_ip", True) and "duplicate ip" in errors_text:
            blocked.append({"code": "duplicate_ip", "title": "Duplicate IP detected", "message": "Preflight detected duplicate IP addresses.", "severity": "critical"})
        if apply_guard.get("block_apply_on_missing_parent", True) and "parent" in errors_text:
            blocked.append({"code": "missing_parent", "title": "Missing parent node", "message": "One or more circuits reference missing Parent Node values.", "severity": "critical"})
        if apply_guard.get("block_apply_on_invalid_speed", True) and ("bandwidth" in errors_text or "speed" in errors_text):
            blocked.append({"code": "invalid_speed", "title": "Invalid speed/bandwidth", "message": "Preflight detected invalid speed or bandwidth values.", "severity": "critical"})
        if not blocked:
            blocked.append({"code": "preflight_errors", "title": "Preflight errors", "message": "Preflight returned one or more errors.", "severity": "critical"})
        risk_score += 35
        trace.append({"policy": "preflight", "decision": "errors_present"})

    unsafe_sources = []
    for item in collector_trust:
        result = item.get("result") if isinstance(item.get("result"), dict) else item
        if isinstance(result, dict) and result.get("safe_for_cleanup") is False:
            unsafe_sources.append(f"{result.get('router','unknown')}/{result.get('source','unknown')}")
    if unsafe_sources:
        cleanup_allowed = False
        risk_score += 25
        warnings.append({"title": "Collector cleanup held", "message": "Unsafe collector output held cleanup for: " + ", ".join(unsafe_sources), "severity": "high", "sources": unsafe_sources})
        trace.append({"policy": "collector_trust", "decision": "cleanup_held", "unsafe_count": len(unsafe_sources)})
        if apply_guard.get("block_apply_on_collector_failure", True):
            blocked.append({"code": "collector_not_trusted", "title": "Collector trust failure", "message": "One or more collector outputs were not trusted for cleanup/apply.", "severity": "critical"})

    if rust_validation and (rust_validation.get("ok") is False or rust_validation.get("errors")):
        risk_score += 30
        blocked.append({"code": "rust_validation_failed", "title": "Rust validation failed", "message": "Rust validation reported errors in proposed output.", "severity": "critical"})

    removed = int(cleanup.get("removed") or 0)
    queued = int(cleanup.get("queued") or 0)
    preserved = int(cleanup.get("preserved") or 0)
    if removed:
        risk_score += min(25, removed * 4)
        warnings.append({"title": "Rows removed by cleanup", "message": f"{removed} row(s) are scheduled for removal by cleanup policy.", "severity": "high" if removed >= 10 else "warning", "affected_rows": removed})
    if queued or preserved:
        risk_score += min(20, (queued + preserved) * 2)

    if blocked:
        write_allowed = False
        apply_allowed = False
        cleanup_allowed = False
    risk_score = min(100, risk_score + len(blocked) * 30)
    risk_level = _risk_level(risk_score)
    verdict = "blocked_by_policy" if blocked or risk_level == "critical" else ("apply_with_caution" if risk_level in {"medium", "high"} else "safe_to_apply")
    if verdict == "blocked_by_policy":
        write_allowed = False
        apply_allowed = False
        recommendations.append({"title": "Review blocked policy decision", "reason": "Rust/Python shadow found blocking conditions.", "action": "Review Dry Run diagnostics before applying.", "severity": "critical"})

    parity = {"available": bool(python_decision)}
    if python_decision:
        parity.update({
            "matches_verdict": python_decision.get("verdict") == verdict,
            "matches_risk_level": python_decision.get("risk_level") == risk_level,
            "matches_write_allowed": python_decision.get("write_allowed") == write_allowed,
            "matches_apply_allowed": python_decision.get("apply_allowed") == apply_allowed,
            "python": {k: python_decision.get(k) for k in ("verdict", "risk_level", "write_allowed", "apply_allowed")},
            "rust": {"verdict": verdict, "risk_level": risk_level, "write_allowed": write_allowed, "apply_allowed": apply_allowed},
        })
        if not parity.get("matches_verdict", True):
            warnings.append({"title": "Policy parity mismatch", "message": "Shadow policy verdict differs from Python policy verdict. Python remains authoritative in this release.", "severity": "warning", "python_verdict": python_decision.get("verdict"), "rust_verdict": verdict})

    return {
        "version": PROTOCOL_VERSION,
        "op": "evaluate-policy",
        "available": False,
        "ok": True,
        "result": {
            "verdict": verdict,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "apply_allowed": apply_allowed,
            "write_allowed": write_allowed,
            "cleanup_allowed": cleanup_allowed,
            "blocked_reasons": blocked,
            "warnings": warnings,
            "recommendations": recommendations,
            "decision_trace": trace,
            "parity": parity,
            "mode": "shadow",
            "authoritative": False,
        },
        "errors": [],
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_policy_shadow_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }



def _record_number(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        val = record.get(key)
        if val is None or val == "":
            continue
        try:
            num = float(val)
            if num == num:
                return num
        except Exception:
            continue
    return None


def _python_normalize_circuits(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust `normalize-circuits` shadow mode."""
    started = started or time.perf_counter()
    source = str(payload.get("source") or "mixed")
    router = str(payload.get("router") or "mixed")
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    try:
        min_rate = float(payload.get("min_rate_percentage", 0.5))
    except Exception:
        min_rate = 0.5
    min_rate = min(max(min_rate, 0.0), 1.0)
    normalized = []
    errors = []
    warnings = []
    seen_ips: dict[str, str] = {}
    for idx, rec in enumerate(records):
        rec = rec if isinstance(rec, dict) else {}
        code = str(rec.get("code") or rec.get("circuit_name") or rec.get("Circuit Name") or "").strip()
        name = str(rec.get("device_name") or rec.get("Device Name") or rec.get("name") or code).strip()
        parent = str(rec.get("parent_node") or rec.get("Parent Node") or "").strip()
        ipv4 = str(rec.get("ipv4") or rec.get("IPv4") or rec.get("address") or "").strip()
        mac = str(rec.get("mac") or rec.get("MAC") or "").strip()
        down = _record_number(rec, "download_max_mbps", "Download Max Mbps", "download_mbps", "base_rx")
        up = _record_number(rec, "upload_max_mbps", "Upload Max Mbps", "upload_mbps", "base_tx")
        label = code or f"record[{idx}]"
        if not code:
            errors.append({"code": "missing_circuit_name", "severity": "error", "path": f"records[{idx}].circuit_name", "message": "Circuit record is missing circuit_name/code"})
        if not parent:
            warnings.append({"code": "missing_parent_node", "severity": "warning", "path": f"records[{idx}].parent_node", "message": f"Circuit {label} has no Parent Node"})
        if not down or not up or down <= 0 or up <= 0:
            errors.append({"code": "invalid_circuit_speed", "severity": "error", "path": f"records[{idx}].speed", "message": f"Circuit {label} has invalid or missing download/upload Mbps"})
            continue
        if ipv4:
            if ipv4 in seen_ips:
                warnings.append({"code": "duplicate_ip", "severity": "warning", "path": f"records[{idx}].ipv4", "message": f"Duplicate IPv4 {ipv4}: {seen_ips[ipv4]} and {code}", "value": ipv4})
            else:
                seen_ips[ipv4] = code
        comment = str(rec.get("comment") or rec.get("Comment") or source).strip()
        comment = {"pppoe": "PPP", "ppp": "PPP", "hotspot": "HS", "hs": "HS", "dhcp": "DHCP"}.get(comment.lower(), comment.upper() if comment else "UNKNOWN")
        normalized.append({
            "Circuit ID": code,
            "Circuit Name": code,
            "Device ID": code,
            "Device Name": name,
            "Parent Node": parent,
            "MAC": mac,
            "IPv4": ipv4,
            "IPv6": str(rec.get("ipv6") or rec.get("IPv6") or ""),
            "Download Min Mbps": round(down * min_rate, 3),
            "Upload Min Mbps": round(up * min_rate, 3),
            "Download Max Mbps": round(down, 3),
            "Upload Max Mbps": round(up, 3),
            "Comment": comment,
        })
    source_counts: dict[str, int] = {}
    for row in normalized:
        source_counts[row.get("Comment", "UNKNOWN")] = source_counts.get(row.get("Comment", "UNKNOWN"), 0) + 1
    return {
        "version": PROTOCOL_VERSION,
        "op": "normalize-circuits",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "shadow",
            "authoritative": False,
            "source": source,
            "router": router,
            "input_count": len(records),
            "normalized_count": len(normalized),
            "invalid_count": len(errors),
            "warning_count": len(warnings),
            "source_counts": source_counts,
            "normalized_rows": normalized,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_circuit_shadow_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def _rows_to_circuit_records(rows: dict[str, dict[str, Any]], meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    meta = meta or {}
    records = []
    for code, row in (rows or {}).items():
        row = row or {}
        m = meta.get(code, {}) if isinstance(meta.get(code, {}), dict) else {}
        records.append({
            "code": code,
            "circuit_name": row.get("Circuit Name") or code,
            "device_name": row.get("Device Name") or row.get("Circuit Name") or code,
            "parent_node": row.get("Parent Node") or "",
            "mac": row.get("MAC") or "",
            "ipv4": row.get("IPv4") or "",
            "ipv6": row.get("IPv6") or "",
            "download_min_mbps": row.get("Download Min Mbps") or "",
            "upload_min_mbps": row.get("Upload Min Mbps") or "",
            "download_max_mbps": row.get("Download Max Mbps") or m.get("base_rx") or "",
            "upload_max_mbps": row.get("Upload Max Mbps") or m.get("base_tx") or "",
            "comment": row.get("Comment") or m.get("source_type") or "",
            "source_type": m.get("source_type") or row.get("Comment") or "",
            "speed_source": m.get("speed_source") or "",
            "router": m.get("router") or "",
        })
    return records


def rust_normalize_circuits(config: dict, rows: dict[str, dict[str, Any]], *, meta: dict[str, Any] | None = None, source: str = "mixed", router: str = "mixed") -> dict[str, Any]:
    defaults = (config or {}).get("defaults", {}) if isinstance(config, dict) else {}
    payload = {
        "source": source,
        "router": router,
        "min_rate_percentage": defaults.get("min_rate_percentage", 0.5),
        "records": _rows_to_circuit_records(rows, meta),
    }
    response = call_rust_core("normalize-circuits", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_normalize_circuits(payload)
    return response


def _python_sync_plan_shadow(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust `evaluate-sync-plan` shadow mode."""
    started = started or time.perf_counter()
    mode = str(payload.get("mode") or "apply")
    files_changed = bool(payload.get("files_changed"))
    csv_changed = bool(payload.get("csv_changed"))
    network_changed = bool(payload.get("network_changed"))
    rust_validation = payload.get("rust_validation") if isinstance(payload.get("rust_validation"), dict) else {}
    rust_policy = payload.get("rust_policy_shadow") if isinstance(payload.get("rust_policy_shadow"), dict) else {}
    rust_circuit = payload.get("rust_circuit_shadow") if isinstance(payload.get("rust_circuit_shadow"), dict) else {}
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    collector_trust = payload.get("collector_trust") if isinstance(payload.get("collector_trust"), list) else []
    cleanup = payload.get("cleanup") if isinstance(payload.get("cleanup"), dict) else {}
    rust_diff = payload.get("rust_diff") if isinstance(payload.get("rust_diff"), dict) else {}
    risk_score = 0
    blockers = []
    holds = []
    trace = []
    warnings = []
    errors = []

    validation_errors = len(rust_validation.get("errors") or [])
    if validation_errors or rust_validation.get("ok") is False:
        risk_score += 35
        blockers.append({"code": "rust_validation_failed", "title": "Rust validation reported errors", "message": "Proposed CSV/network output failed Rust validation.", "severity": "critical", "count": validation_errors})
        errors.append({"code": "sync_plan_validation_blocker", "severity": "error", "path": "rust_validation", "message": "Rust validation errors block the shadow sync plan"})
        trace.append({"step": "validation", "decision": "block", "errors": validation_errors})
    else:
        trace.append({"step": "validation", "decision": "ok"})

    preflight_errors = len(preflight.get("errors") or [])
    if preflight_errors:
        risk_score += 35
        blockers.append({"code": "preflight_failed", "title": "Python preflight reported errors", "message": "The authoritative Python preflight returned one or more errors.", "severity": "critical", "count": preflight_errors})
        trace.append({"step": "preflight", "decision": "block", "errors": preflight_errors})
    else:
        trace.append({"step": "preflight", "decision": "ok"})

    unsafe = []
    for item in collector_trust:
        res = item.get("result") if isinstance(item, dict) and isinstance(item.get("result"), dict) else item
        if isinstance(res, dict) and res.get("safe_for_cleanup") is False:
            unsafe.append(f"{res.get('router','unknown')}/{res.get('source','unknown')}")
    if unsafe:
        risk_score += 25
        holds.append({"code": "collector_cleanup_held", "title": "Collector cleanup held", "message": "One or more collectors are not trusted for cleanup.", "severity": "high", "sources": unsafe})
        warnings.append({"code": "sync_plan_collector_cleanup_held", "severity": "warning", "path": "collector_trust", "message": "One or more collector outputs are not trusted for cleanup", "safe_for_cleanup": False})
        trace.append({"step": "collector_trust", "decision": "hold_cleanup"})
    else:
        trace.append({"step": "collector_trust", "decision": "ok"})

    policy_result = rust_policy.get("result") if isinstance(rust_policy.get("result"), dict) else {}
    policy_verdict = str(policy_result.get("verdict") or "unknown")
    try:
        risk_score = max(risk_score, int(policy_result.get("risk_score") or 0))
    except Exception:
        pass
    if policy_verdict == "blocked_by_policy":
        risk_score += 30
        blockers.append({"code": "policy_shadow_blocked", "title": "Rust policy shadow blocked", "message": "Rust policy shadow returned blocked_by_policy. Python policy remains authoritative.", "severity": "high"})
        trace.append({"step": "policy_shadow", "decision": "block_hint", "verdict": policy_verdict})
    elif policy_verdict == "apply_with_caution":
        risk_score += 12
        holds.append({"code": "policy_shadow_caution", "title": "Rust policy shadow recommends caution", "message": "Rust policy shadow returned apply_with_caution.", "severity": "warning"})
        trace.append({"step": "policy_shadow", "decision": "caution", "verdict": policy_verdict})
    else:
        trace.append({"step": "policy_shadow", "decision": "ok", "verdict": policy_verdict})

    circuit_errors = len(rust_circuit.get("errors") or [])
    circuit_warnings = len(rust_circuit.get("warnings") or [])
    if circuit_errors:
        risk_score += 25
        blockers.append({"code": "circuit_shadow_errors", "title": "Rust circuit shadow reported errors", "message": "Circuit normalization shadow reported invalid circuit rows.", "severity": "high", "count": circuit_errors})
    elif circuit_warnings:
        risk_score += 8

    diff_result = rust_diff.get("result") if isinstance(rust_diff.get("result"), dict) else {}
    csv_diff = diff_result.get("csv") if isinstance(diff_result.get("csv"), dict) else {}
    try:
        csv_change_count = int(csv_diff.get("added_count") or 0) + int(csv_diff.get("updated_count") or 0) + int(csv_diff.get("removed_count") or 0)
    except Exception:
        csv_change_count = 0
    if csv_change_count or network_changed:
        risk_score += 18 if csv_change_count > 20 else 6

    try:
        removed = int(cleanup.get("removed") or 0)
        queued = int(cleanup.get("queued") or 0)
    except Exception:
        removed, queued = 0, 0
    if removed:
        risk_score += min(18, removed * 3)
        holds.append({"code": "cleanup_removal_present", "title": "Cleanup removes rows", "message": f"Cleanup would remove {removed} row(s).", "severity": "high" if removed >= 10 else "warning", "affected_rows": removed})
    if queued:
        risk_score += 5

    risk_score = min(100, risk_score)
    risk_level = _risk_level(risk_score)
    dry_run = mode == "dry_run"
    write_allowed = not blockers and not dry_run
    apply_allowed = not blockers and not dry_run and files_changed
    cleanup_allowed = not blockers and not any(h.get("code") == "collector_cleanup_held" for h in holds)
    if blockers or risk_level == "critical":
        verdict = "blocked_by_shadow_plan"
        write_allowed = False
        apply_allowed = False
    elif holds or risk_level in {"medium", "high"}:
        verdict = "manual_review_recommended"
    elif not files_changed:
        verdict = "no_changes"
        write_allowed = False
        apply_allowed = False
    else:
        verdict = "ready_by_shadow_plan"

    next_actions = []
    if dry_run:
        next_actions.append({"title": "Review Dry Run", "action": "Inspect Rust/Python shadow diagnostics before switching to apply mode.", "severity": "info"})
    elif blockers:
        next_actions.append({"title": "Resolve blockers", "action": "Review validation, collector trust, circuit shadow, and policy diagnostics before applying.", "severity": "critical"})
    elif not files_changed:
        next_actions.append({"title": "No file changes", "action": "No generated file write/apply is needed.", "severity": "info"})
    else:
        next_actions.append({"title": "Apply candidate", "action": "Python remains authoritative; this Rust plan agrees there are no shadow blockers.", "severity": "info"})

    return {
        "version": PROTOCOL_VERSION,
        "op": "evaluate-sync-plan",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "shadow",
            "authoritative": False,
            "transport_safe": True,
            "input_mode": mode,
            "verdict": verdict,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "write_allowed": write_allowed,
            "apply_allowed": apply_allowed,
            "cleanup_allowed": cleanup_allowed,
            "files_changed": files_changed,
            "csv_changed": csv_changed,
            "network_changed": network_changed,
            "summary": {
                "csv_change_count": csv_change_count,
                "network_changed": network_changed,
                "collector_checks": len(collector_trust),
                "blocked_count": len(blockers),
                "hold_count": len(holds),
                "validation_errors": validation_errors,
                "preflight_errors": preflight_errors,
                "circuit_errors": circuit_errors,
                "policy_verdict": policy_verdict,
                "policy_risk_level": policy_result.get("risk_level", "unknown"),
            },
            "blockers": blockers,
            "holds": holds,
            "next_actions": next_actions,
            "decision_trace": trace,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_sync_plan_shadow_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_evaluate_sync_plan(config: dict, *, mode: str, files_changed: bool, csv_changed: bool, network_changed: bool, rust_diff: dict | None = None, rust_validation: dict | None = None, rust_policy_shadow: dict | None = None, rust_circuit_shadow: dict | None = None, collector_trust: list[dict[str, Any]] | None = None, preflight: dict | None = None, cleanup: dict | None = None) -> dict[str, Any]:
    payload = {
        "config": config or {},
        "mode": mode,
        "files_changed": bool(files_changed),
        "csv_changed": bool(csv_changed),
        "network_changed": bool(network_changed),
        "rust_diff": rust_diff or {},
        "rust_validation": rust_validation or {},
        "rust_policy_shadow": rust_policy_shadow or {},
        "rust_circuit_shadow": rust_circuit_shadow or {},
        "collector_trust": collector_trust or [],
        "preflight": preflight or {},
        "cleanup": cleanup or {},
        "authority": {
            "enabled": bool(rust_core_config(config).get("enforce_sync_plan", False)),
            "fail_closed_when_enforced": bool(rust_core_config(config).get("fail_closed_when_enforced", True)),
            "authority_mode": rust_core_config(config).get("authority_mode", "shadow"),
        },
    }
    response = call_rust_core("evaluate-sync-plan", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_sync_plan_shadow(payload)
    return response


def rust_evaluate_policy(config: dict, *, preflight: dict | None = None, collector_trust: list[dict[str, Any]] | None = None, cleanup: dict | None = None, rust_validation: dict | None = None, python_policy_decision: dict | None = None, diff_summary: dict | None = None) -> dict[str, Any]:
    payload = {
        "config": config or {},
        "preflight": preflight or {},
        "collector_trust": collector_trust or [],
        "cleanup": cleanup or {},
        "rust_validation": rust_validation or {},
        "python_policy_decision": python_policy_decision or {},
        "diff_summary": diff_summary or {},
    }
    response = call_rust_core("evaluate-policy", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    # Older installed Rust cores (v0.4 and below) do not know evaluate-policy.
    # Treat that as a transport/capability gap and use the Python shadow fallback.
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_policy_shadow(payload)
    return response



def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _python_apply_manifest(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust `build-apply-manifest`.

    This mirrors the Rust v0.9 transaction preview shape so Dry Run remains
    useful even when the Rust daemon/binary is unavailable.
    """
    started = started or time.perf_counter()
    mode = str(payload.get("mode") or "apply")
    dry_run = mode == "dry_run"
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else (config.get("paths") or {})
    current_csv = str(payload.get("current_csv_text") or "")
    proposed_csv = str(payload.get("proposed_csv_text") or "")
    current_network = str(payload.get("current_network_text") or "{}")
    proposed_network = str(payload.get("proposed_network_text") or "{}")
    csv_changed = bool(payload.get("csv_changed", current_csv != proposed_csv))
    network_changed = bool(payload.get("network_changed", current_network != proposed_network))
    files_changed = bool(payload.get("files_changed", csv_changed or network_changed))
    policy = payload.get("policy_decision") if isinstance(payload.get("policy_decision"), dict) else {}
    sync_plan = payload.get("rust_sync_plan") if isinstance(payload.get("rust_sync_plan"), dict) else {}
    sync_result = sync_plan.get("result") if isinstance(sync_plan.get("result"), dict) else {}
    gate = payload.get("rust_authority_gate") if isinstance(payload.get("rust_authority_gate"), dict) else {}
    authority_block = bool(gate.get("should_block") or ((sync_result.get("authority") or {}).get("would_block") if isinstance(sync_result.get("authority"), dict) else False))
    policy_write_allowed = bool(policy.get("write_allowed", True))
    policy_apply_allowed = bool(policy.get("apply_allowed", True))
    backup_before_apply = bool((config.get("app") or {}).get("backup_before_apply", False))
    auto_apply = bool((config.get("app") or {}).get("auto_apply", True))
    retry_failed = bool((config.get("libreqos") or {}).get("retry_if_last_apply_failed", True))
    pending_apply = bool(state.get("pending_libreqos_apply") or state.get("last_libreqos_apply_failed"))
    write_allowed = bool((not dry_run) and files_changed and policy_write_allowed and not authority_block)
    backup_required = bool(write_allowed and backup_before_apply)
    apply_required = bool((not dry_run) and policy_apply_allowed and not authority_block and ((auto_apply and files_changed) or (retry_failed and pending_apply) or mode == "force_apply"))
    operations = []
    if backup_required:
        operations.append({"op": "backup_live_files", "phase": "before_write", "required": True, "path": paths.get("backup_dir"), "reason": mode})
    if csv_changed:
        operations.append({"op": "write_file", "phase": "write", "file": "ShapedDevices.csv", "path": paths.get("shaped_devices_csv"), "allowed_now": write_allowed, "current_sha256": _sha256_text(current_csv), "proposed_sha256": _sha256_text(proposed_csv), "bytes": len(proposed_csv.encode("utf-8"))})
    if network_changed:
        operations.append({"op": "write_file", "phase": "write", "file": "network.json", "path": paths.get("network_json"), "allowed_now": write_allowed, "current_sha256": _sha256_text(current_network), "proposed_sha256": _sha256_text(proposed_network), "bytes": len(proposed_network.encode("utf-8"))})
    if write_allowed and files_changed:
        operations.append({"op": "mark_pending_apply", "phase": "post_write_state", "path": paths.get("runtime_state"), "allowed_now": True})
    if apply_required:
        operations.append({"op": "run_libreqos_update", "phase": "apply", "allowed_now": True, "cmd": (config.get("libreqos") or {}).get("cmd", "/opt/libreqos/src/LibreQoS.py"), "working_dir": (config.get("libreqos") or {}).get("working_dir", "/opt/libreqos/src"), "reason": "force_apply" if mode == "force_apply" else ("files_changed" if files_changed else "retry_pending_failed_apply")})
    status = "preview_only" if dry_run else ("blocked_by_authority_gate" if authority_block else ("blocked_by_policy" if not policy_write_allowed else ("no_changes" if not files_changed and not apply_required else "ready")))
    hashes = {"current_csv": _sha256_text(current_csv), "proposed_csv": _sha256_text(proposed_csv), "current_network": _sha256_text(current_network), "proposed_network": _sha256_text(proposed_network)}
    basis = json.dumps({"mode": mode, "paths": paths, "hashes": hashes, "operations": operations, "status": status}, sort_keys=True)
    manifest_id = "apply-" + _sha256_text(basis)[:16]
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-apply-manifest",
        "available": False,
        "ok": True,
        "result": {
            "mode": "transaction_preview",
            "authoritative": False,
            "manifest_id": manifest_id,
            "status": status,
            "input_mode": mode,
            "dry_run": dry_run,
            "files_changed": files_changed,
            "csv_changed": csv_changed,
            "network_changed": network_changed,
            "write_allowed": write_allowed,
            "apply_required": apply_required,
            "backup_required": backup_required,
            "policy_write_allowed": policy_write_allowed,
            "policy_apply_allowed": policy_apply_allowed,
            "authority_block": authority_block,
            "sync_plan_verdict": sync_result.get("verdict", "unknown"),
            "hashes": hashes,
            "operations": operations,
            "operation_count": len(operations),
            "trace": [],
        },
        "errors": [],
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_apply_manifest_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_apply_manifest(config: dict, *, mode: str, paths: dict, current_csv_text: str, proposed_csv_text: str, current_network_text: str, proposed_network_text: str, files_changed: bool, csv_changed: bool, network_changed: bool, policy_decision: dict | None = None, rust_sync_plan: dict | None = None, rust_authority_gate: dict | None = None, state: dict | None = None) -> dict[str, Any]:
    payload = {
        "config": config or {},
        "mode": mode,
        "paths": paths or {},
        "state": state or {},
        "current_csv_text": current_csv_text or "",
        "proposed_csv_text": proposed_csv_text or "",
        "current_network_text": current_network_text or "{}",
        "proposed_network_text": proposed_network_text or "{}",
        "files_changed": bool(files_changed),
        "csv_changed": bool(csv_changed),
        "network_changed": bool(network_changed),
        "policy_decision": policy_decision or {},
        "rust_sync_plan": rust_sync_plan or {},
        "rust_authority_gate": rust_authority_gate or {},
    }
    response = call_rust_core("build-apply-manifest", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_apply_manifest(payload)
    return response



def _python_execute_apply_transaction(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust `execute-apply-transaction`.

    Fallback intentionally never writes files. It mirrors the transaction
    rehearsal shape so the UI and Dry Run remain stable if an older Rust core is
    installed.
    """
    started = started or time.perf_counter()
    manifest = _python_apply_manifest(payload).get("result", {})
    return {
        "version": PROTOCOL_VERSION,
        "op": "execute-apply-transaction",
        "available": False,
        "ok": True,
        "result": {
            "mode": "transaction_executor",
            "authoritative": False,
            "executed": False,
            "status": "python_fallback_rehearsal_only",
            "manifest": manifest,
            "write_results": [],
            "write_count": 0,
            "execute_requested": bool(payload.get("execute")),
            "allow_file_writes": False,
            "allow_libreqos_apply": False,
            "libreqos_apply_executed": False,
            "trace": [{"step": "fallback", "decision": "no_file_writes"}],
        },
        "errors": [],
        "warnings": [{"code": "rust_transaction_executor_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust execute-apply-transaction is unavailable; Python fallback rehearsed only."}],
        "meta": {"engine": "python-wrapper", "mode": "python_transaction_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_execute_apply_transaction(config: dict, *, mode: str, paths: dict, current_csv_text: str, proposed_csv_text: str, current_network_text: str, proposed_network_text: str, files_changed: bool, csv_changed: bool, network_changed: bool, policy_decision: dict | None = None, rust_sync_plan: dict | None = None, rust_authority_gate: dict | None = None, state: dict | None = None, execute: bool | None = None) -> dict[str, Any]:
    rc = rust_core_config(config)
    do_execute = bool(rc.get("execute_apply_manifest") if execute is None else execute)
    payload = {
        "config": config or {},
        "mode": mode,
        "paths": paths or {},
        "state": state or {},
        "current_csv_text": current_csv_text or "",
        "proposed_csv_text": proposed_csv_text or "",
        "current_network_text": current_network_text or "{}",
        "proposed_network_text": proposed_network_text or "{}",
        "files_changed": bool(files_changed),
        "csv_changed": bool(csv_changed),
        "network_changed": bool(network_changed),
        "policy_decision": policy_decision or {},
        "rust_sync_plan": rust_sync_plan or {},
        "rust_authority_gate": rust_authority_gate or {},
        "execute": do_execute,
        "allow_file_writes": bool(rc.get("allow_rust_file_writes", False)),
        "allow_libreqos_apply": bool(rc.get("allow_rust_libreqos_apply", False)),
    }
    response = call_rust_core("execute-apply-transaction", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_execute_apply_transaction(payload)
    return response

def rust_sync_plan_authority_gate(config: dict, rust_sync_plan: dict | None, *, mode: str = "apply") -> dict[str, Any]:
    """Return the opt-in Rust authority gate decision for an apply cycle.

    v0.8 keeps Python authoritative by default. When rust_core.enforce_sync_plan
    or rust_core.authority_mode=enforce_blockers is enabled, non-dry-run cycles
    fail closed if the Rust sync plan is unavailable or reports blockers.
    """
    rc = rust_core_config(config)
    enforced = bool(rc.get("enforce_sync_plan"))
    dry_run = str(mode or "").lower() == "dry_run"
    response = rust_sync_plan or {}
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    available = bool(response.get("available", True)) and not bool(response.get("skipped", False))
    verdict = str(result.get("verdict") or "unknown")
    blockers = result.get("blockers") if isinstance(result.get("blockers"), list) else []
    fail_closed = bool(rc.get("fail_closed_when_enforced", True))
    should_block = False
    reason = "shadow_only"

    if dry_run:
        reason = "dry_run_preview_only"
    elif enforced and not available and fail_closed:
        should_block = True
        reason = "rust_sync_plan_unavailable_fail_closed"
    elif enforced and verdict == "blocked_by_shadow_plan":
        should_block = True
        reason = "rust_sync_plan_blocked"
    elif enforced:
        reason = "rust_sync_plan_allowed"

    return {
        "enabled": enforced,
        "authoritative": bool(enforced and not dry_run),
        "dry_run": dry_run,
        "available": available,
        "fail_closed_when_enforced": fail_closed,
        "authority_mode": rc.get("authority_mode", "shadow"),
        "verdict": verdict,
        "blocker_count": len(blockers),
        "should_block": should_block,
        "reason": reason,
        "message": (
            "Rust sync-plan authority gate blocked this non-dry-run cycle." if should_block else
            "Rust sync-plan authority gate is in preview/shadow or allowed this cycle."
        ),
    }


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rust_core_config(config: dict | None = None) -> dict:
    cfg = (config or {}).get("rust_core", {}) if isinstance(config, dict) else {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "binary_path": str(cfg.get("binary_path") or os.getenv("LQOSYNC_CORE_BIN") or "").strip(),
        "timeout_seconds": int(cfg.get("timeout_seconds", os.getenv("LQOSYNC_CORE_TIMEOUT", 10)) or 10),
        "enforce_validation": bool(cfg.get("enforce_validation", False)),
        "enforce_sync_plan": bool(cfg.get("enforce_sync_plan", False) or cfg.get("authority_mode") == "enforce_blockers"),
        "fail_closed_when_enforced": bool(cfg.get("fail_closed_when_enforced", True)),
        "authority_mode": str(cfg.get("authority_mode") or ("enforce_blockers" if cfg.get("enforce_sync_plan") else "shadow")),
        "prefer_daemon": bool(cfg.get("prefer_daemon", False)),
        "unix_socket": str(cfg.get("unix_socket") or os.getenv("LQOSYNC_CORE_SOCKET") or DEFAULT_SOCKET),
        "transaction_authority": str(cfg.get("transaction_authority") or "preview"),
        "execute_apply_manifest": bool(cfg.get("execute_apply_manifest", False)),
        "allow_rust_file_writes": bool(cfg.get("allow_rust_file_writes", False)),
        "allow_rust_libreqos_apply": bool(cfg.get("allow_rust_libreqos_apply", False)),
    }


def find_rust_core_binary(config: dict | None = None) -> str | None:
    rc = rust_core_config(config)
    if not rc["enabled"]:
        return None
    candidates = []
    if rc["binary_path"]:
        candidates.append(Path(rc["binary_path"]))
    candidates.extend([
        _project_root() / "rust" / "lqosync-core" / "target" / "release" / "lqosync-core",
        _project_root() / "rust" / "lqosync-core" / "target" / "debug" / "lqosync-core",
    ])
    which = shutil.which("lqosync-core")
    if which:
        candidates.append(Path(which))
    candidates.append(Path("/usr/local/bin/lqosync-core"))

    for candidate in candidates:
        try:
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)
        except Exception:
            continue
    return None



def daemon_socket_available(config: dict | None = None) -> bool:
    rc = rust_core_config(config)
    try:
        return rc["enabled"] and Path(rc["unix_socket"]).exists()
    except Exception:
        return False


def call_rust_core_daemon(op: str, payload: dict[str, Any] | None = None, *, config: dict | None = None, request_id: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    """Call lqosync-core over the Unix socket daemon.

    The daemon uses the exact same request/response envelope as the CLI. If the
    socket is unavailable or the daemon response is malformed, the caller can
    safely fall back to subprocess or Python fallback.
    """
    started = time.perf_counter()
    rc = rust_core_config(config)
    socket_path = rc["unix_socket"]
    request_payload = {
        "version": PROTOCOL_VERSION,
        "op": op,
        "request_id": request_id,
        "payload": payload or {},
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout or rc["timeout_seconds"])
            sock.connect(socket_path)
            sock.sendall(json.dumps(request_payload, ensure_ascii=False).encode("utf-8"))
            try:
                sock.shutdown(socket.SHUT_WR)
            except Exception:
                pass
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except Exception as exc:
        return _wrapper_error(op, request_id, "rust_core_daemon_failed", str(exc), started, available=False, mode="daemon")
    try:
        response = json.loads(b"".join(chunks).decode("utf-8") or "{}")
    except Exception as exc:
        return _wrapper_error(op, request_id, "rust_core_daemon_invalid_response", str(exc), started, available=False, mode="daemon")
    response.setdefault("available", True)
    response.setdefault("meta", {})
    response["meta"].setdefault("wrapper_duration_ms", round((time.perf_counter() - started) * 1000, 3))
    response["meta"].setdefault("transport", "unix_socket")
    response["meta"].setdefault("socket", socket_path)
    return response


def rust_core_status(config: dict | None = None) -> dict[str, Any]:
    rc = rust_core_config(config)
    binary = find_rust_core_binary(config)
    daemon_available = daemon_socket_available(config)
    status = {
        "enabled": rc["enabled"],
        "available": bool(binary or daemon_available),
        "binary": binary,
        "daemon_available": bool(daemon_available),
        "timeout_seconds": rc["timeout_seconds"],
        "enforce_validation": rc["enforce_validation"],
        "enforce_sync_plan": rc["enforce_sync_plan"],
        "fail_closed_when_enforced": rc["fail_closed_when_enforced"],
        "authority_mode": rc["authority_mode"],
        "prefer_daemon": rc["prefer_daemon"],
        "unix_socket": rc["unix_socket"],
        "mode": "daemon" if rc["prefer_daemon"] and daemon_available else ("subprocess" if binary else "python_fallback"),
        "self_test_on_status": bool(rc.get("self_test_on_status", False)),
    }
    if rc.get("self_test_on_status"):
        status["self_test"] = rust_core_self_test(config)
    return status


def call_rust_core(op: str, payload: dict[str, Any] | None = None, *, config: dict | None = None, request_id: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    """Call the Rust core through the stable JSON envelope.

    The same envelope is intended for the future Unix socket daemon. v0.1 uses
    subprocess because it is easy to deploy and debug.
    """
    started = time.perf_counter()
    rc = rust_core_config(config)
    if rc.get("prefer_daemon") and daemon_socket_available(config):
        daemon_response = call_rust_core_daemon(op, payload, config=config, request_id=request_id, timeout=timeout)
        # Fallback to subprocess only when the daemon transport itself fails.
        # A valid daemon response with ok=false is an operation result, not a transport failure.
        if daemon_response.get("errors") and any((e.get("code") or "").startswith("rust_core_daemon_") for e in daemon_response.get("errors", [])):
            pass
        else:
            return daemon_response
    binary = find_rust_core_binary(config)
    if not binary:
        return {
            "version": PROTOCOL_VERSION,
            "op": op,
            "request_id": request_id,
            "available": False,
            "ok": True,
            "skipped": True,
            "result": {},
            "errors": [],
            "warnings": [{
                "code": "rust_core_unavailable",
                "severity": "info",
                "message": "Rust core daemon/binary is not available; Python validator fallback is active.",
            }],
            "meta": {
                "engine": "python-wrapper",
                "mode": "python_fallback",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        }

    request_payload = {
        "version": PROTOCOL_VERSION,
        "op": op,
        "request_id": request_id,
        "payload": payload or {},
    }
    try:
        proc = subprocess.run(
            [binary],
            input=json.dumps(request_payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout or rc["timeout_seconds"],
        )
    except subprocess.TimeoutExpired:
        return _wrapper_error(op, request_id, "rust_core_timeout", f"Rust core timed out after {timeout or rc['timeout_seconds']} seconds", started, available=True)
    except Exception as exc:
        return _wrapper_error(op, request_id, "rust_core_call_failed", str(exc), started, available=True)

    try:
        response = json.loads(proc.stdout or "{}")
    except Exception as exc:
        return _wrapper_error(
            op,
            request_id,
            "rust_core_invalid_response",
            f"Rust core returned invalid JSON: {exc}; stderr={proc.stderr[:500]}",
            started,
            available=True,
        )

    response.setdefault("available", True)
    response.setdefault("meta", {})
    response["meta"].setdefault("wrapper_duration_ms", round((time.perf_counter() - started) * 1000, 3))
    response["meta"].setdefault("exit_code", proc.returncode)
    if proc.stderr:
        response["meta"].setdefault("stderr", proc.stderr[:1000])
    return response


def validate_json_state(config: dict | None, *, state: dict[str, Any], state_type: str) -> dict[str, Any]:
    return call_rust_core("validate-json-state", {"state": state or {}, "state_type": state_type}, config=config)


def rust_write_json_state(config: dict | None, *, path: str, state: dict[str, Any], state_type: str, create_backup: bool = False) -> dict[str, Any]:
    return call_rust_core("write-json-state", {"path": path, "state": state or {}, "state_type": state_type, "create_backup": create_backup}, config=config)


def rust_append_audit_jsonl(config: dict | None, *, path: str, event: dict[str, Any]) -> dict[str, Any]:
    return call_rust_core("append-audit-jsonl", {"path": path, "event": event or {}}, config=config)


def validate_runtime_outputs(config: dict, *, csv_text: str | None = None, network_text: str | None = None, csv_path: str | None = None, network_path: str | None = None) -> dict[str, Any]:
    paths = (config or {}).get("paths", {})
    payload = {
        "config": config or {},
        "csv_text": csv_text,
        "network_text": network_text,
        "shaped_devices_csv_path": csv_path or paths.get("shaped_devices_csv"),
        "network_json_path": network_path or paths.get("network_json"),
    }
    # Avoid sending null text values because the Rust side treats present text as
    # authoritative. If text is None, let the path fallback be used.
    payload = {k: v for k, v in payload.items() if v is not None}
    return call_rust_core("validate-files", payload, config=config)


def validate_collector_output(config: dict, envelope: dict[str, Any]) -> dict[str, Any]:
    response = call_rust_core("validate-collector-output", envelope, config=config)
    # If the Rust core is not built yet, still enforce the collector trust
    # contract locally. This closes the silent-empty-list cleanup risk even in
    # fallback mode.
    if response.get("skipped") or not response.get("available"):
        return _python_collector_contract(envelope)
    return response


def diagnostics_to_messages(response: dict[str, Any], *, include_warnings: bool = True) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    for item in response.get("errors") or []:
        msg = item.get("message") or item.get("code") or "Rust core error"
        errors.append(f"Rust core: {msg}")
    if include_warnings:
        for item in response.get("warnings") or []:
            msg = item.get("message") or item.get("code") or "Rust core warning"
            severity = item.get("severity", "warning")
            if severity == "info":
                warnings.append(f"Rust core: {msg}")
            else:
                warnings.append(f"Rust core: {msg}")
    return errors, warnings


def _wrapper_error(op: str, request_id: str | None, code: str, message: str, started: float, *, available: bool, mode: str = "subprocess") -> dict[str, Any]:
    return {
        "version": PROTOCOL_VERSION,
        "op": op,
        "request_id": request_id,
        "available": available,
        "ok": False,
        "result": {},
        "errors": [{"code": code, "severity": "error", "message": message}],
        "warnings": [],
        "meta": {
            "engine": "python-wrapper",
            "mode": mode,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }


def rust_core_self_test(config: dict | None = None, *, strict: bool = False) -> dict[str, Any]:
    """Run the Rust core runtime self-test without mutating files."""
    response = call_rust_core("self-test", {"strict": bool(strict)}, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return {
            "version": PROTOCOL_VERSION,
            "op": "self-test",
            "available": False,
            "ok": False,
            "skipped": bool(response.get("skipped", False)),
            "result": {
                "status": "unavailable",
                "checks": [],
                "operation_count": 0,
                "purpose": "Rust core runtime self-test unavailable; install or upgrade lqosync-core.",
            },
            "errors": response.get("errors") or [{"code": "rust_core_self_test_unavailable", "severity": "error", "message": "Rust core self-test is unavailable."}],
            "warnings": response.get("warnings") or [],
            "meta": response.get("meta") or {"engine": "python-wrapper"},
        }
    return response
