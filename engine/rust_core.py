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


def _python_transaction_journal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust build-transaction-journal.

    This fallback is non-mutating. It builds the same high-level event shape so
    Dry Run and reports stay stable if an older Rust core is installed.
    """
    started = started or time.perf_counter()
    manifest_resp = payload.get("rust_apply_manifest") if isinstance(payload.get("rust_apply_manifest"), dict) else {}
    tx_resp = payload.get("rust_apply_transaction") if isinstance(payload.get("rust_apply_transaction"), dict) else {}
    manifest = manifest_resp.get("result") if isinstance(manifest_resp.get("result"), dict) else manifest_resp
    tx = tx_resp.get("result") if isinstance(tx_resp.get("result"), dict) else tx_resp
    paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else (payload.get("config", {}).get("paths", {}) if isinstance(payload.get("config"), dict) else {})
    basis = json.dumps({"manifest": manifest.get("manifest_id"), "tx": tx.get("status"), "executed": tx.get("executed")}, sort_keys=True)
    journal_id = "txj-" + hashlib.sha256(basis.encode()).hexdigest()[:16]
    event = {
        "schema_version": "1",
        "event": "rust_apply_transaction_journal",
        "journal_id": journal_id,
        "mode": payload.get("mode", "apply"),
        "manifest_id": manifest.get("manifest_id", "unknown"),
        "manifest_status": manifest.get("status"),
        "transaction_status": tx.get("status", "not_run"),
        "executed": bool(tx.get("executed", False)),
        "write_count": int(tx.get("write_count", 0) or 0),
        "operation_count": int(manifest.get("operation_count", 0) or 0),
        "rollback_available": any(bool(item.get("backup_path")) for item in (tx.get("write_results") or []) if isinstance(item, dict)),
    }
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-transaction-journal",
        "available": False,
        "ok": True,
        "result": {
            "mode": "transaction_journal_preview",
            "authoritative": False,
            "journal_id": journal_id,
            "journal_path": paths.get("transaction_journal", "/opt/lqosync/logs/transaction_journal.jsonl"),
            "append_required": bool(event["executed"]),
            "append_executed": False,
            "rollback_available": bool(event["rollback_available"]),
            "manifest_id": event["manifest_id"],
            "transaction_status": event["transaction_status"],
            "executed": event["executed"],
            "write_count": event["write_count"],
            "operation_count": event["operation_count"],
            "event": event,
        },
        "errors": [],
        "warnings": [{"code": "rust_transaction_journal_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust build-transaction-journal is unavailable; Python fallback generated a preview only."}],
        "meta": {"engine": "python-wrapper", "mode": "python_transaction_journal_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }



def _python_append_transaction_journal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust append-transaction-journal.

    The fallback is intentionally non-mutating. Journal persistence is a Rust
    authority surface, so if Rust is unavailable Python reports rehearsal only.
    """
    started = started or time.perf_counter()
    preview = _python_transaction_journal(payload, started=started).get("result", {})
    return {
        "version": PROTOCOL_VERSION,
        "op": "append-transaction-journal",
        "available": False,
        "ok": True,
        "result": {
            "mode": "transaction_journal_writer",
            "authoritative": False,
            "status": "rust_unavailable_rehearsal_only",
            "journal_id": preview.get("journal_id"),
            "journal_path": preview.get("journal_path"),
            "append_requested": bool(payload.get("append")),
            "append_required": bool(preview.get("append_required")),
            "allow_journal_write": bool(payload.get("allow_journal_write")),
            "include_rehearsal_entries": bool(payload.get("include_rehearsal_entries")),
            "allow_dry_run_journal": bool(payload.get("allow_dry_run_journal")),
            "append_executed": False,
            "append_result": {},
            "journal_preview": preview,
        },
        "errors": [],
        "warnings": [{"code": "rust_transaction_journal_append_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust append-transaction-journal is unavailable; Python fallback did not write the journal."}],
        "meta": {"engine": "python-wrapper", "mode": "python_transaction_journal_append_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_transaction_journal(config: dict, *, mode: str, paths: dict, rust_apply_manifest: dict | None = None, rust_apply_transaction: dict | None = None, rust_sync_plan: dict | None = None, rust_authority_gate: dict | None = None, policy_decision: dict | None = None) -> dict[str, Any]:
    payload = {
        "config": config or {},
        "mode": mode,
        "paths": paths or {},
        "rust_apply_manifest": rust_apply_manifest or {},
        "rust_apply_transaction": rust_apply_transaction or {},
        "rust_sync_plan": rust_sync_plan or {},
        "rust_authority_gate": rust_authority_gate or {},
        "policy_decision": policy_decision or {},
    }
    response = call_rust_core("build-transaction-journal", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_transaction_journal(payload)
    return response



def rust_append_transaction_journal(config: dict, *, mode: str, paths: dict, rust_apply_manifest: dict | None = None, rust_apply_transaction: dict | None = None, rust_sync_plan: dict | None = None, rust_authority_gate: dict | None = None, policy_decision: dict | None = None, rust_transaction_journal: dict | None = None) -> dict[str, Any]:
    rc = rust_core_config(config)
    payload = {
        "config": config or {},
        "mode": mode,
        "paths": paths or {},
        "rust_apply_manifest": rust_apply_manifest or {},
        "rust_apply_transaction": rust_apply_transaction or {},
        "rust_sync_plan": rust_sync_plan or {},
        "rust_authority_gate": rust_authority_gate or {},
        "policy_decision": policy_decision or {},
        "rust_transaction_journal": rust_transaction_journal or {},
        "append": bool(rc.get("append_transaction_journal", False)),
        "allow_journal_write": bool(rc.get("allow_transaction_journal_writes", False)),
        "include_rehearsal_entries": bool(rc.get("include_rehearsal_journal_entries", False)),
        "allow_dry_run_journal": bool(rc.get("allow_dry_run_journal_entries", False)),
    }
    response = call_rust_core("append-transaction-journal", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_append_transaction_journal(payload)
    return response


def _python_rollback_manifest(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    tx_resp = payload.get("rust_apply_transaction") if isinstance(payload.get("rust_apply_transaction"), dict) else {}
    manifest_resp = payload.get("rust_apply_manifest") if isinstance(payload.get("rust_apply_manifest"), dict) else {}
    tx = tx_resp.get("result") if isinstance(tx_resp.get("result"), dict) else tx_resp
    manifest = manifest_resp.get("result") if isinstance(manifest_resp.get("result"), dict) else manifest_resp
    ops = []
    for item in (tx.get("write_results") or []):
        if isinstance(item, dict) and item.get("path") and item.get("backup_path"):
            ops.append({
                "op": "restore_file",
                "phase": "rollback",
                "target_path": item.get("path"),
                "backup_path": item.get("backup_path"),
                "expected_current_sha256": item.get("after_sha256"),
                "restore_sha256": item.get("before_sha256"),
                "file_kind": item.get("file_kind"),
                "allowed_now": False,
            })
    status = "rollback_available" if ops else ("no_restore_points" if tx.get("executed") else "not_executed")
    basis = json.dumps({"manifest": manifest.get("manifest_id"), "tx": tx.get("status"), "ops": ops}, sort_keys=True)
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-rollback-manifest",
        "available": False,
        "ok": True,
        "result": {
            "mode": "rollback_manifest_preview",
            "authoritative": False,
            "rollback_id": "rollback-" + hashlib.sha256(basis.encode()).hexdigest()[:16],
            "status": status,
            "manifest_id": manifest.get("manifest_id"),
            "transaction_status": tx.get("status"),
            "executed": bool(tx.get("executed", False)),
            "rollback_available": bool(ops),
            "operation_count": len(ops),
            "operations": ops,
            "requires_operator_confirmation": True,
            "execute_supported": False,
        },
        "errors": [],
        "warnings": [{"code": "rust_rollback_manifest_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust build-rollback-manifest is unavailable; Python fallback generated a preview only."}],
        "meta": {"engine": "python-wrapper", "mode": "python_rollback_manifest_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rollback_manifest(config: dict, *, rust_apply_manifest: dict | None = None, rust_apply_transaction: dict | None = None, rust_transaction_journal: dict | None = None) -> dict[str, Any]:
    payload = {
        "config": config or {},
        "rust_apply_manifest": rust_apply_manifest or {},
        "rust_apply_transaction": rust_apply_transaction or {},
        "rust_transaction_journal": rust_transaction_journal or {},
    }
    response = call_rust_core("build-rollback-manifest", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_rollback_manifest(payload)
    return response


def _python_read_transaction_journal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    path = str(payload.get("path") or payload.get("journal_path") or "/opt/lqosync/logs/transaction_journal.jsonl")
    limit = min(int(payload.get("limit") or 50), 500)
    offset = max(int(payload.get("offset") or 0), 0)
    reverse = bool(payload.get("reverse", True))
    include_event = bool(payload.get("include_event", True))
    filters = {
        "journal_id": str(payload.get("journal_id") or ""),
        "manifest_id": str(payload.get("manifest_id") or ""),
        "transaction_status": str(payload.get("transaction_status") or ""),
        "sync_plan_verdict": str(payload.get("sync_plan_verdict") or ""),
        "executed": payload.get("executed"),
    }
    target = Path(path)
    entries = []
    invalid = 0
    warnings = []
    if target.exists():
        for line_number, line in enumerate(target.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception as exc:
                invalid += 1
                warnings.append({"code": "transaction_journal_invalid_jsonl", "severity": "warning", "path": f"line[{line_number}]", "message": f"Invalid transaction journal JSONL line: {exc}"})
                continue
            if not isinstance(event, dict):
                invalid += 1
                continue
            def _match(key):
                return not filters[key] or str(event.get(key) or "") == filters[key]
            if not (_match("journal_id") and _match("manifest_id") and _match("transaction_status") and _match("sync_plan_verdict")):
                continue
            if filters["executed"] is not None:
                expected = str(filters["executed"]).lower() in {"1", "true", "yes", "on"}
                if bool(event.get("executed")) != expected:
                    continue
            item = {
                "line_number": line_number,
                "journal_id": event.get("journal_id"),
                "generated_at_unix": event.get("generated_at_unix"),
                "event": event.get("event"),
                "mode": event.get("mode"),
                "manifest_id": event.get("manifest_id"),
                "manifest_status": event.get("manifest_status"),
                "transaction_status": event.get("transaction_status"),
                "executed": bool(event.get("executed", False)),
                "write_count": int(event.get("write_count") or 0),
                "operation_count": int(event.get("operation_count") or 0),
                "rollback_available": bool(event.get("rollback_available", False)),
                "policy_verdict": event.get("policy_verdict"),
                "sync_plan_verdict": event.get("sync_plan_verdict"),
                "authority_reason": (event.get("authority_gate") or {}).get("reason") if isinstance(event.get("authority_gate"), dict) else None,
            }
            if include_event:
                item["raw_event"] = event
            entries.append(item)
    if reverse:
        entries = list(reversed(entries))
    returned = entries[offset:offset + limit]
    return {
        "version": PROTOCOL_VERSION,
        "op": "read-transaction-journal",
        "available": False,
        "ok": True,
        "result": {
            "mode": "transaction_journal_reader",
            "authoritative": False,
            "read_only": True,
            "status": "ok" if target.exists() else "missing",
            "path": path,
            "limit": limit,
            "offset": offset,
            "reverse": reverse,
            "include_event": include_event,
            "filters": filters,
            "total_line_count": len(entries) + invalid,
            "parsed_count": len(entries),
            "invalid_line_count": invalid,
            "matched_count": len(entries),
            "returned_count": len(returned),
            "entries": returned,
        },
        "errors": [],
        "warnings": warnings + [{"code": "rust_transaction_journal_reader_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust read-transaction-journal is unavailable; Python fallback read the JSONL file."}],
        "meta": {"engine": "python-wrapper", "mode": "python_transaction_journal_reader_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_read_transaction_journal(config: dict, *, limit: int = 50, offset: int = 0, journal_id: str = "", manifest_id: str = "", transaction_status: str = "", executed: bool | None = None, include_event: bool = True, reverse: bool = True) -> dict[str, Any]:
    paths = (config or {}).get("paths", {}) if isinstance(config, dict) else {}
    payload: dict[str, Any] = {
        "path": paths.get("transaction_journal") or "/opt/lqosync/logs/transaction_journal.jsonl",
        "limit": int(limit or 50),
        "offset": int(offset or 0),
        "journal_id": journal_id or "",
        "manifest_id": manifest_id or "",
        "transaction_status": transaction_status or "",
        "include_event": bool(include_event),
        "reverse": bool(reverse),
    }
    if executed is not None:
        payload["executed"] = bool(executed)
    response = call_rust_core("read-transaction-journal", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_read_transaction_journal(payload)
    return response


def _python_rollback_from_journal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    read_resp = _python_read_transaction_journal({**payload, "limit": 1, "include_event": True}, started=started)
    entries = (((read_resp.get("result") or {}).get("entries")) or [])
    if not entries:
        return {
            "version": PROTOCOL_VERSION,
            "op": "build-rollback-from-journal",
            "available": False,
            "ok": False,
            "result": {"mode": "rollback_from_journal", "status": "not_found", "path": payload.get("path")},
            "errors": [{"code": "transaction_journal_entry_not_found", "severity": "error", "path": "journal_id", "message": "No transaction journal entry matched the selector."}],
            "warnings": read_resp.get("warnings", []),
            "meta": {"engine": "python-wrapper", "mode": "python_rollback_from_journal_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
        }
    event = entries[0].get("raw_event") or {}
    return _python_rollback_manifest({"rust_apply_manifest": event.get("manifest") or {}, "rust_apply_transaction": event.get("transaction") or {}}, started=started)


def rust_build_rollback_from_journal(config: dict, *, journal_id: str = "", manifest_id: str = "") -> dict[str, Any]:
    paths = (config or {}).get("paths", {}) if isinstance(config, dict) else {}
    payload = {
        "path": paths.get("transaction_journal") or "/opt/lqosync/logs/transaction_journal.jsonl",
        "journal_id": journal_id or "",
        "manifest_id": manifest_id or "",
    }
    response = call_rust_core("build-rollback-from-journal", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_rollback_from_journal(payload)
    return response


def _python_execute_rollback(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for Rust execute-rollback.

    The Python fallback never restores files. It exists only to keep the API
    shape stable when the Rust core is unavailable.
    """
    started = started or time.perf_counter()
    rollback_manifest = payload.get("rollback_manifest") if isinstance(payload.get("rollback_manifest"), dict) else {}
    if not rollback_manifest and (payload.get("journal_id") or payload.get("manifest_id")):
        rollback_manifest = (rust_build_rollback_from_journal(payload.get("config") or {}, journal_id=str(payload.get("journal_id") or ""), manifest_id=str(payload.get("manifest_id") or "")).get("result") or {})
    return {
        "version": PROTOCOL_VERSION,
        "op": "execute-rollback",
        "available": False,
        "ok": True,
        "result": {
            "mode": "rollback_executor",
            "authoritative": False,
            "executed": False,
            "status": "python_fallback_rehearsal_only",
            "rollback_manifest": rollback_manifest,
            "restore_results": [],
            "restore_count": 0,
            "execute_requested": bool(payload.get("execute", False)),
            "allow_rollback_file_writes": False,
            "confirmation_required": True,
            "confirmation_ok": str(payload.get("confirmation") or "") == "CONFIRM_ROLLBACK",
            "trace": [{"step": "rollback_execute", "decision": "python_fallback_never_restores_files"}],
        },
        "errors": [],
        "warnings": [{"code": "rust_rollback_executor_unavailable", "severity": "warning", "path": "rust_core", "message": "Rust execute-rollback is unavailable; Python fallback rehearsed only and did not restore files."}],
        "meta": {"engine": "python-wrapper", "mode": "python_rollback_executor_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_execute_rollback(config: dict, *, journal_id: str = "", manifest_id: str = "", rollback_manifest: dict | None = None, execute: bool | None = None, confirmation: str = "", allow_checksum_mismatch: bool = False) -> dict[str, Any]:
    rc = rust_core_config(config)
    paths = (config or {}).get("paths", {}) if isinstance(config, dict) else {}
    payload: dict[str, Any] = {
        "config": config or {},
        "path": paths.get("transaction_journal") or "/opt/lqosync/logs/transaction_journal.jsonl",
        "journal_id": journal_id or "",
        "manifest_id": manifest_id or "",
        "rollback_manifest": rollback_manifest or {},
        "execute": bool(rc.get("execute_rollback", False) if execute is None else execute),
        "allow_rollback_file_writes": bool(rc.get("allow_rust_rollback_file_writes", False)),
        "confirmation": confirmation or "",
        "allow_checksum_mismatch": bool(allow_checksum_mismatch),
    }
    if str(rc.get("rollback_authority") or "preview") != "execute_file_restores":
        payload["execute"] = False
    response = call_rust_core("execute-rollback", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_execute_rollback(payload)
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
        "append_transaction_journal": bool(cfg.get("append_transaction_journal", False)),
        "allow_transaction_journal_writes": bool(cfg.get("allow_transaction_journal_writes", False)),
        "include_rehearsal_journal_entries": bool(cfg.get("include_rehearsal_journal_entries", False)),
        "allow_dry_run_journal_entries": bool(cfg.get("allow_dry_run_journal_entries", False)),
        "execute_rollback": bool(cfg.get("execute_rollback", False)),
        "allow_rust_rollback_file_writes": bool(cfg.get("allow_rust_rollback_file_writes", False)),
        "rollback_authority": str(cfg.get("rollback_authority") or "preview"),
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


def _python_authority_readiness(config: dict, *, status: dict | None = None, self_test: dict | None = None, journal_summary: dict | None = None, started: float | None = None) -> dict[str, Any]:
    """Python fallback for Rust authority readiness scoring."""
    started = started or time.perf_counter()
    cfg = config or {}
    rc = cfg.get("rust_core", {}) if isinstance(cfg, dict) else {}
    paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
    status = status or {"available": False, "ok": False}
    self_test = self_test or {"ok": False, "result": {"status": "unavailable"}}
    checks = []
    errors = []
    warnings = []
    blockers = []
    risk_score = 0

    def check(name, ok, severity="info", details=None):
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "details": details or {}})

    enabled = bool(rc.get("enabled", True))
    transport_ok = bool(status.get("available", False) and status.get("ok", False))
    self_ok = bool(self_test.get("ok") and (self_test.get("result") or {}).get("status") == "ok")
    check("rust_core_enabled", enabled, "required", {"enabled": enabled})
    check("transport_available", transport_ok, "required", {"available": status.get("available"), "ok": status.get("ok")})
    check("self_test_ok", self_ok, "required", {"ok": self_test.get("ok"), "status": (self_test.get("result") or {}).get("status")})
    paths_ok = bool(paths.get("shaped_devices_csv") and paths.get("network_json"))
    check("generated_file_paths_present", paths_ok, "required", {"shaped_devices_csv": paths.get("shaped_devices_csv"), "network_json": paths.get("network_json")})
    for name, ok in (("rust_core_enabled", enabled), ("transport_available", transport_ok), ("self_test_ok", self_ok), ("generated_file_paths_present", paths_ok)):
        if not ok:
            blockers.append({"code": name, "message": f"{name} is not ready"})
            errors.append({"code": name, "severity": "error", "path": "rust_core", "message": f"{name} is not ready"})
            risk_score += 30
    authority_flags = any(bool(rc.get(k)) for k in ("enforce_sync_plan", "execute_apply_manifest", "allow_rust_file_writes", "append_transaction_journal", "allow_transaction_journal_writes", "execute_rollback", "allow_rust_rollback_file_writes")) or rc.get("authority_mode") == "enforce_blockers" or rc.get("rollback_authority") == "execute_file_restores"
    if rc.get("allow_rust_libreqos_apply"):
        warnings.append({"code": "rust_libreqos_apply_not_implemented", "severity": "warning", "path": "rust_core.allow_rust_libreqos_apply", "message": "Rust does not invoke LibreQoS.py in this release."})
        risk_score += 15
    if rc.get("execute_apply_manifest") != rc.get("allow_rust_file_writes") and (rc.get("execute_apply_manifest") or rc.get("allow_rust_file_writes")):
        blockers.append({"code": "partial_file_write_authority", "message": "execute_apply_manifest and allow_rust_file_writes must be enabled together for a file-write pilot."})
        errors.append({"code": "partial_file_write_authority", "severity": "error", "path": "rust_core", "message": "Rust file-write authority flags are partial."})
        risk_score += 35
    if rc.get("append_transaction_journal") != rc.get("allow_transaction_journal_writes") and (rc.get("append_transaction_journal") or rc.get("allow_transaction_journal_writes")):
        blockers.append({"code": "partial_journal_authority", "message": "append_transaction_journal and allow_transaction_journal_writes must be enabled together."})
        errors.append({"code": "partial_journal_authority", "severity": "error", "path": "rust_core", "message": "Journal authority flags are partial."})
        risk_score += 25
    if rc.get("execute_rollback") != rc.get("allow_rust_rollback_file_writes") and (rc.get("execute_rollback") or rc.get("allow_rust_rollback_file_writes")):
        blockers.append({"code": "partial_rollback_authority", "message": "execute_rollback and allow_rust_rollback_file_writes must be enabled together."})
        errors.append({"code": "partial_rollback_authority", "severity": "error", "path": "rust_core", "message": "Rollback authority flags are partial."})
        risk_score += 40
    verdict = "not_ready" if blockers else ("shadow_safe" if not authority_flags else "ready_with_warnings")
    risk_score = min(100, risk_score + len([c for c in checks if not c.get("ok")]) * 6)
    risk_level = _risk_level(risk_score)
    return {
        "version": PROTOCOL_VERSION,
        "op": "evaluate-authority-readiness",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "authority_readiness",
            "authoritative": False,
            "verdict": verdict,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "ready": not blockers,
            "authority_flags_enabled": authority_flags,
            "check_count": len(checks),
            "failed_check_count": len([c for c in checks if not c.get("ok")]),
            "checks": checks,
            "blockers": blockers,
            "recommendations": [{"title": "Review Rust authority flags", "action": "Use Rust self-test and Dry Run before enabling authority flags.", "severity": "info"}],
            "journal_summary": journal_summary or {},
            "transport": {"available": status.get("available"), "ok": status.get("ok")},
            "self_test": {"ok": self_test.get("ok"), "status": (self_test.get("result") or {}).get("status")},
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_authority_readiness_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_authority_readiness(config: dict) -> dict[str, Any]:
    """Evaluate readiness before enabling Rust authority flags."""
    started = time.perf_counter()
    status = rust_core_status(config)
    self_test = rust_core_self_test(config, strict=False) if status.get("available") else {"ok": False, "result": {"status": "unavailable"}}
    journal = rust_read_transaction_journal(config, limit=1, include_event=False) if status.get("available") else {"ok": False, "result": {"total_count": 0}}
    journal_result = journal.get("result") if isinstance(journal.get("result"), dict) else {}
    payload = {
        "config": config or {},
        "rust_core_status": status,
        "self_test": self_test,
        "journal_summary": {"total_count": journal_result.get("total_count", journal_result.get("returned_count", 0)), "returned_count": journal_result.get("returned_count", 0)},
    }
    response = call_rust_core("evaluate-authority-readiness", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_authority_readiness(config or {}, status=status, self_test=self_test, journal_summary=payload["journal_summary"], started=started)
    return response


def _python_full_rust_readiness(config: dict, *, status: dict | None = None, self_test: dict | None = None, authority_readiness: dict | None = None, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = (config or {}).get("rust_core", {}) if isinstance(config, dict) else {}
    status = status or {}
    self_test = self_test or {}
    operations = (((self_test.get("result") or {}).get("operations")) or []) if isinstance(self_test, dict) else []
    implemented = [
        {"component": "rust_protocol_daemon", "status": "ready" if status.get("available", True) else "not_ready", "rust_owned": True},
        {"component": "validation_diff_core", "status": "ready", "rust_owned": True},
        {"component": "collector_trust_contract", "status": "ready", "rust_owned": True, "note": "Rust validates collector output, but Python still collects RouterOS data."},
        {"component": "policy_engine", "status": "shadow", "rust_owned": "partial"},
        {"component": "circuit_normalizer", "status": "shadow", "rust_owned": "partial"},
        {"component": "sync_plan_apply_transaction_journal_rollback", "status": "gated_ready", "rust_owned": True},
    ]
    remaining = [
        {"component": "webui_auth_routes_templates", "owner": "python", "reason": "Flask/Jinja UI remains the operator surface."},
        {"component": "scheduler_runner", "owner": "python", "reason": "Python scheduler still starts sync jobs."},
        {"component": "run_cycle_orchestration", "owner": "python", "reason": "Python run_cycle remains authoritative by default."},
        {"component": "routeros_api_collectors", "owner": "python", "reason": "RouterOS PPPoE/DHCP/Hotspot collectors still use Python routeros-api."},
        {"component": "libreqos_external_apply", "owner": "python", "reason": "Rust does not invoke LibreQoS.py in this release."},
    ]
    authority_flags = any(bool(rc.get(k)) for k in ("enforce_sync_plan", "execute_apply_manifest", "allow_rust_file_writes", "append_transaction_journal", "allow_transaction_journal_writes", "execute_rollback", "allow_rust_rollback_file_writes"))
    return {
        "version": PROTOCOL_VERSION,
        "op": "evaluate-full-rust-readiness",
        "available": False,
        "ok": True,
        "result": {
            "mode": "full_rust_readiness",
            "full_backend_ready": False,
            "backend_model": "hybrid_rust_authority_pilot" if authority_flags else "hybrid_python_authoritative_rust_safety_core",
            "maturity": "authority_pilot_active" if authority_flags else "hybrid_shadow_ready",
            "verdict": "not_full_rust_backend_yet",
            "summary": "LQoSync is a hybrid system: Python remains WebUI/orchestrator/collector authority by default while Rust provides safety, planning, transaction, journal, rollback, and optional authority gates.",
            "rust_operations_count": len(operations),
            "implemented_rust_capabilities": implemented,
            "remaining_python_authoritative_components": remaining,
            "authority_readiness_verdict": ((authority_readiness or {}).get("result") or {}).get("verdict", "unknown"),
            "blockers": [],
            "next_steps": [
                {"step": 1, "title": "Pilot sync-plan enforcement", "action": "Enable enforce_sync_plan only after authority readiness is clean."},
                {"step": 2, "title": "Pilot transaction journal persistence", "action": "Enable append_transaction_journal before Rust file writes."},
                {"step": 3, "title": "Move collector normalization", "action": "Migrate PPPoE/DHCP/Hotspot row-building to Rust before replacing RouterOS API transport."},
            ],
        },
        "errors": [],
        "warnings": [{"code": "python_fallback_full_readiness", "severity": "warning", "path": "rust_core", "message": "Rust full-readiness evaluator unavailable; Python returned a conservative hybrid readiness report."}],
        "meta": {"engine": "python-wrapper", "mode": "python_full_rust_readiness_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_full_backend_readiness(config: dict) -> dict[str, Any]:
    started = time.perf_counter()
    status = rust_core_status(config)
    self_test = rust_core_self_test(config, strict=False) if status.get("available") else {"ok": False, "result": {"status": "unavailable", "operations": []}}
    authority = rust_authority_readiness(config)
    payload = {"config": config or {}, "rust_core_status": status, "self_test": self_test, "authority_readiness": authority}
    response = call_rust_core("evaluate-full-rust-readiness", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_full_rust_readiness(config or {}, status=status, self_test=self_test, authority_readiness=authority, started=started)
    return response


def _python_authority_pilot_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    readiness = ((payload.get("authority_readiness") or {}).get("result") or {}).get("verdict", "shadow_safe")
    stages = [
        {"stage": 0, "name": "Shadow baseline", "status": "current_or_complete", "description": "Rust shadows Python authority."},
        {"stage": 1, "name": "Daemon and self-test", "status": "ready" if readiness != "not_ready" else "blocked", "description": "Prefer daemon and verify self-test."},
        {"stage": 2, "name": "Sync-plan enforcement", "status": "available", "config_delta": {"enforce_sync_plan": True, "fail_closed_when_enforced": True, "authority_mode": "enforce_blockers"}},
        {"stage": 3, "name": "Transaction journal persistence", "status": "available", "config_delta": {"append_transaction_journal": True, "allow_transaction_journal_writes": True}},
        {"stage": 4, "name": "Rust file-write pilot", "status": "available_after_journal", "config_delta": {"execute_apply_manifest": True, "allow_rust_file_writes": True}},
        {"stage": 5, "name": "Rollback execution pilot", "status": "available_after_file_write_pilot", "config_delta": {"execute_rollback": True, "allow_rust_rollback_file_writes": True, "rollback_authority": "execute_file_restores"}},
        {"stage": 6, "name": "Collector/circuit migration", "status": "future_work"},
    ]
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-authority-pilot-plan",
        "available": False,
        "ok": readiness != "not_ready",
        "result": {"mode": "authority_pilot_plan", "full_backend_ready": False, "pilot_only": True, "readiness_verdict": readiness, "recommended_next_stage": stages[2], "stages": stages, "guardrails": ["Keep Python authoritative until multiple clean Rust authority pilot cycles pass.", "Enable journal persistence before Rust file writes."]},
        "errors": [] if readiness != "not_ready" else [{"code": "authority_pilot_blocked", "severity": "error", "path": "authority_readiness", "message": "Authority readiness is not clean."}],
        "warnings": [{"code": "python_fallback_authority_pilot_plan", "severity": "warning", "path": "rust_core", "message": "Rust pilot-plan evaluator unavailable; Python returned conservative staged plan."}],
        "meta": {"engine": "python-wrapper", "mode": "python_authority_pilot_plan_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_authority_pilot_plan(config: dict) -> dict[str, Any]:
    started = time.perf_counter()
    authority = rust_authority_readiness(config)
    full = rust_full_backend_readiness(config)
    payload = {"config": config or {}, "authority_readiness": authority, "full_backend_readiness": full}
    response = call_rust_core("build-authority-pilot-plan", payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_authority_pilot_plan(payload, started=started)
    return response




def _python_build_routeros_collector_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    routers = payload.get("routers") if isinstance(payload.get("routers"), list) else cfg.get("routers", [])
    requested_router = str(payload.get("router") or "")
    requested_source = str(payload.get("source") or "").lower()
    include_disabled = bool(payload.get("include_disabled_routers", False))
    commands: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    def add(router_name: str, source: str, path: str, fields: list[str], required: bool, purpose: str, **extra):
        commands.append({
            "router": router_name,
            "source": source,
            "path": path,
            "fields": fields,
            "required": required,
            "purpose": purpose,
            "transport": "routeros-api",
            "mode": "plan_only",
            **extra,
        })
        source_counts[source] = source_counts.get(source, 0) + 1

    routers_seen = len(routers) if isinstance(routers, list) else 0
    routers_planned = 0
    for router in routers if isinstance(routers, list) else []:
        if not isinstance(router, dict):
            continue
        name = str(router.get("name") or "Router")
        if requested_router and requested_router != name:
            continue
        if not bool(router.get("enabled", True)) and not include_disabled:
            continue
        routers_planned += 1
        if router.get("pppoe", {}).get("enabled") and requested_source in {"", "pppoe", "ppp"}:
            add(name, "pppoe", "/ppp/active", ["name", "address", "caller-id", "comment"], True, "Read active PPPoE sessions.", trust_role="active_presence")
            add(name, "pppoe", "/ppp/secret", ["name", "profile", "comment", "caller-id", "disabled", "inactive"], True, "Read PPPoE secrets for profile and disabled/inactive state.", trust_role="identity_profile")
            add(name, "pppoe", "/ppp/profile", ["name", "comment", "rate-limit"], True, "Read PPPoE profiles for rate-limit fallback.", trust_role="speed_profile")
        if router.get("dhcp", {}).get("enabled") and requested_source in {"", "dhcp"}:
            servers = [str(s.get("name")) for s in router.get("dhcp", {}).get("servers", []) if isinstance(s, dict) and s.get("enabled", True) and s.get("name")]
            add(name, "dhcp", "/ip/dhcp-server/lease", ["address", "mac-address", "host-name", "server", "status", "comment", "dynamic", "disabled"], True, "Read DHCP leases for IP/MAC/hostname/server mapping.", trust_role="lease_presence", server_filter=servers)
            if cfg.get("collector", {}).get("dhcp", {}).get("read_server_metadata", True):
                add(name, "dhcp", "/ip/dhcp-server", ["name", "interface", "comment", "disabled", "lease-script"], False, "Read DHCP server metadata for speed/comment context.", trust_role="source_metadata")
        if router.get("hotspot", {}).get("enabled") and requested_source in {"", "hotspot", "hs"}:
            add(name, "hotspot", "/ip/hotspot/active", ["user", "address", "mac-address", "server", "uptime", "comment"], True, "Read active Hotspot sessions.", trust_role="active_presence")
            add(name, "hotspot", "/ip/hotspot/user", ["name", "profile", "comment", "mac-address", "disabled"], False, "Read Hotspot users for profile/comment speed hints.", trust_role="identity_profile")
            add(name, "hotspot", "/ip/hotspot/user/profile", ["name", "rate-limit", "comment"], False, "Read Hotspot profiles for rate-limit fallback.", trust_role="speed_profile")

    warnings = []
    if routers_seen == 0:
        warnings.append({"code": "routeros_plan_no_routers", "severity": "warning", "path": "config.routers", "message": "No routers were present in the config, so the RouterOS collector plan is empty."})
    elif routers_planned == 0:
        warnings.append({"code": "routeros_plan_no_enabled_router_match", "severity": "warning", "path": "config.routers", "message": "No enabled routers matched the requested RouterOS collector plan filter."})
    if not commands:
        warnings.append({"code": "routeros_plan_no_enabled_sources", "severity": "warning", "path": "config.routers", "message": "No enabled PPPoE, DHCP, or Hotspot sources matched the requested RouterOS collector plan."})

    result = {
        "mode": "plan_only",
        "authority": "none",
        "status": "empty" if not commands else "ready",
        "router_count": routers_planned,
        "command_count": len(commands),
        "required_command_count": len([c for c in commands if c.get("required")]),
        "source_counts": source_counts,
        "commands": commands,
        "next_stage": "rust_routeros_transport_shadow",
        "full_rust_backend": False,
        "note": "This is a deterministic RouterOS read plan only. It does not open RouterOS connections or replace Python collectors.",
    }
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-routeros-collector-plan",
        "ok": True,
        "available": False,
        "skipped": True,
        "result": result,
        "errors": [],
        "warnings": warnings,
        "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_routeros_collector_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("build-routeros-collector-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_collector_plan(req_payload, started=started)
    return response



def _python_build_routeros_transport_session(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    plan_response = _python_build_routeros_collector_plan(payload, started=started)
    plan = plan_response.get("result") if isinstance(plan_response.get("result"), dict) else {}
    commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
    requested_router = str(payload.get("router") or "").strip()
    requested_source = str(payload.get("source") or "").strip().lower()
    rust_core = cfg.get("rust_core", {}) if isinstance(cfg.get("rust_core"), dict) else {}
    allow_live_reads = bool(payload.get("allow_live_reads", rust_core.get("allow_rust_routeros_live_reads", False)))
    allow_credentials = bool(payload.get("allow_credentials", rust_core.get("allow_rust_routeros_credentials", False)))
    authority = str(rust_core.get("routeros_transport_authority") or "plan_only")
    mode = str(payload.get("mode") or "rehearsal")
    execute = bool(payload.get("execute", False))
    sessions = []
    for router in cfg.get("routers", []) or []:
        if not isinstance(router, dict):
            continue
        name = str(router.get("name") or "unknown")
        if requested_router and requested_router != name:
            continue
        count = len([c for c in commands if c.get("router") == name and (not requested_source or c.get("source") == requested_source)])
        if count <= 0:
            continue
        sessions.append({
            "router": name,
            "address_present": bool(str(router.get("address") or "")),
            "address_redacted": "configured" if router.get("address") else "missing",
            "port": int(router.get("port") or 8728),
            "username_present": bool(str(router.get("username") or "")),
            "password_present": bool(str(router.get("password") or "")),
            "credential_material": "redacted",
            "sources": {
                "pppoe": bool((router.get("pppoe") or {}).get("enabled", False)),
                "dhcp": bool((router.get("dhcp") or {}).get("enabled", False)),
                "hotspot": bool((router.get("hotspot") or {}).get("enabled", False)),
            },
            "command_count": count,
            "status": "planned_not_connected",
            "connection_attempted": False,
        })
    errors = []
    warnings = list(plan_response.get("warnings") or [])
    wants_live = execute or mode == "live" or authority == "live_read_pilot"
    if wants_live:
        errors.append({"code": "routeros_live_transport_not_implemented", "severity": "error", "path": "rust_core.routeros_transport_authority", "message": "Live Rust RouterOS transport is not implemented in this release. This operation only rehearses sessions and redacts credentials."})
    if allow_live_reads and not allow_credentials:
        warnings.append({"code": "routeros_credentials_not_allowed", "severity": "warning", "path": "rust_core.allow_rust_routeros_credentials", "message": "Rust live reads were requested but credential access is not allowed; no live transport can be attempted."})
    result = {
        "mode": "transport_rehearsal",
        "status": "blocked" if errors else ("empty" if not commands else "ready_for_future_transport"),
        "authority": "none",
        "full_rust_backend": False,
        "live_transport_supported": False,
        "connection_attempt_count": 0,
        "allow_live_reads": allow_live_reads,
        "allow_credentials": allow_credentials,
        "routeros_transport_authority": authority,
        "router_count": len(sessions),
        "credential_router_count": len([s for s in sessions if s.get("username_present") or s.get("password_present")]),
        "command_count": len(commands),
        "sessions": sessions,
        "plan": plan,
        "next_stage": "rust_routeros_transport_client_pilot",
        "note": "This is a RouterOS transport-session rehearsal only. Rust does not connect to MikroTik or consume credentials in this release.",
    }
    return {"version": PROTOCOL_VERSION, "op": "build-routeros-transport-session", "ok": not errors, "available": False, "skipped": True, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_build_routeros_transport_session(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("build-routeros-transport-session", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_transport_session(req_payload, started=started)
    return response



def _python_build_routeros_live_read_pilot(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    plan_response = _python_build_routeros_collector_plan(payload, started=started)
    plan = plan_response.get("result") if isinstance(plan_response.get("result"), dict) else {}
    commands = plan.get("commands") if isinstance(plan.get("commands"), list) else []
    router = str(payload.get("router") or "").strip()
    source = str(payload.get("source") or "").strip().lower()
    path = str(payload.get("path") or "").strip()
    selected = None
    for cmd in commands:
        if router and cmd.get("router") != router:
            continue
        if source and cmd.get("source") != source:
            continue
        if path and cmd.get("path") != path:
            continue
        selected = {k: cmd.get(k) for k in ("router", "source", "path", "fields", "required", "purpose", "trust_role")}
        break
    rust_core = cfg.get("rust_core", {}) if isinstance(cfg.get("rust_core"), dict) else {}
    execute = bool(payload.get("execute", False)) or str(payload.get("mode") or "") == "live"
    pilot_enabled = bool(payload.get("pilot_enabled", rust_core.get("routeros_live_read_pilot", False)))
    allow_live_reads = bool(payload.get("allow_live_reads", rust_core.get("allow_rust_routeros_live_reads", False)))
    allow_credentials = bool(payload.get("allow_credentials", rust_core.get("allow_rust_routeros_credentials", False)))
    authority = str(rust_core.get("routeros_transport_authority") or "plan_only")
    errors = []
    warnings = list(plan_response.get("warnings") or [])
    if selected is None:
        errors.append({"code": "routeros_live_read_no_planned_command", "severity": "error", "path": "routeros_live_read_pilot", "message": "No RouterOS read command matched the requested router/source/path pilot selection."})
    if execute and not pilot_enabled:
        errors.append({"code": "routeros_live_read_pilot_disabled", "severity": "error", "path": "rust_core.routeros_live_read_pilot", "message": "Rust RouterOS live-read pilot is disabled."})
    if execute and not allow_live_reads:
        errors.append({"code": "routeros_live_reads_not_allowed", "severity": "error", "path": "rust_core.allow_rust_routeros_live_reads", "message": "Rust RouterOS live reads are not allowed by configuration."})
    if execute and not allow_credentials:
        errors.append({"code": "routeros_credentials_not_allowed", "severity": "error", "path": "rust_core.allow_rust_routeros_credentials", "message": "Rust RouterOS credential access is not allowed by configuration."})
    if execute and authority != "live_read_pilot":
        errors.append({"code": "routeros_transport_authority_not_live_read_pilot", "severity": "error", "path": "rust_core.routeros_transport_authority", "message": "Rust RouterOS transport authority must be live_read_pilot before any live-read pilot can be attempted."})
    if execute and pilot_enabled and allow_live_reads and allow_credentials and authority == "live_read_pilot":
        errors.append({"code": "routeros_live_transport_adapter_not_implemented", "severity": "error", "path": "routeros_live_read_pilot", "message": "Live RouterOS socket transport is still not implemented in Rust. v2.3 only builds and gates the pilot request contract."})
    result = {
        "mode": "routeros_live_read_pilot_contract",
        "status": "blocked" if errors else ("pilot_contract_ready" if selected else "empty"),
        "authority": "none",
        "full_rust_backend": False,
        "live_transport_supported": False,
        "execute_requested": execute,
        "connection_attempt_count": 0,
        "pilot_enabled": pilot_enabled,
        "allow_live_reads": allow_live_reads,
        "allow_credentials": allow_credentials,
        "routeros_transport_authority": authority,
        "selected_command": selected,
        "credential_material": "redacted",
        "next_stage": "rust_routeros_readonly_transport_adapter",
        "note": "v2.3 builds a gated live-read pilot contract only. It does not open RouterOS sockets or consume credentials.",
    }
    return {"version": PROTOCOL_VERSION, "op": "build-routeros-live-read-pilot", "ok": not errors, "available": False, "skipped": True, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_build_routeros_live_read_pilot(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("build-routeros-live-read-pilot", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_live_read_pilot(req_payload, started=started)
    return response



def _python_run_routeros_read_pilot(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    live = _python_build_routeros_live_read_pilot(payload, started=started)
    result_live = live.get("result") if isinstance(live.get("result"), dict) else {}
    selected = result_live.get("selected_command") if isinstance(result_live.get("selected_command"), dict) else {}
    adapter = str(payload.get("adapter") or "fixture")
    execute = bool(payload.get("execute", False))
    rows = payload.get("fixture_rows") if isinstance(payload.get("fixture_rows"), list) else (payload.get("rows") if isinstance(payload.get("rows"), list) else [])
    errors = list(live.get("errors") or [])
    warnings = list(live.get("warnings") or [])
    if adapter != "fixture":
        errors.append({"code": "routeros_live_adapter_not_implemented", "severity": "error", "path": "adapter", "message": "Only the offline fixture adapter is available in the Python fallback."})
    read_result = {
        "router": selected.get("router", "unknown"),
        "source": selected.get("source", "unknown"),
        "path": selected.get("path", ""),
        "status": str(payload.get("fixture_status") or "ok"),
        "rows": rows,
        "duration_ms": float(payload.get("duration_ms") or 0),
        "adapter": "fixture",
        "connection_attempted": False,
        "credential_material": "none",
    }
    safe_for_cleanup = not errors and read_result["status"] in {"ok", "zero_valid"}
    result = {
        "mode": "routeros_read_pilot_fixture",
        "status": "blocked" if errors else ("fixture_executed" if execute else "fixture_rehearsal"),
        "adapter": adapter,
        "execute_requested": execute,
        "executed": bool(execute and adapter == "fixture" and not errors),
        "connection_attempt_count": 0,
        "live_transport_supported": False,
        "full_rust_backend": False,
        "selected_command": selected,
        "read_result": read_result,
        "read_validation": {"status": "trusted" if safe_for_cleanup else "failed", "safe_for_cleanup": safe_for_cleanup, "command_count": 1 if selected else 0},
        "row_count": len(rows),
        "safe_for_cleanup": safe_for_cleanup,
        "credential_material": "redacted_or_absent",
        "next_stage": "rust_routeros_socket_transport_adapter",
        "note": "Python fallback executes only an offline fixture adapter; no RouterOS sockets are opened.",
    }
    return {"version": PROTOCOL_VERSION, "op": "run-routeros-read-pilot", "ok": not errors, "available": False, "skipped": True, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_run_routeros_read_pilot(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("run-routeros-read-pilot", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_read_pilot(req_payload, started=started)
    return response


def _python_build_routeros_api_sentence(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    command = payload.get("command") if isinstance(payload.get("command"), dict) else {}
    path = str(payload.get("path") or command.get("path") or "")
    fields = payload.get("fields") if isinstance(payload.get("fields"), list) else command.get("fields", [])
    fields = [str(f) for f in fields if str(f).strip()]
    sensitive = {"password", "secret", "token", "key"}
    clean_fields = [f for f in fields if not any(x in f.lower() for x in sensitive)]
    dropped = [f for f in fields if f not in clean_fields]
    errors = []
    warnings = []
    if not path:
        errors.append({"code": "routeros_api_sentence_missing_path", "severity": "error", "path": "path", "message": "RouterOS API sentence requires a command path."})
    if dropped:
        warnings.append({"code": "routeros_api_sentence_sensitive_fields_dropped", "severity": "warning", "path": "fields", "message": "Sensitive field names were removed from the proplist."})
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() == "live":
        errors.append({"code": "routeros_api_sentence_is_offline_only", "severity": "error", "path": "execute", "message": "RouterOS API sentence codec is offline-only in the Python fallback."})
    command_word = f"{path.rstrip('/')}/print" if path else ""
    words = [command_word] if command_word else []
    if clean_fields:
        words.append("=.proplist=" + ",".join(clean_fields))
    result = {
        "mode": "routeros_api_sentence_codec",
        "status": "blocked" if errors else "encoded",
        "authority": "none",
        "full_rust_backend": False,
        "live_transport_supported": False,
        "connection_attempt_count": 0,
        "path": path,
        "command_word": command_word,
        "sentence_words": words,
        "word_count": len(words),
        "dropped_sensitive_fields": dropped,
        "credential_material": "redacted_or_absent",
        "note": "Python fallback builds an offline RouterOS API sentence only; no sockets are opened.",
    }
    return {"version": PROTOCOL_VERSION, "op": "build-routeros-api-sentence", "ok": not errors, "available": False, "skipped": True, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_build_routeros_api_sentence(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("build-routeros-api-sentence", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_api_sentence(req_payload, started=started)
    return response



def _python_decode_routeros_api_reply(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    words = payload.get("words")
    if not isinstance(words, list):
        sentences = payload.get("sentences")
        if isinstance(sentences, list):
            words = []
            for sent in sentences:
                if isinstance(sent, list):
                    words.extend(str(x) for x in sent)
        else:
            raw_text = str(payload.get("raw_text") or "")
            words = [line.strip() for line in raw_text.splitlines() if line.strip()]
    errors = []
    warnings = []
    if not words:
        errors.append({"code": "routeros_api_reply_missing_words", "severity": "error", "path": "words", "message": "RouterOS API reply decoder requires words, sentences, or raw_text."})
    if bool(payload.get("execute")) or str(payload.get("adapter") or "").lower() == "live" or str(payload.get("mode") or "").lower() == "live":
        errors.append({"code": "routeros_api_reply_decode_is_offline_only", "severity": "error", "path": "execute", "message": "RouterOS API reply decoder is offline-only in the Python fallback."})
    rows = []
    traps = []
    done_count = 0
    current_type = None
    current = {}
    dropped = 0
    def flush():
        nonlocal current_type, current, done_count
        if not current_type:
            return
        if current_type == "!re":
            rows.append(dict(current))
        elif current_type in {"!trap", "!fatal"}:
            traps.append(dict(current))
        elif current_type == "!done":
            done_count += 1
        current_type = None
        current = {}
    for word in words:
        w = str(word)
        if w.startswith("!"):
            flush()
            current_type = w
            continue
        if not current_type or not w.startswith("="):
            continue
        rest = w[1:]
        if "=" not in rest:
            continue
        key, value = rest.split("=", 1)
        lowered = key.lower()
        if any(token in lowered for token in ("password", "secret", "token", "key")):
            dropped += 1
            continue
        current[key] = value
    flush()
    if dropped:
        warnings.append({"code": "routeros_api_reply_sensitive_fields_redacted", "severity": "warning", "path": "words", "message": "Sensitive RouterOS reply fields were removed from decoded rows/traps."})
    if errors:
        status = "blocked"
    elif traps:
        status = "trap"
    elif rows:
        status = "decoded"
    elif done_count:
        status = "done"
    else:
        status = "empty"
    result = {
        "mode": "routeros_api_reply_decoder",
        "status": status,
        "authority": "none",
        "full_rust_backend": False,
        "live_transport_supported": False,
        "connection_attempt_count": 0,
        "adapter": str(payload.get("adapter") or "offline_words"),
        "word_count": len(words),
        "row_count": len(rows),
        "trap_count": len(traps),
        "done_count": done_count,
        "rows": rows,
        "traps": traps,
        "dropped_sensitive_field_count": dropped,
        "dropped_sensitive_fields_redacted": True,
        "credential_material": "redacted_or_absent",
        "note": "Python fallback decodes already-captured RouterOS API reply words only; no sockets are opened.",
    }
    return {"version": PROTOCOL_VERSION, "op": "decode-routeros-api-reply", "ok": not errors, "available": False, "skipped": True, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_decode_routeros_api_reply(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("decode-routeros-api-reply", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_decode_routeros_api_reply(req_payload, started=started)
    return response

def _python_codec_routeros_api_frame(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Minimal Python fallback for offline RouterOS API frame codec."""
    started = started or time.perf_counter()
    direction = str(payload.get("direction") or "encode")
    errors: list[dict[str, Any]] = []

    def sensitive_word(word: str) -> bool:
        if not word.startswith("=") or "=" not in word[1:]:
            return False
        key = word[1:].split("=", 1)[0].lower()
        return any(part in key for part in ("password", "secret", "token", "key"))

    def enc_len(n: int) -> bytes:
        if n < 0x80:
            return bytes([n])
        if n < 0x4000:
            return bytes([(n >> 8) | 0x80, n & 0xff])
        if n < 0x20_0000:
            return bytes([(n >> 16) | 0xC0, (n >> 8) & 0xff, n & 0xff])
        if n < 0x1000_0000:
            return bytes([(n >> 24) | 0xE0, (n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff])
        return bytes([0xF0, (n >> 24) & 0xff, (n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff])

    if payload.get("execute") or str(payload.get("mode") or "offline") == "live":
        errors.append({"code": "routeros_api_frame_codec_is_offline_only", "severity": "error", "path": "execute", "message": "RouterOS API frame codec is offline-only."})

    if direction == "encode":
        words = payload.get("words") or payload.get("sentence_words") or []
        words = [str(w) for w in words if isinstance(w, (str, int, float))]
        out = bytearray()
        dropped = 0
        kept = 0
        for word in words:
            if sensitive_word(word):
                dropped += 1
                continue
            b = word.encode()
            out.extend(enc_len(len(b)))
            out.extend(b)
            kept += 1
        out.append(0)
        result = {
            "status": "frame_encoded" if not errors else "blocked",
            "direction": "encode",
            "word_count": kept,
            "byte_count": len(out),
            "hex": out.hex(),
            "zero_terminated": True,
            "connection_attempt_count": 0,
            "live_transport_supported": False,
            "dropped_sensitive_field_count": dropped,
            "dropped_sensitive_fields_redacted": True,
        }
    else:
        result = {
            "status": "fallback_decode_unavailable",
            "direction": direction,
            "word_count": 0,
            "connection_attempt_count": 0,
            "live_transport_supported": False,
        }
        if direction != "decode":
            errors.append({"code": "routeros_api_frame_unknown_direction", "severity": "error", "path": "direction", "message": f"Unknown RouterOS API frame codec direction: {direction}"})
    return {
        "version": PROTOCOL_VERSION,
        "op": "codec-routeros-api-frame",
        "ok": not errors,
        "available": False,
        "result": result,
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_frame_codec_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_codec_routeros_api_frame(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("codec-routeros-api-frame", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_codec_routeros_api_frame(req_payload, started=started)
    return response


def _python_run_routeros_offline_session(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Minimal Python fallback for the offline RouterOS session pipeline."""
    started = started or time.perf_counter()
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("adapter") or "offline_fixture") == "live" or str(payload.get("mode") or "offline_session") == "live" or bool(payload.get("execute")):
        errors.append({"code": "routeros_offline_session_is_not_live_transport", "severity": "error", "path": "adapter", "message": "RouterOS offline session fallback cannot open live sockets."})
    rows = payload.get("fixture_rows") if isinstance(payload.get("fixture_rows"), list) else []
    clean_rows = []
    dropped = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean = {}
        for key, value in row.items():
            lowered = str(key).lower()
            if any(part in lowered for part in ("password", "secret", "token", "key")):
                dropped += 1
                continue
            clean[str(key)] = value
        clean_rows.append(clean)
    if dropped:
        warnings.append({"code": "routeros_offline_session_fixture_sensitive_fields_redacted", "severity": "warning", "path": "fixture_rows", "message": "Sensitive fixture fields were removed."})
    result = {
        "mode": "routeros_offline_session_pipeline",
        "status": "blocked" if errors else "offline_session_complete",
        "authority": "none",
        "full_rust_backend": False,
        "live_transport_supported": False,
        "connection_attempt_count": 0,
        "adapter": str(payload.get("adapter") or "offline_fixture"),
        "row_count": len(clean_rows),
        "trap_count": 0,
        "reply_decode": {"status": "decoded" if clean_rows else "done", "rows": clean_rows, "row_count": len(clean_rows)},
        "dropped_sensitive_field_count": dropped,
        "dropped_sensitive_fields_redacted": True,
        "credential_material": "redacted_or_absent",
        "note": "Python fallback simulates offline RouterOS session fixtures only; no sockets are opened.",
    }
    return {"version": PROTOCOL_VERSION, "op": "run-routeros-offline-session", "ok": not errors, "available": False, "result": result, "errors": errors, "warnings": warnings, "meta": {"engine": "python-wrapper", "mode": "python_offline_session_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)}}


def rust_run_routeros_offline_session(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("run-routeros-offline-session", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_offline_session(req_payload, started=started)
    return response

def _python_run_routeros_tcp_connectivity_pilot(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for the RouterOS TCP connectivity pilot.

    The fallback is deliberately conservative: it never opens sockets. Real TCP
    probe authority belongs to the Rust core only when explicit gates are
    enabled and the binary supports the operation.
    """
    started = started or time.perf_counter()
    execute = bool(payload.get("execute"))
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if execute:
        errors.append({
            "code": "routeros_tcp_probe_requires_rust_core",
            "severity": "error",
            "path": "rust_core",
            "message": "Python fallback will not open RouterOS TCP sockets. Install the Rust core and enable explicit TCP pilot gates.",
        })
    result = {
        "mode": "python_fallback",
        "status": "blocked" if errors else "tcp_connect_rehearsal",
        "connection_attempt_count": 0,
        "connected": False,
        "authentication_attempt_count": 0,
        "api_sentence_write_count": 0,
        "api_reply_read_count": 0,
        "credential_material": "not_requested",
        "full_rust_backend": False,
        "live_api_transport_supported": False,
        "note": "Python fallback never opens RouterOS TCP sockets.",
    }
    return {
        "version": PROTOCOL_VERSION,
        "op": "run-routeros-tcp-connectivity-pilot",
        "available": False,
        "ok": not errors,
        "result": result,
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_tcp_probe_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_run_routeros_tcp_connectivity_pilot(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config or {})
    response = call_rust_core("run-routeros-tcp-connectivity-pilot", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_tcp_connectivity_pilot(req_payload, started=started)
    return response


def _python_validate_routeros_read_results(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    plan_result = plan.get("result") if isinstance(plan.get("result"), dict) else plan
    commands = plan_result.get("commands") if isinstance(plan_result.get("commands"), list) else []
    results = payload.get("results")
    if isinstance(results, dict):
        result_items = [v for v in results.values() if isinstance(v, dict)]
    elif isinstance(results, list):
        result_items = [v for v in results if isinstance(v, dict)]
    else:
        result_items = []
    expected = {}
    required = set()
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        key = f"{cmd.get('router','unknown')}|{cmd.get('source','unknown')}|{cmd.get('path','')}"
        expected[key] = cmd
        if bool(cmd.get("required", True)):
            required.add(key)
    seen = set()
    errors = []
    warnings = []
    command_reports = []
    total_rows = 0
    for item in result_items:
        router = str(item.get("router") or "unknown")
        source = str(item.get("source") or "unknown")
        path = str(item.get("path") or "")
        key = f"{router}|{source}|{path}"
        seen.add(key)
        status = str(item.get("status") or "ok")
        rows = item.get("rows") if isinstance(item.get("rows"), list) else []
        total_rows += len(rows)
        trusted = status in {"ok", "zero_valid"}
        if not trusted:
            errors.append({"code": "routeros_read_failed", "severity": "error", "path": f"results.{router}.{path}", "message": f"RouterOS read result for {router}/{source} {path} is not trusted: status={status}.", "safe_for_cleanup": False})
        command_reports.append({"router": router, "source": source, "path": path, "status": status, "trusted": trusted, "row_count": len(rows), "planned": key in expected})
    for key, cmd in expected.items():
        if key in required and key not in seen:
            errors.append({"code": "routeros_required_read_missing", "severity": "error", "path": f"plan.{cmd.get('router','unknown')}.{cmd.get('path','')}", "message": f"Required RouterOS read result is missing for {cmd.get('router','unknown')}/{cmd.get('source','unknown')} {cmd.get('path','')}.", "safe_for_cleanup": False})
            command_reports.append({"router": cmd.get("router","unknown"), "source": cmd.get("source","unknown"), "path": cmd.get("path",""), "status": "missing", "trusted": False, "row_count": 0, "planned": True})
    safe = not errors
    return {
        "version": PROTOCOL_VERSION,
        "op": "validate-routeros-read-results",
        "available": False,
        "ok": safe,
        "result": {
            "mode": "routeros_read_results_contract",
            "status": "trusted" if safe else "failed",
            "safe_for_cleanup": safe,
            "trusted": safe,
            "planned_command_count": len(expected),
            "received_result_count": len(seen),
            "command_count": len(command_reports),
            "total_row_count": total_rows,
            "commands": command_reports,
            "authority_note": "Python fallback validates command-level RouterOS read results. Live reads are still Python-authoritative.",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_read_results_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }




def _python_run_routeros_authenticated_read_fixture(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.3 RouterOS authenticated-read fixture.

    This is fixture-only. It never opens sockets, authenticates, sends API words,
    or replaces Python collectors.
    """
    started = started or time.perf_counter()
    session = _python_build_routeros_auth_session_contract({**(payload or {}), "execute": bool((payload or {}).get("execute", False))}, started=started)
    errors = list(session.get("errors") or [])
    session_result = session.get("result") or {}
    authenticated = bool(session_result.get("authenticated")) and session_result.get("status") == "auth_session_contract_ready"
    adapter = str((payload or {}).get("adapter") or "fixture")
    if adapter in {"live", "tcp", "routeros"} or str((payload or {}).get("mode") or "").lower() in {"live", "authenticated_live_read", "execute_live"}:
        errors.append({"code": "routeros_authenticated_read_live_adapter_not_implemented", "severity": "error", "path": "adapter", "message": "Python fallback cannot execute live RouterOS authenticated reads."})
    if not authenticated and not errors:
        errors.append({"code": "routeros_authenticated_read_session_not_authenticated", "severity": "error", "path": "auth_session", "message": "Authenticated read fixture requires an accepted auth session contract."})
    rows = (payload or {}).get("fixture_rows") if isinstance((payload or {}).get("fixture_rows"), list) else []
    status = "blocked" if errors else "authenticated_read_fixture_complete"
    return {
        "version": PROTOCOL_VERSION,
        "op": "run-routeros-authenticated-read-fixture",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "routeros_authenticated_read_fixture",
            "status": status,
            "adapter": adapter,
            "authenticated": authenticated,
            "auth_session": session_result,
            "row_count": len(rows),
            "trap_count": 0,
            "safe_for_cleanup": bool(rows) and not errors,
            "fixture_read_count": 1 if bool((payload or {}).get("execute")) and not errors else 0,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "credential_material": "redacted",
            "username_emitted": False,
            "password_emitted": False,
            "session_token_emitted": False,
            "full_rust_backend": False,
            "authority_note": "Python fallback only models authenticated read fixtures. It never performs live RouterOS reads."
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_authenticated_read_fixture_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_run_routeros_authenticated_read_fixture(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("run-routeros-authenticated-read-fixture", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_authenticated_read_fixture(req_payload, started=started)
    return response


def _python_run_routeros_live_read_adapter_pilot(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.4 live-read adapter contract.

    This is contract-only. It never opens sockets, authenticates, sends API words,
    reads RouterOS replies, or replaces Python collectors.
    """
    started = started or time.perf_counter()
    adapter = str((payload or {}).get("adapter") or "contract")
    mode = str((payload or {}).get("mode") or "contract")
    execute = bool((payload or {}).get("execute", False))
    live_requested = adapter in {"live", "tcp", "routeros"} or mode in {"live", "live_read", "execute_live", "authenticated_live_read"}
    errors: list[dict[str, Any]] = []
    if execute or live_requested:
        errors.append({"code": "routeros_live_read_adapter_not_implemented", "severity": "error", "path": "adapter", "message": "Python fallback cannot execute the Rust RouterOS live read adapter."})
    session = _python_build_routeros_auth_session_contract({**(payload or {}), "adapter": "fixture", "execute": True, "fixture_reply_words": (payload or {}).get("fixture_reply_words") or ["!done"]}, started=started)
    session_result = session.get("result") or {}
    authenticated = bool(session_result.get("authenticated")) and session_result.get("status") == "auth_session_contract_ready"
    status = "blocked" if errors else ("live_read_adapter_contract_ready" if authenticated else "live_read_adapter_contract_not_authenticated")
    return {
        "version": PROTOCOL_VERSION,
        "op": "run-routeros-live-read-adapter-pilot",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "routeros_live_read_adapter_pilot",
            "status": status,
            "adapter": adapter,
            "requested_mode": mode,
            "authority": ((payload or {}).get("rust_core") or {}).get("routeros_transport_authority", "plan_only") if isinstance((payload or {}).get("rust_core"), dict) else "plan_only",
            "full_rust_backend": False,
            "live_transport_supported": False,
            "live_adapter_implemented": False,
            "authenticated": authenticated,
            "auth_session": session_result,
            "path": (payload or {}).get("path") or "/ppp/active",
            "credential_material": "redacted",
            "username_emitted": False,
            "password_emitted": False,
            "session_token_emitted": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "collector_authority": "python_authoritative",
            "next_stage": "rust_routeros_live_read_socket_adapter",
            "authority_note": "Python fallback only models the live-read adapter contract. It never performs live RouterOS reads."
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_live_read_adapter_pilot_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_run_routeros_live_read_adapter_pilot(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("run-routeros-live-read-adapter-pilot", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_live_read_adapter_pilot(req_payload, started=started)
    return response



def _python_evaluate_collector_authority_pilot(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.5 Rust collector authority pilot gate.

    This fallback is non-authoritative. It never performs live reads or switches
    collector authority away from Python.
    """
    started = started or time.perf_counter()
    rc = {}
    if isinstance(payload.get("rust_core"), dict):
        rc.update(payload.get("rust_core") or {})
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    if isinstance((cfg.get("rust_core") if isinstance(cfg, dict) else None), dict):
        merged = dict(cfg.get("rust_core") or {})
        merged.update(rc)
        rc = merged
    path = str(payload.get("path") or "/ppp/active")
    source = str(payload.get("source") or ("pppoe" if path.startswith("/ppp/") else "dhcp" if path.startswith("/ip/dhcp-server") else "hotspot" if path.startswith("/ip/hotspot") else "unknown"))
    parity = payload.get("collector_parity") if isinstance(payload.get("collector_parity"), dict) else {}
    parity_result = parity.get("result") if isinstance(parity.get("result"), dict) else parity
    try:
        parity_score = float(parity_result.get("parity_score", 0))
    except Exception:
        parity_score = 0.0
    parity_verdict = str(parity_result.get("verdict") or "not_available")
    sources = rc.get("rust_collector_authority_sources") if isinstance(rc.get("rust_collector_authority_sources"), list) else []
    gates_ready = bool(rc.get("allow_rust_collector_authority")) and bool(rc.get("rust_collector_authority_pilot")) and bool(rc.get("allow_rust_routeros_live_read_adapter")) and bool(rc.get("routeros_live_read_adapter_pilot")) and (source in sources or "all" in sources) and (parity_score >= 99.99 or parity_verdict == "parity_pass") and rc.get("collector_authority_mode") == "rust_collector_authority_pilot"
    errors = []
    if payload.get("execute"):
        errors.append({"code": "rust_collector_authority_switch_not_implemented", "severity": "error", "path": "collector_authority", "message": "Python fallback cannot switch collector authority; Python collectors remain authoritative."})
    status = "blocked" if errors else ("collector_authority_pilot_gate_ready" if gates_ready else "collector_authority_shadow_only")
    return {
        "version": PROTOCOL_VERSION,
        "op": "evaluate-rust-collector-authority-pilot",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "rust_collector_authority_pilot_gate",
            "status": status,
            "source": source,
            "path": path,
            "collector_authority": "python_authoritative",
            "future_collector_authority": "rust_pilot_eligible" if gates_ready else "not_eligible",
            "gates_ready": gates_ready,
            "full_rust_backend": False,
            "rust_collector_authority_switch_supported": False,
            "python_collector_fallback_required": True,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_live_read_pilot",
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_pilot_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_evaluate_collector_authority_pilot(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("evaluate-rust-collector-authority-pilot", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_evaluate_collector_authority_pilot(req_payload, started=started)
    return response




def _python_build_collector_authority_manifest(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.6 collector authority decision manifest.

    This fallback is non-mutating and keeps Python collectors authoritative.
    """
    started = started or time.perf_counter()
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else [payload.get("source") or "pppoe"]
    decisions = []
    ready_count = 0
    shadow_count = 0
    for source in [str(s.get("source") if isinstance(s, dict) else s or "pppoe") for s in sources]:
        gate = _python_evaluate_collector_authority_pilot({**(payload or {}), "source": source, "execute": False}, started=started)
        gate_result = gate.get("result") or {}
        gates_ready = bool(gate_result.get("gates_ready"))
        if gates_ready:
            ready_count += 1
            decision = "rust_pilot_ready"
        else:
            shadow_count += 1
            decision = "python_authoritative_shadow"
        decisions.append({
            "source": source,
            "path": (payload.get("paths") or {}).get(source) if isinstance(payload.get("paths"), dict) else (payload.get("path") or ("/ppp/active" if source == "pppoe" else "/ip/dhcp-server/lease" if source == "dhcp" else "/ip/hotspot/active")),
            "decision": decision,
            "current_authority": "python",
            "proposed_authority": "rust_collector_pilot" if gates_ready else "python",
            "gates_ready": gates_ready,
            "fallback": "python_collector",
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
        })
    errors = []
    if payload.get("execute"):
        errors.append({"code": "collector_authority_manifest_execute_not_implemented", "severity": "error", "path": "collector_authority_manifest", "message": "Python fallback cannot execute collector authority manifest switches."})
    status = "blocked" if errors else ("collector_authority_manifest_ready" if ready_count and not shadow_count else "collector_authority_manifest_partial" if ready_count else "collector_authority_manifest_shadow_only")
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-manifest",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_decision_manifest",
            "status": status,
            "manifest_id": f"cam-python-{ready_count}-{shadow_count}-{len(decisions)}",
            "collector_authority": "python_authoritative",
            "future_collector_authority": "rust_pilot_candidates" if ready_count else "not_eligible",
            "source_count": len(decisions),
            "ready_count": ready_count,
            "shadow_count": shadow_count,
            "blocked_count": 0,
            "decisions": decisions,
            "full_rust_backend": False,
            "collector_authority_switch_supported": False,
            "python_collector_fallback_required": True,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_dry_run_shadow_integration",
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_manifest_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_manifest(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-manifest", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_manifest(req_payload, started=started)
    return response




def _python_build_collector_authority_selection(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.7 collector authority dry-run selection.

    This fallback is non-mutating. It never switches production collector
    authority and keeps Python collector output as the only cleanup/apply source.
    """
    started = started or time.perf_counter()
    manifest_resp = _python_build_collector_authority_manifest(payload, started=started)
    manifest = manifest_resp.get("result") or {}
    rust_core = (payload.get("rust_core") or (payload.get("config") or {}).get("rust_core") or {}) if isinstance(payload, dict) else {}
    allow = bool(rust_core.get("allow_collector_authority_dry_run_selection"))
    pilot = bool(rust_core.get("collector_authority_dry_run_selection_pilot"))
    mode = rust_core.get("collector_authority_mode") or "python_authoritative"
    errors = []
    if payload.get("execute") or str(payload.get("mode") or "").lower() in {"execute", "promote", "switch", "authority"}:
        errors.append({"code": "collector_authority_selection_execute_not_implemented", "severity": "error", "path": "collector_authority_selection", "message": "Python fallback cannot switch collector authority."})
    selections = []
    rust_shadow_count = 0
    python_count = 0
    for item in manifest.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        gates_ready = bool(item.get("gates_ready"))
        eligible = gates_ready and allow and pilot and mode == "rust_collector_authority_pilot" and item.get("decision") == "rust_pilot_ready"
        if eligible:
            rust_shadow_count += 1
            selected = "rust_shadow_collector"
        else:
            python_count += 1
            selected = "python_collector"
        selections.append({
            "source": item.get("source") or "unknown",
            "path": item.get("path") or "",
            "manifest_decision": item.get("decision") or "python_authoritative_shadow",
            "selected_for_dry_run": selected,
            "production_authority": "python_collector",
            "cleanup_authority": "python_policy",
            "apply_authority": "python_orchestrator",
            "rust_shadow_selected": eligible,
            "gates_ready": gates_ready,
            "collector_output_can_drive_cleanup": False,
            "collector_output_can_drive_apply": False,
            "requires_python_fallback": True,
            "fallback": "python_collector",
        })
    status = "blocked" if errors else ("collector_authority_dry_run_selection_ready" if rust_shadow_count else "collector_authority_dry_run_selection_python_only")
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-selection",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_dry_run_selection",
            "status": status,
            "selection_id": f"cas-python-{rust_shadow_count}-{python_count}-{len(selections)}",
            "manifest_id": manifest.get("manifest_id"),
            "manifest_status": manifest.get("status") or "unknown",
            "collector_authority": "python_authoritative",
            "production_authority": "python_collector",
            "dry_run_authority": "rust_shadow_candidate" if rust_shadow_count else "python_collector",
            "selection_count": len(selections),
            "rust_shadow_count": rust_shadow_count,
            "python_count": python_count,
            "blocked_count": 0,
            "allow_dry_run_selection": allow,
            "dry_run_selection_pilot": pilot,
            "selections": selections,
            "full_rust_backend": False,
            "collector_authority_switch_supported": False,
            "collector_output_can_drive_cleanup": False,
            "collector_output_can_drive_apply": False,
            "python_collector_fallback_required": True,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_dry_run_in_run_cycle",
        },
        "errors": errors,
        "warnings": manifest_resp.get("warnings") or [],
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_selection_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_selection(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-selection", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_selection(req_payload, started=started)
    return response


def _python_build_collector_authority_dry_run_bundle(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for v3.8 collector authority dry-run bundle.

    This fallback is non-mutating and never allows Rust shadow output to drive
    cleanup, writes, or apply. It exists only to keep the API shape stable when
    the Rust core is unavailable.
    """
    started = started or time.perf_counter()
    selection_resp = _python_build_collector_authority_selection(payload, started=started)
    selection = selection_resp.get("result") or {}
    rust_core = (payload.get("rust_core") or (payload.get("config") or {}).get("rust_core") or {}) if isinstance(payload, dict) else {}
    allow = bool(rust_core.get("allow_collector_authority_dry_run_bundle"))
    pilot = bool(rust_core.get("collector_authority_dry_run_bundle_pilot"))
    rust_shadow_requested = bool(selection.get("rust_shadow_count")) and allow and pilot
    errors = []
    if payload.get("execute") or str(payload.get("mode") or "").lower() in {"execute", "promote", "switch", "authority", "apply"}:
        errors.append({"code": "collector_authority_dry_run_execute_not_implemented", "severity": "error", "path": "collector_authority_dry_run", "message": "Python fallback cannot execute or switch collector authority."})
    status = "blocked" if errors else ("collector_authority_dry_run_bundle_review" if rust_shadow_requested else "collector_authority_dry_run_bundle_python_only")
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-dry-run-bundle",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_dry_run_bundle",
            "status": status,
            "dry_run_bundle_id": f"cad-python-{1 if rust_shadow_requested else 0}",
            "collector_authority": "python_authoritative",
            "production_authority": "python_collector",
            "dry_run_authority": "rust_shadow_candidate" if rust_shadow_requested else "python_collector",
            "selection": selection,
            "rust_shadow_requested": rust_shadow_requested,
            "rust_bundle": {"normalized_count": 0, "normalized_rows": []},
            "parity": {"verdict": "not_available", "parity_score": 0.0},
            "normalized_count": 0,
            "full_rust_backend": False,
            "collector_authority_switch_supported": False,
            "collector_output_can_drive_cleanup": False,
            "collector_output_can_drive_apply": False,
            "python_collector_fallback_required": True,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "next_stage": "rust_collector_authority_shadow_run_cycle_integration",
        },
        "errors": errors,
        "warnings": selection_resp.get("warnings") or [],
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_dry_run_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_dry_run_bundle(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-dry-run-bundle", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_dry_run_bundle(req_payload, started=started)
    return response

def _python_build_run_cycle_rust_shadow_report(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = payload.get("rust_core") if isinstance(payload.get("rust_core"), dict) else ((payload.get("config") or {}).get("rust_core") if isinstance(payload.get("config"), dict) else {}) or {}
    allow = bool(rust_core.get("run_cycle_rust_shadow_report_enabled"))
    pilot = bool(rust_core.get("run_cycle_rust_shadow_report_pilot"))
    bundle_resp = _python_build_collector_authority_dry_run_bundle(payload, started=started)
    bundle = bundle_resp.get("result") if isinstance(bundle_resp.get("result"), dict) else {}
    rust_ready = bundle.get("status") == "collector_authority_dry_run_bundle_review" or bundle.get("status") == "collector_authority_dry_run_bundle_ready"
    rust_rows = int(bundle.get("normalized_count") or 0)
    python_rows = payload.get("python_rows") or payload.get("python_authoritative_rows") or payload.get("existing_rows") or []
    if not isinstance(python_rows, list):
        python_rows = []
    status = "run_cycle_rust_shadow_ready" if (allow and pilot and rust_ready and rust_rows > 0) else ("run_cycle_rust_shadow_available_not_enabled" if rust_ready else "run_cycle_rust_shadow_python_only")
    warnings = []
    if not (allow and pilot):
        warnings.append({"code": "run_cycle_rust_shadow_report_not_enabled", "severity": "warning", "path": "run_cycle_rust_shadow", "message": "run_cycle Rust-shadow report gates are not fully enabled; Python run_cycle remains authoritative."})
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-run-cycle-rust-shadow-report",
        "available": False,
        "ok": True,
        "result": {
            "mode": "run_cycle_rust_shadow_report",
            "status": status,
            "collector_authority": "python_authoritative",
            "production_authority": "python_run_cycle",
            "shadow_authority": "rust_shadow_diagnostic" if status == "run_cycle_rust_shadow_ready" else "disabled_or_python_only",
            "report_enabled": allow,
            "report_pilot": pilot,
            "rust_shadow_ready": bool(rust_ready),
            "python_row_count": len(python_rows),
            "rust_row_count": rust_rows,
            "collector_authority_dry_run_bundle": bundle,
            "full_rust_backend": False,
            "python_run_cycle_authoritative": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_run_cycle_shadow_ui",
        },
        "errors": [],
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_run_cycle_rust_shadow_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_run_cycle_rust_shadow_report(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-run-cycle-rust-shadow-report", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_run_cycle_rust_shadow_report(req_payload, started=started)
    return response


def _python_build_collector_authority_activation_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = payload.get("rust_core") if isinstance(payload.get("rust_core"), dict) else ((payload.get("config") or {}).get("rust_core") if isinstance(payload.get("config"), dict) else {}) or {}
    allow = bool(rust_core.get("allow_collector_authority_activation"))
    pilot = bool(rust_core.get("collector_authority_activation_pilot"))
    mode = str(rust_core.get("collector_authority_activation_mode") or "shadow_only")
    require_fallback = rust_core.get("collector_authority_require_python_fallback", True) is not False
    required_cycles = int(rust_core.get("collector_authority_min_shadow_cycles") or 3)
    successful_cycles = int(payload.get("successful_shadow_cycles") or rust_core.get("collector_authority_successful_shadow_cycles") or 0)
    report_resp = _python_build_run_cycle_rust_shadow_report(payload, started=started)
    report = report_resp.get("result") if isinstance(report_resp.get("result"), dict) else {}
    rust_shadow_ready = bool(report.get("rust_shadow_ready")) and report.get("status") == "run_cycle_rust_shadow_ready"
    errors = []
    warnings = []
    if payload.get("execute") or str(payload.get("mode") or "plan") in {"execute", "promote", "switch", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_activation_execute_not_implemented", "severity": "error", "path": "collector_authority_activation", "message": "Python fallback cannot activate Rust collector authority."})
    if not require_fallback:
        errors.append({"code": "collector_authority_activation_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_require_python_fallback", "message": "Collector authority pilot requires Python collector fallback in this release."})
    if successful_cycles < required_cycles:
        warnings.append({"code": "collector_authority_activation_shadow_cycles_insufficient", "severity": "warning", "path": "collector_authority_activation.successful_shadow_cycles", "message": "Not enough successful Rust-shadow cycles for collector authority activation."})
    ready = not errors and allow and pilot and mode == "rust_collector_authority_pilot" and require_fallback and rust_shadow_ready and successful_cycles >= required_cycles
    status = "blocked" if errors else ("collector_authority_activation_ready_for_pilot" if ready else "collector_authority_activation_shadow_only")
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-activation-plan",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_activation_plan",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_authority": "rust_collector_authority_pilot_candidate" if ready else "python_authoritative",
            "activation_requested": bool(allow and pilot and mode == "rust_collector_authority_pilot"),
            "allow_activation": allow,
            "activation_pilot": pilot,
            "activation_mode": mode,
            "require_python_fallback": require_fallback,
            "required_shadow_cycles": required_cycles,
            "successful_shadow_cycles": successful_cycles,
            "shadow_cycles_ok": successful_cycles >= required_cycles,
            "run_cycle_shadow_status": report.get("status"),
            "rust_shadow_ready": rust_shadow_ready,
            "python_row_count": report.get("python_row_count", 0),
            "rust_row_count": report.get("rust_row_count", 0),
            "run_cycle_rust_shadow_report": report,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_switch_supported": False,
            "python_collector_fallback_required": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_pilot_runtime_decision",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_activation_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_activation_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-activation-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_activation_plan(req_payload, started=started)
    return response



def _python_build_collector_authority_runtime_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = payload.get("rust_core") if isinstance(payload.get("rust_core"), dict) else ((payload.get("config") or {}).get("rust_core") if isinstance(payload.get("config"), dict) else {}) or {}
    allow = bool(rust_core.get("allow_collector_authority_runtime_contract"))
    pilot = bool(rust_core.get("collector_authority_runtime_pilot"))
    mode = str(rust_core.get("collector_authority_runtime_mode") or "contract_only")
    require_fallback = rust_core.get("collector_authority_runtime_require_python_fallback", True) is not False
    max_age = int(rust_core.get("collector_authority_runtime_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or rust_core.get("collector_authority_shadow_age_seconds") or 0)
    activation_resp = _python_build_collector_authority_activation_plan(payload, started=started)
    activation = activation_resp.get("result") if isinstance(activation_resp.get("result"), dict) else {}
    activation_ready = activation.get("status") == "collector_authority_activation_ready_for_pilot" and activation.get("production_collector_authority_switched") is False
    errors = []
    warnings = []
    if payload.get("execute") or str(payload.get("mode") or "contract") in {"execute", "promote", "switch", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_runtime_execute_not_implemented", "severity": "error", "path": "collector_authority_runtime", "message": "Python fallback cannot switch Rust collector authority."})
    if not require_fallback:
        errors.append({"code": "collector_authority_runtime_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_runtime_require_python_fallback", "message": "Collector authority runtime pilot requires Python collector fallback in this release."})
    if shadow_age > max_age:
        warnings.append({"code": "collector_authority_runtime_shadow_state_stale", "severity": "warning", "path": "collector_authority_runtime.shadow_age_seconds", "message": "Rust-shadow collector state is older than the runtime pilot freshness limit."})
    requested = bool(allow and pilot and mode == "rust_collector_authority_runtime_contract")
    ready = not errors and requested and activation_ready and require_fallback and shadow_age <= max_age
    status = "blocked" if errors else ("collector_authority_runtime_contract_ready" if ready else ("collector_authority_runtime_waiting_for_gates" if activation_ready else "collector_authority_runtime_shadow_only"))
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-runtime-contract",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_runtime_contract",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_authority": "rust_collector_authority_runtime_candidate" if ready else "python_authoritative",
            "runtime_requested": requested,
            "activation_status": activation.get("status"),
            "activation_ready": activation_ready,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_age,
            "shadow_fresh": shadow_age <= max_age,
            "collector_authority_activation_plan": activation,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_switch_supported": False,
            "python_collector_fallback_required": True,
            "runtime_contract_only": True,
            "rust_pilot_may_select_rows_for_diagnostics": ready,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_pilot_controlled_handoff",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_runtime_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_runtime_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-runtime-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_runtime_contract(req_payload, started=started)
    return response



def _python_build_collector_authority_switch_rehearsal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = (payload.get("rust_core") if isinstance(payload.get("rust_core"), dict) else (payload.get("config") or {}).get("rust_core") if isinstance(payload.get("config"), dict) else {}) or {}
    allow = bool(rust_core.get("allow_collector_authority_switch_rehearsal"))
    pilot = bool(rust_core.get("collector_authority_switch_rehearsal_pilot"))
    mode = str(rust_core.get("collector_authority_switch_mode") or "rehearsal_only")
    require_fallback = rust_core.get("collector_authority_switch_require_python_fallback", True) is not False
    require_confirm = rust_core.get("collector_authority_switch_require_manual_confirmation", True) is not False
    confirmation_ok = (not require_confirm) or payload.get("confirmation") == "CONFIRM_COLLECTOR_AUTHORITY_REHEARSAL"
    runtime = payload.get("collector_authority_runtime_contract") or {}
    if isinstance(runtime, dict) and isinstance(runtime.get("result"), dict):
        runtime = runtime.get("result")
    runtime_ready = isinstance(runtime, dict) and runtime.get("status") == "collector_authority_runtime_contract_ready"
    requested = bool(allow and pilot and mode == "rust_collector_authority_switch_rehearsal")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if payload.get("execute") or str(payload.get("mode") or "").lower() in {"execute", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_switch_execute_not_implemented", "severity": "error", "path": "collector_authority_switch", "message": "Python fallback cannot switch Rust collector authority."})
    if not require_fallback:
        errors.append({"code": "collector_authority_switch_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_switch_require_python_fallback", "message": "Collector authority switch rehearsal requires Python collector fallback in this release."})
    if not runtime_ready:
        warnings.append({"code": "collector_authority_switch_runtime_not_ready", "severity": "warning", "path": "collector_authority_runtime_contract", "message": "Collector authority runtime contract is not ready."})
    if not confirmation_ok:
        warnings.append({"code": "collector_authority_switch_confirmation_missing", "severity": "warning", "path": "collector_authority_switch.confirmation", "message": "Manual confirmation token is missing."})
    ready = bool(requested and runtime_ready and require_fallback and confirmation_ok and not errors)
    status = "blocked" if errors else ("collector_authority_switch_rehearsal_ready" if ready else ("collector_authority_switch_rehearsal_waiting_for_gates" if runtime_ready else "collector_authority_switch_rehearsal_shadow_only"))
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-collector-authority-switch-rehearsal",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_authority_switch_rehearsal",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_authority": "rust_collector_authority_rehearsal_candidate" if ready else "python_authoritative",
            "rehearsal_requested": requested,
            "allow_switch_rehearsal": allow,
            "switch_rehearsal_pilot": pilot,
            "switch_mode": mode,
            "runtime_ready": runtime_ready,
            "manual_confirmation_ok": confirmation_ok,
            "collector_authority_runtime_contract": runtime if isinstance(runtime, dict) else {},
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_switch_supported": False,
            "collector_authority_switch_executed": False,
            "python_collector_fallback_required": True,
            "switch_rehearsal_only": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_switch_rehearsal_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_switch_rehearsal(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-switch-rehearsal", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_switch_rehearsal(req_payload, started=started)
    return response


def _python_build_collector_authority_pilot_execution_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _extract_rust_core_config(payload)
    allow = bool(rust_core.get("allow_collector_authority_pilot_execution_contract"))
    pilot = bool(rust_core.get("collector_authority_pilot_execution_pilot"))
    mode = str(rust_core.get("collector_authority_pilot_execution_mode") or "contract_only")
    require_fallback = rust_core.get("collector_authority_pilot_execution_require_python_fallback", True) is not False
    require_confirm = rust_core.get("collector_authority_pilot_execution_require_manual_confirmation", True) is not False
    max_shadow_age = int(rust_core.get("collector_authority_pilot_execution_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirm) or payload.get("confirmation") == "CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION"
    switch = payload.get("collector_authority_switch_rehearsal") or {}
    if isinstance(switch, dict) and isinstance(switch.get("result"), dict):
        switch = switch.get("result") or {}
    if not isinstance(switch, dict) or not switch:
        switch_payload = dict(payload)
        switch_confirmation = payload.get("collector_authority_switch_confirmation") or payload.get("switch_confirmation")
        if switch_confirmation:
            switch_payload["confirmation"] = switch_confirmation
        switch = rust_build_collector_authority_switch_rehearsal(payload.get("config") or {}, switch_payload).get("result") or {}
    switch_ready = switch.get("status") == "collector_authority_switch_rehearsal_ready" and switch.get("production_collector_authority_switched") is False
    requested = bool(allow and pilot and mode == "rust_collector_authority_pilot_execution_contract")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_pilot_execution_not_implemented", "severity": "error", "path": "collector_authority_pilot_execution", "message": "Python fallback cannot execute Rust collector authority pilot execution."})
    if not require_fallback:
        errors.append({"code": "collector_authority_pilot_execution_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_pilot_execution_require_python_fallback", "message": "Collector authority pilot execution contract requires Python collector fallback in this release."})
    if not switch_ready:
        warnings.append({"code": "collector_authority_pilot_execution_switch_not_ready", "severity": "warning", "path": "collector_authority_switch_rehearsal", "message": "Collector authority switch rehearsal is not ready."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_pilot_execution_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow collector output is older than the configured maximum age."})
    if not confirmation_ok:
        warnings.append({"code": "collector_authority_pilot_execution_confirmation_missing", "severity": "warning", "path": "collector_authority_pilot_execution.confirmation", "message": "Manual confirmation token is missing."})
    ready = not errors and requested and switch_ready and require_fallback and confirmation_ok and shadow_age <= max_shadow_age
    status = "blocked" if errors else ("collector_authority_pilot_execution_contract_ready" if ready else ("collector_authority_pilot_execution_waiting_for_gates" if switch_ready else "collector_authority_pilot_execution_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-pilot-execution-contract",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_pilot_execution_contract",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_authority": "rust_collector_authority_pilot_candidate" if ready else "python_authoritative",
            "contract_requested": requested,
            "switch_ready": switch_ready,
            "manual_confirmation_ok": confirmation_ok,
            "collector_authority_switch_rehearsal": switch,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_switch_supported": False,
            "collector_authority_switch_executed": False,
            "collector_authority_pilot_execution_supported": False,
            "collector_authority_pilot_execution_executed": False,
            "python_collector_fallback_required": True,
            "pilot_execution_contract_only": True,
            "rust_pilot_may_be_observed": ready,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_pilot_execution_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_pilot_execution_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-pilot-execution-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_pilot_execution_contract(req_payload, started=started)
    return response


def _rows_for_pilot_result(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [r for r in value if isinstance(r, dict)]
    if isinstance(value, dict):
        return [r for r in value.values() if isinstance(r, dict)]
    return []


def _python_evaluate_collector_authority_pilot_result(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_collector_authority_pilot_result_evaluation"))
    pilot = bool(rust_core.get("collector_authority_pilot_result_evaluator_pilot"))
    mode = str(rust_core.get("collector_authority_pilot_result_mode") or "evaluate_only")
    require_contract = rust_core.get("collector_authority_pilot_result_require_execution_contract", True) is not False
    require_fallback = rust_core.get("collector_authority_pilot_result_require_python_fallback", True) is not False
    require_no_side_effects = rust_core.get("collector_authority_pilot_result_require_no_cleanup_apply", True) is not False
    require_parity = rust_core.get("collector_authority_pilot_result_require_parity", True) is not False
    max_shadow_age = int(rust_core.get("collector_authority_pilot_result_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    contract = payload.get("collector_authority_pilot_execution_contract") or payload.get("pilot_execution_contract") or {}
    if isinstance(contract, dict) and isinstance(contract.get("result"), dict):
        contract = contract.get("result") or {}
    if not isinstance(contract, dict) or not contract:
        contract = rust_build_collector_authority_pilot_execution_contract(payload.get("config") or {}, payload).get("result") or {}
    contract_ready = contract.get("status") == "collector_authority_pilot_execution_contract_ready" and contract.get("production_collector_authority_switched") is False and contract.get("python_collector_fallback_required") is True
    observed = payload.get("pilot_result") or payload.get("pilot_observation") or {}
    observed = observed if isinstance(observed, dict) else {}
    cleanup_attempted = bool(observed.get("cleanup_attempted") or payload.get("cleanup_attempted"))
    apply_attempted = bool(observed.get("apply_attempted") or payload.get("apply_attempted"))
    write_attempted = bool(observed.get("write_attempted") or payload.get("write_attempted"))
    authority_switched = bool(observed.get("production_collector_authority_switched") or payload.get("production_collector_authority_switched"))
    side_effect_free = not any([cleanup_attempted, apply_attempted, write_attempted, authority_switched])
    rust_rows = _rows_for_pilot_result(observed.get("rust_rows")) or _rows_for_pilot_result(payload.get("rust_rows"))
    python_rows = _rows_for_pilot_result(observed.get("python_rows")) or _rows_for_pilot_result(payload.get("python_rows"))
    parity = payload.get("collector_parity") if isinstance(payload.get("collector_parity"), dict) else {}
    if rust_rows or python_rows:
        parity = _python_compare_collector_bundle_parity({"python_rows": python_rows, "rust_rows": rust_rows}).get("result") or {}
    parity_pass = parity.get("verdict") == "parity_pass"
    observed_status = str(observed.get("status") or "pilot_result_not_supplied")
    observed_error_count = int(observed.get("error_count") or payload.get("pilot_error_count") or 0)
    observed_ok = observed_error_count == 0 and observed_status in {"pilot_shadow_complete", "pilot_result_pass", "collector_authority_pilot_result_pass", "pilot_completed", "ok", "pilot_result_not_supplied"}
    requested = bool(allow and pilot and mode == "rust_collector_authority_pilot_result_evaluation")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_pilot_result_execute_not_implemented", "severity": "error", "path": "collector_authority_pilot_result", "message": "Python fallback cannot execute collector authority pilot result actions."})
    if require_contract and not contract_ready:
        warnings.append({"code": "collector_authority_pilot_result_execution_contract_not_ready", "severity": "warning", "path": "collector_authority_pilot_execution_contract", "message": "Collector authority pilot execution contract is not ready."})
    if not require_fallback:
        errors.append({"code": "collector_authority_pilot_result_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_pilot_result_require_python_fallback", "message": "Collector authority pilot result evaluation requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_pilot_result_side_effect_detected", "severity": "error", "path": "collector_authority_pilot_result", "message": "Collector authority pilot result contains forbidden cleanup/apply/write/authority side effects."})
    if require_parity and not parity_pass:
        warnings.append({"code": "collector_authority_pilot_result_parity_not_passed", "severity": "warning", "path": "collector_parity", "message": "Collector authority pilot result parity has not passed."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_pilot_result_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow collector result is stale."})
    passed = (not errors and requested and (contract_ready or not require_contract) and require_fallback and side_effect_free and observed_ok and shadow_age <= max_shadow_age and (parity_pass or not require_parity))
    status = "blocked" if errors else ("collector_authority_pilot_result_pass" if passed else ("collector_authority_pilot_result_review" if contract_ready else "collector_authority_pilot_result_shadow_only"))
    return {
        "version": "1",
        "op": "evaluate-collector-authority-pilot-result",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_pilot_result_evaluation",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_authority": "rust_collector_authority_pilot_candidate_validated" if passed else "python_authoritative",
            "evaluation_requested": requested,
            "execution_contract_ready": contract_ready,
            "observed_status": observed_status,
            "observed_error_count": observed_error_count,
            "side_effect_free": side_effect_free,
            "parity": parity,
            "parity_pass": parity_pass,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_shadow_age,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_switch_executed": False,
            "collector_authority_pilot_result_evaluated": passed,
            "python_collector_fallback_required": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_pilot_handoff_manifest",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_pilot_result_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_evaluate_collector_authority_pilot_result(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("evaluate-collector-authority-pilot-result", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_evaluate_collector_authority_pilot_result(req_payload, started=started)
    return response



def _python_build_collector_authority_promotion_readiness(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_collector_authority_promotion_readiness"))
    pilot = bool(rust_core.get("collector_authority_promotion_readiness_pilot"))
    mode = str(rust_core.get("collector_authority_promotion_readiness_mode") or "readiness_only")
    require_result = rust_core.get("collector_authority_promotion_require_pilot_result", True) is not False
    require_fallback = rust_core.get("collector_authority_promotion_require_python_fallback", True) is not False
    require_confirmation = rust_core.get("collector_authority_promotion_require_manual_confirmation", True) is not False
    require_no_side_effects = rust_core.get("collector_authority_promotion_require_no_cleanup_apply", True) is not False
    max_shadow_age = int(rust_core.get("collector_authority_promotion_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS"

    pilot_result = payload.get("collector_authority_pilot_result_evaluation") or payload.get("pilot_result_evaluation") or payload.get("collector_authority_pilot_result") or {}
    if isinstance(pilot_result, dict) and isinstance(pilot_result.get("result"), dict):
        pilot_result = pilot_result.get("result") or {}
    if not isinstance(pilot_result, dict) or not pilot_result:
        pilot_result = rust_evaluate_collector_authority_pilot_result(payload.get("config") or {}, payload).get("result") or {}

    pilot_pass = (
        pilot_result.get("status") == "collector_authority_pilot_result_pass"
        and pilot_result.get("collector_authority_pilot_result_evaluated") is True
        and pilot_result.get("production_collector_authority_switched") is False
        and pilot_result.get("python_collector_fallback_required", True) is True
    )
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        pilot_result.get("cleanup_attempted"), pilot_result.get("apply_attempted"), pilot_result.get("write_attempted"), pilot_result.get("production_collector_authority_switched"),
    ])
    gates_ready = bool(allow and pilot and mode == "rust_collector_authority_promotion_readiness")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_promotion_execute_not_implemented", "severity": "error", "path": "collector_authority_promotion_readiness", "message": "Python fallback cannot execute collector authority promotion."})
    if require_result and not pilot_pass:
        warnings.append({"code": "collector_authority_promotion_pilot_result_not_passed", "severity": "warning", "path": "collector_authority_pilot_result", "message": "Pilot result has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_promotion_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Promotion readiness confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_promotion_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_promotion_require_python_fallback", "message": "Promotion readiness requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_promotion_side_effect_detected", "severity": "error", "path": "collector_authority_promotion_readiness", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_promotion_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_promotion_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Promotion readiness gates are not fully enabled."})

    ready = not errors and gates_ready and confirmation_ok and (pilot_pass or not require_result) and shadow_age <= max_shadow_age and side_effect_free and require_fallback
    review = not errors and pilot_pass and side_effect_free
    status = "blocked" if errors else ("collector_authority_promotion_readiness_ready" if ready else ("collector_authority_promotion_readiness_review" if review else "collector_authority_promotion_readiness_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-promotion-readiness",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_promotion_readiness",
            "status": status,
            "collector_authority": "python_authoritative",
            "promotion_ready": ready,
            "promotion_readiness_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_promotion_supported": False,
            "collector_authority_promotion_executed": False,
            "pilot_result_status": pilot_result.get("status"),
            "pilot_result_pass": pilot_pass,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "python_collector_fallback_required": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_shadow_age,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_promotion_readiness_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_promotion_readiness(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-promotion-readiness", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_promotion_readiness(req_payload, started=started)
    return response



def _python_build_collector_authority_promotion_execution_rehearsal(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_collector_authority_promotion_execution_rehearsal"))
    pilot = bool(rust_core.get("collector_authority_promotion_execution_rehearsal_pilot"))
    mode = str(rust_core.get("collector_authority_promotion_execution_mode") or "rehearsal_only")
    require_readiness = rust_core.get("collector_authority_promotion_execution_require_readiness", True) is not False
    require_fallback = rust_core.get("collector_authority_promotion_execution_require_python_fallback", True) is not False
    require_confirmation = rust_core.get("collector_authority_promotion_execution_require_manual_confirmation", True) is not False
    require_no_side_effects = rust_core.get("collector_authority_promotion_execution_require_no_cleanup_apply", True) is not False
    max_shadow_age = int(rust_core.get("collector_authority_promotion_execution_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL"

    readiness = payload.get("collector_authority_promotion_readiness") or payload.get("promotion_readiness") or payload.get("collector_authority_promotion_readiness_report") or {}
    if isinstance(readiness, dict) and isinstance(readiness.get("result"), dict):
        readiness = readiness.get("result") or {}
    if not isinstance(readiness, dict) or not readiness:
        nested = dict(payload)
        nested["confirmation"] = payload.get("collector_authority_promotion_readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS"
        readiness = rust_build_collector_authority_promotion_readiness(payload.get("config") or {}, nested).get("result") or {}

    readiness_ready = (
        readiness.get("status") == "collector_authority_promotion_readiness_ready"
        and readiness.get("promotion_ready") is True
        and readiness.get("production_collector_authority_switched") is False
        and readiness.get("python_collector_fallback_required", True) is True
    )
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        readiness.get("cleanup_attempted"), readiness.get("apply_attempted"), readiness.get("write_attempted"), readiness.get("production_collector_authority_switched"),
    ])
    gates_ready = bool(allow and pilot and mode == "rehearsal_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_promotion_execution_not_implemented", "severity": "error", "path": "collector_authority_promotion_execution_rehearsal", "message": "Python fallback cannot execute collector authority promotion."})
    if require_readiness and not readiness_ready:
        warnings.append({"code": "collector_authority_promotion_execution_readiness_not_ready", "severity": "warning", "path": "collector_authority_promotion_readiness", "message": "Promotion readiness has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_promotion_execution_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Promotion execution rehearsal confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_promotion_execution_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_promotion_execution_require_python_fallback", "message": "Promotion execution rehearsal requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_promotion_execution_side_effect_detected", "severity": "error", "path": "collector_authority_promotion_execution_rehearsal", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_promotion_execution_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_promotion_execution_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Promotion execution rehearsal gates are not fully enabled."})

    ready = not errors and gates_ready and confirmation_ok and (readiness_ready or not require_readiness) and shadow_age <= max_shadow_age and side_effect_free and require_fallback
    review = not errors and readiness_ready and side_effect_free
    status = "blocked" if errors else ("collector_authority_promotion_execution_rehearsal_ready" if ready else ("collector_authority_promotion_execution_rehearsal_review" if review else "collector_authority_promotion_execution_rehearsal_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-promotion-execution-rehearsal",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_promotion_execution_rehearsal",
            "status": status,
            "collector_authority": "python_authoritative",
            "promotion_execution_rehearsal_ready": ready,
            "promotion_execution_rehearsal_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_promotion_supported": False,
            "collector_authority_promotion_executed": False,
            "promotion_readiness_status": readiness.get("status"),
            "promotion_readiness_ready": readiness_ready,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "python_collector_fallback_required": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_shadow_age,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_promotion_execution_rehearsal_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_promotion_execution_rehearsal(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-promotion-execution-rehearsal", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_promotion_execution_rehearsal(req_payload, started=started)
    return response


def _python_build_collector_authority_promotion_commit_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_collector_authority_promotion_commit_plan"))
    pilot = bool(rust_core.get("collector_authority_promotion_commit_plan_pilot"))
    mode = str(rust_core.get("collector_authority_promotion_commit_mode") or "plan_only")
    require_rehearsal = rust_core.get("collector_authority_promotion_commit_require_execution_rehearsal", True) is not False
    require_fallback = rust_core.get("collector_authority_promotion_commit_require_python_fallback", True) is not False
    require_confirmation = rust_core.get("collector_authority_promotion_commit_require_manual_confirmation", True) is not False
    require_no_side_effects = rust_core.get("collector_authority_promotion_commit_require_no_cleanup_apply", True) is not False
    max_shadow_age = int(rust_core.get("collector_authority_promotion_commit_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN"

    rehearsal = payload.get("collector_authority_promotion_execution_rehearsal") or payload.get("promotion_execution_rehearsal") or payload.get("collector_authority_promotion_execution_report") or {}
    if isinstance(rehearsal, dict) and isinstance(rehearsal.get("result"), dict):
        rehearsal = rehearsal.get("result") or {}
    if not isinstance(rehearsal, dict) or not rehearsal:
        nested = dict(payload)
        nested["confirmation"] = payload.get("collector_authority_promotion_execution_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL"
        rehearsal = rust_build_collector_authority_promotion_execution_rehearsal(payload.get("config") or {}, nested).get("result") or {}

    rehearsal_ready = (
        rehearsal.get("status") == "collector_authority_promotion_execution_rehearsal_ready"
        and rehearsal.get("promotion_execution_rehearsal_ready") is True
        and rehearsal.get("production_collector_authority_switched") is False
        and rehearsal.get("python_collector_fallback_required", True) is True
    )
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        rehearsal.get("cleanup_attempted"), rehearsal.get("apply_attempted"), rehearsal.get("write_attempted"), rehearsal.get("production_collector_authority_switched"),
    ])
    gates_ready = bool(allow and pilot and mode == "plan_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "promote", "authority", "apply", "production"}:
        errors.append({"code": "collector_authority_promotion_commit_not_implemented", "severity": "error", "path": "collector_authority_promotion_commit_plan", "message": "Python fallback cannot commit collector authority promotion."})
    if require_rehearsal and not rehearsal_ready:
        warnings.append({"code": "collector_authority_promotion_commit_rehearsal_not_ready", "severity": "warning", "path": "collector_authority_promotion_execution_rehearsal", "message": "Promotion execution rehearsal has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_promotion_commit_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Promotion commit-plan confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_promotion_commit_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_promotion_commit_require_python_fallback", "message": "Promotion commit planning requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_promotion_commit_side_effect_detected", "severity": "error", "path": "collector_authority_promotion_commit_plan", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_promotion_commit_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_promotion_commit_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Promotion commit plan gates are not fully enabled."})

    ready = not errors and gates_ready and confirmation_ok and (rehearsal_ready or not require_rehearsal) and shadow_age <= max_shadow_age and side_effect_free and require_fallback
    review = not errors and rehearsal_ready and side_effect_free
    status = "blocked" if errors else ("collector_authority_promotion_commit_plan_ready" if ready else ("collector_authority_promotion_commit_plan_review" if review else "collector_authority_promotion_commit_plan_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-promotion-commit-plan",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_promotion_commit_plan",
            "status": status,
            "collector_authority": "python_authoritative",
            "promotion_commit_plan_ready": ready,
            "promotion_commit_plan_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_promotion_supported": False,
            "collector_authority_promotion_executed": False,
            "promotion_execution_rehearsal_status": rehearsal.get("status"),
            "promotion_execution_rehearsal_ready": rehearsal_ready,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "python_collector_fallback_required": True,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_shadow_age,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_promotion_commit_plan_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_promotion_commit_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-promotion-commit-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_promotion_commit_plan(req_payload, started=started)
    return response




def _python_build_collector_authority_promotion_cutover_ledger(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_collector_authority_promotion_cutover_ledger"))
    pilot = bool(rc.get("collector_authority_promotion_cutover_ledger_pilot"))
    mode = str(rc.get("collector_authority_promotion_cutover_mode") or "ledger_only")
    require_commit = bool(rc.get("collector_authority_promotion_cutover_require_commit_plan", True))
    require_fallback = bool(rc.get("collector_authority_promotion_cutover_require_python_fallback", True))
    require_confirmation = bool(rc.get("collector_authority_promotion_cutover_require_manual_confirmation", True))
    require_no_side_effects = bool(rc.get("collector_authority_promotion_cutover_require_no_cleanup_apply", True))
    require_rollback_path = bool(rc.get("collector_authority_promotion_cutover_require_rollback_path", True))
    max_shadow_age = int(rc.get("collector_authority_promotion_cutover_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or str(payload.get("confirmation") or "") == "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER"
    commit = payload.get("collector_authority_promotion_commit_plan") or payload.get("promotion_commit_plan") or {}
    if isinstance(commit, dict) and isinstance(commit.get("result"), dict):
        commit = commit.get("result")
    commit_ready = isinstance(commit, dict) and commit.get("status") == "collector_authority_promotion_commit_plan_ready" and bool(commit.get("promotion_commit_plan_ready")) and commit.get("production_collector_authority_switched") is False
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        isinstance(commit, dict) and commit.get("cleanup_attempted"), isinstance(commit, dict) and commit.get("apply_attempted"), isinstance(commit, dict) and commit.get("write_attempted"), isinstance(commit, dict) and commit.get("production_collector_authority_switched"),
    ])
    rollback_path = str(payload.get("rollback_path") or "python_fallback_revert")
    rollback_ready = (not require_rollback_path) or bool(rollback_path.strip())
    gates_ready = bool(allow and pilot and mode == "ledger_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "promote", "authority", "apply", "production", "cutover"}:
        errors.append({"code": "collector_authority_promotion_cutover_not_implemented", "severity": "error", "path": "collector_authority_promotion_cutover_ledger", "message": "Python fallback cannot execute collector authority promotion cutover."})
    if require_commit and not commit_ready:
        warnings.append({"code": "collector_authority_promotion_cutover_commit_plan_not_ready", "severity": "warning", "path": "collector_authority_promotion_commit_plan", "message": "Promotion commit plan has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_promotion_cutover_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Cutover ledger confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_promotion_cutover_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_promotion_cutover_require_python_fallback", "message": "Cutover ledger requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_promotion_cutover_side_effect_detected", "severity": "error", "path": "collector_authority_promotion_cutover_ledger", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_promotion_cutover_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not rollback_ready:
        warnings.append({"code": "collector_authority_promotion_cutover_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Cutover ledger requires a rollback path."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_promotion_cutover_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Cutover ledger gates are not fully enabled."})

    ready = not errors and gates_ready and confirmation_ok and (commit_ready or not require_commit) and shadow_age <= max_shadow_age and side_effect_free and require_fallback and rollback_ready
    review = not errors and commit_ready and side_effect_free and rollback_ready
    status = "blocked" if errors else ("collector_authority_promotion_cutover_ledger_ready" if ready else ("collector_authority_promotion_cutover_ledger_review" if review else "collector_authority_promotion_cutover_ledger_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-promotion-cutover-ledger",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_promotion_cutover_ledger",
            "status": status,
            "collector_authority": "python_authoritative",
            "cutover_ledger_ready": ready,
            "cutover_ledger_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_promotion_supported": False,
            "collector_authority_promotion_executed": False,
            "promotion_commit_plan_status": commit.get("status") if isinstance(commit, dict) else None,
            "promotion_commit_plan_ready": commit_ready,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "python_collector_fallback_required": True,
            "rollback_ready": rollback_ready,
            "rollback_path": rollback_path,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "shadow_age_seconds": shadow_age,
            "max_shadow_age_seconds": max_shadow_age,
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_promotion_cutover_ledger_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_promotion_cutover_ledger(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-promotion-cutover-ledger", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_promotion_cutover_ledger(req_payload, started=started)
    return response




def _python_build_collector_authority_production_freeze_gate(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_collector_authority_production_freeze_gate"))
    pilot = bool(rc.get("collector_authority_production_freeze_gate_pilot"))
    mode = str(rc.get("collector_authority_production_freeze_mode") or "freeze_only")
    require_cutover = bool(rc.get("collector_authority_production_freeze_require_cutover_ledger", True))
    require_fallback = bool(rc.get("collector_authority_production_freeze_require_python_fallback", True))
    require_confirmation = bool(rc.get("collector_authority_production_freeze_require_manual_confirmation", True))
    require_no_side_effects = bool(rc.get("collector_authority_production_freeze_require_no_cleanup_apply", True))
    require_rollback_path = bool(rc.get("collector_authority_production_freeze_require_rollback_path", True))
    require_maintenance_window = bool(rc.get("collector_authority_production_freeze_require_maintenance_window", True))
    require_operator_ack = bool(rc.get("collector_authority_production_freeze_require_operator_ack", True))
    max_shadow_age = int(rc.get("collector_authority_production_freeze_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or str(payload.get("confirmation") or "") == "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE"
    cutover = payload.get("collector_authority_promotion_cutover_ledger") or payload.get("promotion_cutover_ledger") or payload.get("collector_authority_cutover_ledger") or {}
    if isinstance(cutover, dict) and isinstance(cutover.get("result"), dict):
        cutover = cutover.get("result")
    cutover_ready = isinstance(cutover, dict) and cutover.get("status") == "collector_authority_promotion_cutover_ledger_ready" and bool(cutover.get("cutover_ledger_ready")) and cutover.get("production_collector_authority_switched") is False
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        isinstance(cutover, dict) and cutover.get("cleanup_attempted"), isinstance(cutover, dict) and cutover.get("apply_attempted"), isinstance(cutover, dict) and cutover.get("write_attempted"), isinstance(cutover, dict) and cutover.get("production_collector_authority_switched"),
    ])
    rollback_path = str(payload.get("rollback_path") or (cutover.get("rollback_path") if isinstance(cutover, dict) else "") or "python_fallback_revert")
    rollback_ready = (not require_rollback_path) or bool(rollback_path.strip())
    maintenance_window = str(payload.get("maintenance_window") or "")
    maintenance_ready = (not require_maintenance_window) or bool(maintenance_window.strip())
    operator_ack = bool(payload.get("operator_acknowledged"))
    operator_ready = (not require_operator_ack) or operator_ack
    gates_ready = bool(allow and pilot and mode == "freeze_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "promote", "authority", "apply", "production", "cutover"}:
        errors.append({"code": "collector_authority_production_freeze_execute_not_implemented", "severity": "error", "path": "collector_authority_production_freeze_gate", "message": "Python fallback cannot execute collector authority production switch."})
    if require_cutover and not cutover_ready:
        warnings.append({"code": "collector_authority_production_freeze_cutover_not_ready", "severity": "warning", "path": "collector_authority_promotion_cutover_ledger", "message": "Cutover ledger has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_production_freeze_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Production freeze confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_production_freeze_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_production_freeze_require_python_fallback", "message": "Production freeze still requires Python collector fallback in this release."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_production_freeze_side_effect_detected", "severity": "error", "path": "collector_authority_production_freeze_gate", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_production_freeze_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not rollback_ready:
        warnings.append({"code": "collector_authority_production_freeze_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Rollback path is required."})
    if not maintenance_ready:
        warnings.append({"code": "collector_authority_production_freeze_maintenance_window_required", "severity": "warning", "path": "maintenance_window", "message": "Maintenance window is required."})
    if not operator_ready:
        warnings.append({"code": "collector_authority_production_freeze_operator_ack_required", "severity": "warning", "path": "operator_acknowledged", "message": "Operator acknowledgment is required."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_production_freeze_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Production freeze gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (cutover_ready or not require_cutover) and shadow_age <= max_shadow_age and side_effect_free and require_fallback and rollback_ready and maintenance_ready and operator_ready
    review = not errors and cutover_ready and side_effect_free and rollback_ready
    status = "blocked" if errors else ("collector_authority_production_freeze_gate_ready" if ready else ("collector_authority_production_freeze_gate_review" if review else "collector_authority_production_freeze_gate_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-production-freeze-gate",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_production_freeze_gate",
            "status": status,
            "collector_authority": "python_authoritative",
            "production_freeze_ready": ready,
            "production_freeze_gate_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_production_switch_supported": False,
            "collector_authority_production_switch_executed": False,
            "python_backend_removable": False,
            "python_collector_fallback_required": True,
            "cutover_ledger_status": cutover.get("status") if isinstance(cutover, dict) else None,
            "cutover_ledger_ready": cutover_ready,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "rollback_ready": rollback_ready,
            "maintenance_window_ready": maintenance_ready,
            "operator_ack_ready": operator_ready,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "v5_collector_authority_production_switch_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_production_freeze_gate_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_production_freeze_gate(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-production-freeze-gate", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_production_freeze_gate(req_payload, started=started)
    return response




def _python_build_collector_authority_production_switch_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_collector_authority_production_switch_contract"))
    pilot = bool(rc.get("collector_authority_production_switch_contract_pilot"))
    mode = str(rc.get("collector_authority_production_switch_mode") or "contract_only")
    require_freeze = bool(rc.get("collector_authority_production_switch_require_freeze_gate", True))
    require_fallback = bool(rc.get("collector_authority_production_switch_require_python_fallback", True))
    require_confirmation = bool(rc.get("collector_authority_production_switch_require_manual_confirmation", True))
    require_no_side_effects = bool(rc.get("collector_authority_production_switch_require_no_cleanup_apply", True))
    require_rollback_path = bool(rc.get("collector_authority_production_switch_require_rollback_path", True))
    require_maintenance_window = bool(rc.get("collector_authority_production_switch_require_maintenance_window", True))
    require_operator_ack = bool(rc.get("collector_authority_production_switch_require_operator_ack", True))
    max_shadow_age = int(rc.get("collector_authority_production_switch_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or str(payload.get("confirmation") or "") == "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT"
    freeze = payload.get("collector_authority_production_freeze_gate") or payload.get("production_freeze_gate") or payload.get("collector_authority_freeze_gate") or {}
    if isinstance(freeze, dict) and isinstance(freeze.get("result"), dict):
        freeze = freeze.get("result")
    freeze_ready = isinstance(freeze, dict) and freeze.get("status") == "collector_authority_production_freeze_gate_ready" and bool(freeze.get("production_freeze_ready")) and freeze.get("production_collector_authority_switched") is False and freeze.get("python_backend_removable") is False
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("production_collector_authority_switched"),
        isinstance(freeze, dict) and freeze.get("cleanup_attempted"), isinstance(freeze, dict) and freeze.get("apply_attempted"), isinstance(freeze, dict) and freeze.get("write_attempted"), isinstance(freeze, dict) and freeze.get("production_collector_authority_switched"),
    ])
    rollback_path = str(payload.get("rollback_path") or (freeze.get("rollback_path") if isinstance(freeze, dict) else "") or "python_fallback_revert")
    rollback_ready = (not require_rollback_path) or bool(rollback_path.strip())
    maintenance_window = str(payload.get("maintenance_window") or (freeze.get("maintenance_window") if isinstance(freeze, dict) else "") or "")
    maintenance_ready = (not require_maintenance_window) or bool(maintenance_window.strip())
    operator_ack = bool(payload.get("operator_acknowledged") or (freeze.get("operator_acknowledged") if isinstance(freeze, dict) else False))
    operator_ready = (not require_operator_ack) or operator_ack
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "promote", "authority", "apply", "production", "cutover", "remove-python"}:
        errors.append({"code": "collector_authority_production_switch_execute_not_implemented", "severity": "error", "path": "collector_authority_production_switch_contract", "message": "Python fallback cannot execute collector authority production switch."})
    if require_freeze and not freeze_ready:
        warnings.append({"code": "collector_authority_production_switch_freeze_not_ready", "severity": "warning", "path": "collector_authority_production_freeze_gate", "message": "Production freeze gate has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "collector_authority_production_switch_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Production switch contract confirmation is required."})
    if not require_fallback:
        errors.append({"code": "collector_authority_production_switch_requires_python_fallback", "severity": "error", "path": "rust_core.collector_authority_production_switch_require_python_fallback", "message": "v5.0 still requires Python collector fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "collector_authority_production_switch_side_effect_detected", "severity": "error", "path": "collector_authority_production_switch_contract", "message": "Cleanup/apply/write/authority side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "collector_authority_production_switch_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not rollback_ready:
        warnings.append({"code": "collector_authority_production_switch_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Rollback path is required."})
    if not maintenance_ready:
        warnings.append({"code": "collector_authority_production_switch_maintenance_window_required", "severity": "warning", "path": "maintenance_window", "message": "Maintenance window is required."})
    if not operator_ready:
        warnings.append({"code": "collector_authority_production_switch_operator_ack_required", "severity": "warning", "path": "operator_acknowledged", "message": "Operator acknowledgment is required."})
    if not gates_ready:
        warnings.append({"code": "collector_authority_production_switch_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Production switch contract gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (freeze_ready or not require_freeze) and shadow_age <= max_shadow_age and side_effect_free and require_fallback and rollback_ready and maintenance_ready and operator_ready
    review = not errors and freeze_ready and side_effect_free and rollback_ready and maintenance_ready and operator_ready
    status = "blocked" if errors else ("collector_authority_production_switch_contract_ready" if ready else ("collector_authority_production_switch_contract_review" if review else "collector_authority_production_switch_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-collector-authority-production-switch-contract",
        "ok": not errors,
        "result": {
            "mode": "collector_authority_production_switch_contract",
            "status": status,
            "collector_authority": "python_authoritative",
            "target_collector_authority": "rust_collector_authority_contract_ready" if ready else "python_authoritative",
            "production_switch_contract_ready": ready,
            "production_switch_contract_only": True,
            "full_rust_backend": False,
            "production_collector_authority_switched": False,
            "collector_authority_production_switch_supported": True,
            "collector_authority_production_switch_executed": False,
            "python_backend_removable": False,
            "python_backend_required": True,
            "python_collector_fallback_required": True,
            "production_freeze_status": freeze.get("status") if isinstance(freeze, dict) else None,
            "production_freeze_ready": freeze_ready,
            "manual_confirmation_accepted": confirmation_ok,
            "gates_ready": gates_ready,
            "rollback_ready": rollback_ready,
            "maintenance_window_ready": maintenance_ready,
            "operator_ack_ready": operator_ready,
            "rust_can_drive_cleanup": False,
            "rust_can_drive_apply": False,
            "rust_can_write_generated_files": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_collector_authority_switch_executor",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_authority_production_switch_contract_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_collector_authority_production_switch_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-collector-authority-production-switch-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_collector_authority_production_switch_contract(req_payload, started=started)
    return response



def _python_build_rust_backend_api_handoff_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_backend_api_handoff_plan"))
    pilot = bool(rc.get("rust_backend_api_handoff_plan_pilot"))
    mode = str(rc.get("rust_backend_api_handoff_mode") or "plan_only")
    require_switch = rc.get("rust_backend_api_handoff_require_production_switch_contract", True) is not False
    require_fallback = rc.get("rust_backend_api_handoff_require_python_backend_fallback", True) is not False
    require_confirmation = rc.get("rust_backend_api_handoff_require_manual_confirmation", True) is not False
    require_webui = rc.get("rust_backend_api_handoff_require_webui_compatibility", True) is not False
    require_routes = rc.get("rust_backend_api_handoff_require_route_parity", True) is not False
    require_no_side_effects = rc.get("rust_backend_api_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_backend_api_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or str(payload.get("confirmation") or "") == "CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN"

    switch = payload.get("collector_authority_production_switch_contract") or payload.get("production_switch_contract") or {}
    if isinstance(switch, dict) and isinstance(switch.get("result"), dict):
        switch = switch.get("result") or {}
    if not isinstance(switch, dict) or not switch:
        nested = dict(payload)
        nested["confirmation"] = payload.get("collector_authority_production_switch_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT"
        switch = rust_build_collector_authority_production_switch_contract(payload.get("config") or {}, nested).get("result") or {}

    switch_ready = (
        isinstance(switch, dict)
        and switch.get("status") == "collector_authority_production_switch_contract_ready"
        and switch.get("production_switch_contract_ready") is True
        and switch.get("production_collector_authority_switched") is False
        and switch.get("python_backend_removable") is False
        and switch.get("python_backend_required", True) is True
    )
    webui_ux_unchanged = bool(payload.get("webui_ux_unchanged"))
    static_unchanged = bool(payload.get("webui_static_assets_unchanged", webui_ux_unchanged))
    webui_ready = (not require_webui) or (webui_ux_unchanged and static_unchanged)
    api_route_parity = bool(payload.get("api_route_parity"))
    api_route_count = int(payload.get("api_route_count") or 0)
    route_ready = (not require_routes) or (api_route_parity and api_route_count > 0)
    side_effect_free = not any([payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"), payload.get("python_backend_removed"), payload.get("api_traffic_switched_to_rust")])
    gates_ready = bool(allow and pilot and mode == "plan_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-flask", "production", "cutover"}:
        errors.append({"code": "rust_backend_api_handoff_execute_not_implemented", "severity": "error", "path": "rust_backend_api_handoff_plan", "message": "Python fallback cannot execute API handoff or remove Python."})
    if require_switch and not switch_ready:
        warnings.append({"code": "rust_backend_api_handoff_switch_contract_not_ready", "severity": "warning", "path": "collector_authority_production_switch_contract", "message": "Production switch contract has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_backend_api_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "API handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_backend_api_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_backend_api_handoff_require_python_backend_fallback", "message": "v5.1 still requires Python backend fallback."})
    if require_webui and not webui_ready:
        warnings.append({"code": "rust_backend_api_handoff_webui_compat_required", "severity": "warning", "path": "webui_ux_unchanged", "message": "Existing WebUI/UX compatibility is required."})
    if require_routes and not route_ready:
        warnings.append({"code": "rust_backend_api_handoff_route_parity_required", "severity": "warning", "path": "api_route_parity", "message": "API route parity inventory is required."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_backend_api_handoff_side_effect_detected", "severity": "error", "path": "rust_backend_api_handoff_plan", "message": "API handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_backend_api_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_backend_api_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "API handoff gates are not enabled."})
    ready = not errors and gates_ready and confirmation_ok and (switch_ready or not require_switch) and require_fallback and webui_ready and route_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and switch_ready and webui_ready and route_ready and side_effect_free
    status = "blocked" if errors else ("rust_backend_api_handoff_plan_ready" if ready else ("rust_backend_api_handoff_plan_review" if review else "rust_backend_api_handoff_plan_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-backend-api-handoff-plan",
        "ok": not errors,
        "result": {
            "mode": "rust_backend_api_handoff_plan",
            "status": status,
            "rust_backend_api_handoff_ready": ready,
            "webui_ux_unchanged": webui_ux_unchanged,
            "webui_static_assets_unchanged": static_unchanged,
            "api_route_parity": api_route_parity,
            "api_route_count": api_route_count,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "rust_api_service_authoritative": False,
            "rust_scheduler_authoritative": False,
            "rust_run_cycle_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_scheduler_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_backend_api_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_backend_api_handoff_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-backend-api-handoff-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_backend_api_handoff_plan(req_payload, started=started)
    return response



def _python_build_rust_backend_scheduler_handoff_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_backend_scheduler_handoff_plan"))
    pilot = bool(rc.get("rust_backend_scheduler_handoff_plan_pilot"))
    mode = str(rc.get("rust_backend_scheduler_handoff_mode") or "plan_only")
    require_api = rc.get("rust_backend_scheduler_handoff_require_api_handoff", True) is not False
    require_fallback = rc.get("rust_backend_scheduler_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_backend_scheduler_handoff_require_manual_confirmation", True) is not False
    require_run_cycle_shadow = rc.get("rust_backend_scheduler_handoff_require_run_cycle_shadow", True) is not False
    require_scheduler_parity = rc.get("rust_backend_scheduler_handoff_require_scheduler_parity", True) is not False
    require_no_side_effects = rc.get("rust_backend_scheduler_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_backend_scheduler_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or str(payload.get("confirmation") or "") == "CONFIRM_RUST_BACKEND_SCHEDULER_RUN_CYCLE_HANDOFF_PLAN"

    api_handoff = payload.get("rust_backend_api_handoff_plan") or payload.get("api_handoff_plan") or payload.get("rust_backend_api_handoff") or {}
    if isinstance(api_handoff, dict) and isinstance(api_handoff.get("result"), dict):
        api_handoff = api_handoff.get("result") or {}
    if not isinstance(api_handoff, dict) or not api_handoff:
        nested = dict(payload)
        nested["confirmation"] = payload.get("rust_backend_api_handoff_confirmation") or "CONFIRM_RUST_BACKEND_API_HANDOFF_PLAN"
        api_handoff = rust_build_rust_backend_api_handoff_plan(payload.get("config") or {}, nested).get("result") or {}

    api_ready = (
        isinstance(api_handoff, dict)
        and api_handoff.get("status") == "rust_backend_api_handoff_plan_ready"
        and api_handoff.get("rust_backend_api_handoff_ready") is True
        and api_handoff.get("webui_ux_unchanged") is True
        and api_handoff.get("python_backend_required", True) is True
        and api_handoff.get("python_backend_removed") is False
    )
    scheduler_interval = int(payload.get("scheduler_interval_seconds") or 30)
    scheduler_manifest_ready = bool(payload.get("scheduler_manifest_ready")) and scheduler_interval > 0
    run_cycle_shadow_ready = bool(payload.get("run_cycle_shadow_ready"))
    run_cycle_shadow_count = int(payload.get("run_cycle_shadow_count") or 0)
    run_cycle_ready = (not require_run_cycle_shadow) or (run_cycle_shadow_ready and run_cycle_shadow_count > 0)
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"),
        payload.get("python_backend_removed"), payload.get("scheduler_switched_to_rust"), payload.get("run_cycle_switched_to_rust"),
    ])
    gates_ready = bool(allow and pilot and mode == "plan_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-scheduler", "replace-run-cycle", "production", "cutover"}:
        errors.append({"code": "rust_backend_scheduler_handoff_execute_not_implemented", "severity": "error", "path": "rust_backend_scheduler_handoff_plan", "message": "Python fallback cannot execute scheduler/run_cycle handoff or remove Python."})
    if require_api and not api_ready:
        warnings.append({"code": "rust_backend_scheduler_handoff_api_handoff_not_ready", "severity": "warning", "path": "rust_backend_api_handoff_plan", "message": "Rust API handoff plan has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_backend_scheduler_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Scheduler/run_cycle handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_backend_scheduler_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_backend_scheduler_handoff_require_python_fallback", "message": "v5.2 still requires Python backend fallback."})
    if require_scheduler_parity and not scheduler_manifest_ready:
        warnings.append({"code": "rust_backend_scheduler_handoff_scheduler_manifest_required", "severity": "warning", "path": "scheduler_manifest_ready", "message": "Scheduler manifest is required."})
    if require_run_cycle_shadow and not run_cycle_ready:
        warnings.append({"code": "rust_backend_scheduler_handoff_run_cycle_shadow_required", "severity": "warning", "path": "run_cycle_shadow_ready", "message": "Run-cycle shadow success is required."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_backend_scheduler_handoff_side_effect_detected", "severity": "error", "path": "rust_backend_scheduler_handoff_plan", "message": "Scheduler/run_cycle side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_backend_scheduler_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_backend_scheduler_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Scheduler/run_cycle handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (api_ready or not require_api) and require_fallback and scheduler_manifest_ready and run_cycle_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and api_ready and scheduler_manifest_ready and run_cycle_ready and side_effect_free
    status = "blocked" if errors else ("rust_backend_scheduler_handoff_plan_ready" if ready else ("rust_backend_scheduler_handoff_plan_review" if review else "rust_backend_scheduler_handoff_plan_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-backend-scheduler-handoff-plan",
        "ok": not errors,
        "result": {
            "mode": "rust_backend_scheduler_handoff_plan",
            "status": status,
            "rust_backend_scheduler_handoff_ready": ready,
            "api_handoff_ready": api_ready,
            "scheduler_manifest_ready": scheduler_manifest_ready,
            "scheduler_interval_seconds": scheduler_interval,
            "run_cycle_shadow_ready": run_cycle_ready,
            "run_cycle_shadow_count": run_cycle_shadow_count,
            "webui_ux_unchanged": bool(api_handoff.get("webui_ux_unchanged")) if isinstance(api_handoff, dict) else False,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "rust_api_service_authoritative": False,
            "rust_scheduler_authoritative": False,
            "rust_run_cycle_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_run_cycle_orchestrator_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_backend_scheduler_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_backend_scheduler_handoff_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-backend-scheduler-handoff-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_backend_scheduler_handoff_plan(req_payload, started=started)
    return response




def _python_build_rust_run_cycle_orchestrator_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_run_cycle_orchestrator_handoff_contract"))
    pilot = bool(rc.get("rust_run_cycle_orchestrator_handoff_contract_pilot"))
    mode = str(rc.get("rust_run_cycle_orchestrator_handoff_mode") or "contract_only")
    require_scheduler = rc.get("rust_run_cycle_orchestrator_handoff_require_scheduler_handoff", True) is not False
    require_fallback = rc.get("rust_run_cycle_orchestrator_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_run_cycle_orchestrator_handoff_require_manual_confirmation", True) is not False
    require_run_cycle_shadow = rc.get("rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow", True) is not False
    require_config_state_shadow = rc.get("rust_run_cycle_orchestrator_handoff_require_config_state_shadow", True) is not False
    require_no_side_effects = rc.get("rust_run_cycle_orchestrator_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_RUN_CYCLE_ORCHESTRATOR_HANDOFF_CONTRACT"
    scheduler = payload.get("rust_backend_scheduler_handoff_plan") or payload.get("scheduler_handoff_plan") or {}
    if isinstance(scheduler, dict) and isinstance(scheduler.get("result"), dict):
        scheduler = scheduler.get("result") or {}
    scheduler_ready = isinstance(scheduler, dict) and scheduler.get("status") == "rust_backend_scheduler_handoff_plan_ready" and scheduler.get("rust_backend_scheduler_handoff_ready") is True and scheduler.get("rust_run_cycle_authoritative") is False
    run_cycle_ready = (not require_run_cycle_shadow) or (bool(payload.get("run_cycle_orchestrator_manifest_ready")) and bool(payload.get("run_cycle_shadow_ready")) and int(payload.get("run_cycle_shadow_count") or 0) > 0)
    config_state_ready = (not require_config_state_shadow) or (bool(payload.get("config_state_shadow_ready")) and int(payload.get("config_state_shadow_count") or 0) > 0)
    side_effect_free = not any([
        payload.get("cleanup_attempted"), payload.get("apply_attempted"), payload.get("write_attempted"),
        payload.get("python_backend_removed"), payload.get("scheduler_switched_to_rust"), payload.get("run_cycle_switched_to_rust"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-run-cycle", "production", "cutover", "authoritative"}:
        errors.append({"code": "rust_run_cycle_orchestrator_handoff_execute_not_implemented", "severity": "error", "path": "rust_run_cycle_orchestrator_handoff_contract", "message": "Python fallback cannot execute run_cycle orchestrator handoff or remove Python."})
    if require_scheduler and not scheduler_ready:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_scheduler_not_ready", "severity": "warning", "path": "rust_backend_scheduler_handoff_plan", "message": "Scheduler handoff plan has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Run-cycle orchestrator confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_run_cycle_orchestrator_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_run_cycle_orchestrator_handoff_require_python_fallback", "message": "v5.3 still requires Python backend fallback."})
    if require_run_cycle_shadow and not run_cycle_ready:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_shadow_required", "severity": "warning", "path": "run_cycle_shadow_ready", "message": "Run-cycle orchestrator manifest and shadow cycles are required."})
    if require_config_state_shadow and not config_state_ready:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_config_state_shadow_required", "severity": "warning", "path": "config_state_shadow_ready", "message": "Config/state shadow verification is required."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_run_cycle_orchestrator_handoff_side_effect_detected", "severity": "error", "path": "rust_run_cycle_orchestrator_handoff_contract", "message": "Run-cycle orchestrator side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_run_cycle_orchestrator_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Run-cycle orchestrator handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (scheduler_ready or not require_scheduler) and require_fallback and run_cycle_ready and config_state_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and scheduler_ready and run_cycle_ready and config_state_ready and side_effect_free
    status = "blocked" if errors else ("rust_run_cycle_orchestrator_handoff_contract_ready" if ready else ("rust_run_cycle_orchestrator_handoff_contract_review" if review else "rust_run_cycle_orchestrator_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-run-cycle-orchestrator-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_run_cycle_orchestrator_handoff_contract",
            "status": status,
            "rust_run_cycle_orchestrator_handoff_ready": ready,
            "scheduler_handoff_ready": scheduler_ready,
            "run_cycle_shadow_ready": run_cycle_ready,
            "config_state_shadow_ready": config_state_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_run_cycle_authoritative": True,
            "rust_run_cycle_authoritative": False,
            "rust_scheduler_authoritative": False,
            "rust_api_service_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_config_state_authority_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_run_cycle_orchestrator_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_run_cycle_orchestrator_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-run-cycle-orchestrator-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_run_cycle_orchestrator_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_config_state_authority_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_config_state_authority_handoff_contract"))
    pilot = bool(rc.get("rust_config_state_authority_handoff_contract_pilot"))
    mode = str(rc.get("rust_config_state_authority_handoff_mode") or "contract_only")
    require_run_cycle = rc.get("rust_config_state_authority_handoff_require_run_cycle_orchestrator", True) is not False
    require_fallback = rc.get("rust_config_state_authority_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_config_state_authority_handoff_require_manual_confirmation", True) is not False
    require_config_state = rc.get("rust_config_state_authority_handoff_require_config_state_shadow", True) is not False
    require_atomic = rc.get("rust_config_state_authority_handoff_require_atomic_writer_shadow", True) is not False
    require_journal = rc.get("rust_config_state_authority_handoff_require_transaction_journal_shadow", True) is not False
    require_audit = rc.get("rust_config_state_authority_handoff_require_audit_shadow", True) is not False
    require_rollback = rc.get("rust_config_state_authority_handoff_require_rollback_shadow", True) is not False
    require_no_side_effects = rc.get("rust_config_state_authority_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_config_state_authority_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_CONFIG_STATE_AUTHORITY_HANDOFF_CONTRACT"

    run_cycle = payload.get("rust_run_cycle_orchestrator_handoff_contract") or payload.get("run_cycle_orchestrator_handoff_contract") or {}
    if isinstance(run_cycle, dict) and isinstance(run_cycle.get("result"), dict):
        run_cycle = run_cycle.get("result") or {}
    run_cycle_ready = isinstance(run_cycle, dict) and run_cycle.get("status") == "rust_run_cycle_orchestrator_handoff_contract_ready" and run_cycle.get("rust_run_cycle_orchestrator_handoff_ready") is True and run_cycle.get("rust_run_cycle_authoritative") is False

    config_state_ready = (not require_config_state) or (bool(payload.get("config_state_shadow_ready")) and int(payload.get("config_state_shadow_count") or 0) > 0)
    atomic_ready = (not require_atomic) or (bool(payload.get("atomic_writer_shadow_ready")) and int(payload.get("atomic_writer_shadow_count") or 0) > 0)
    journal_ready = (not require_journal) or (bool(payload.get("transaction_journal_shadow_ready")) and int(payload.get("transaction_journal_shadow_count") or 0) > 0)
    audit_ready = (not require_audit) or (bool(payload.get("audit_shadow_ready")) and int(payload.get("audit_shadow_count") or 0) > 0)
    rollback_ready = (not require_rollback) or (bool(payload.get("rollback_manifest_shadow_ready")) and int(payload.get("rollback_manifest_shadow_count") or 0) > 0)
    side_effect_free = not any([
        payload.get("config_write_attempted"), payload.get("state_write_attempted"), payload.get("audit_write_attempted"), payload.get("journal_write_attempted"),
        payload.get("python_backend_removed"), payload.get("config_state_authority_switched_to_rust"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-config-state", "production", "authoritative", "write"}:
        errors.append({"code": "rust_config_state_authority_handoff_execute_not_implemented", "severity": "error", "path": "rust_config_state_authority_handoff_contract", "message": "Python fallback cannot execute config/state authority handoff or remove Python."})
    if require_run_cycle and not run_cycle_ready:
        warnings.append({"code": "rust_config_state_authority_handoff_run_cycle_not_ready", "severity": "warning", "path": "rust_run_cycle_orchestrator_handoff_contract", "message": "Run-cycle orchestrator handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_config_state_authority_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Config/state authority handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_config_state_authority_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_config_state_authority_handoff_require_python_fallback", "message": "v5.4 still requires Python backend fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_config_state_authority_handoff_side_effect_detected", "severity": "error", "path": "rust_config_state_authority_handoff_contract", "message": "Config/state handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_config_state_authority_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not all([config_state_ready, atomic_ready, journal_ready, audit_ready, rollback_ready]):
        warnings.append({"code": "rust_config_state_authority_handoff_shadow_requirements_missing", "severity": "warning", "path": "config_state_shadow_ready", "message": "One or more config/state shadow requirements are missing."})
    if not gates_ready:
        warnings.append({"code": "rust_config_state_authority_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Config/state authority handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (run_cycle_ready or not require_run_cycle) and require_fallback and config_state_ready and atomic_ready and journal_ready and audit_ready and rollback_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and run_cycle_ready and config_state_ready and atomic_ready and journal_ready and audit_ready and rollback_ready and side_effect_free
    status = "blocked" if errors else ("rust_config_state_authority_handoff_contract_ready" if ready else ("rust_config_state_authority_handoff_contract_review" if review else "rust_config_state_authority_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-config-state-authority-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_config_state_authority_handoff_contract",
            "status": status,
            "rust_config_state_authority_handoff_ready": ready,
            "run_cycle_orchestrator_handoff_ready": run_cycle_ready,
            "config_state_shadow_ready": config_state_ready,
            "atomic_writer_shadow_ready": atomic_ready,
            "transaction_journal_shadow_ready": journal_ready,
            "audit_shadow_ready": audit_ready,
            "rollback_manifest_shadow_ready": rollback_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_config_state_authoritative": True,
            "rust_config_state_authoritative": False,
            "rust_run_cycle_authoritative": False,
            "rust_api_service_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_live_collector_execution_authority_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_config_state_authority_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_config_state_authority_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-config-state-authority-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_config_state_authority_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_live_collector_authority_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_live_collector_authority_handoff_contract"))
    pilot = bool(rc.get("rust_live_collector_authority_handoff_contract_pilot"))
    mode = str(rc.get("rust_live_collector_authority_handoff_mode") or "contract_only")
    require_config_state = rc.get("rust_live_collector_authority_handoff_require_config_state_authority", True) is not False
    require_fallback = rc.get("rust_live_collector_authority_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_live_collector_authority_handoff_require_manual_confirmation", True) is not False
    require_live_shadow = rc.get("rust_live_collector_authority_handoff_require_live_collector_shadow", True) is not False
    require_adapter_shadow = rc.get("rust_live_collector_authority_handoff_require_routeros_adapter_shadow", True) is not False
    require_parity = rc.get("rust_live_collector_authority_handoff_require_collector_parity", True) is not False
    require_no_side_effects = rc.get("rust_live_collector_authority_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_live_collector_authority_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_LIVE_COLLECTOR_AUTHORITY_HANDOFF_CONTRACT"

    config_state = payload.get("rust_config_state_authority_handoff_contract") or payload.get("config_state_authority_handoff_contract") or {}
    if isinstance(config_state, dict) and isinstance(config_state.get("result"), dict):
        config_state = config_state.get("result") or {}
    config_state_ready = isinstance(config_state, dict) and config_state.get("status") == "rust_config_state_authority_handoff_contract_ready" and config_state.get("rust_config_state_authority_handoff_ready") is True and config_state.get("rust_config_state_authoritative") is False
    live_ready = (not require_live_shadow) or (bool(payload.get("live_collector_shadow_ready")) and int(payload.get("live_collector_shadow_count") or 0) > 0)
    adapter_ready = (not require_adapter_shadow) or (bool(payload.get("routeros_live_adapter_shadow_ready")) and int(payload.get("routeros_live_adapter_shadow_count") or 0) > 0)
    parity_verdict = str(payload.get("collector_parity_verdict") or "not_available")
    parity_score = float(payload.get("collector_parity_score") or 0)
    parity_ready = (not require_parity) or (parity_verdict == "parity_pass" and parity_score >= 99.0)
    side_effect_free = not any([
        payload.get("live_collector_authority_switched_to_rust"), payload.get("python_backend_removed"), payload.get("routeros_live_write_attempted"), payload.get("config_write_attempted"), payload.get("state_write_attempted"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-collector", "production", "authoritative", "live"}:
        errors.append({"code": "rust_live_collector_authority_handoff_execute_not_implemented", "severity": "error", "path": "rust_live_collector_authority_handoff_contract", "message": "Python fallback cannot execute live collector authority handoff or remove Python."})
    if require_config_state and not config_state_ready:
        warnings.append({"code": "rust_live_collector_authority_handoff_config_state_not_ready", "severity": "warning", "path": "rust_config_state_authority_handoff_contract", "message": "Config/state authority handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_live_collector_authority_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Live collector authority handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_live_collector_authority_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_live_collector_authority_handoff_require_python_fallback", "message": "v5.5 still requires Python backend fallback."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_live_collector_authority_handoff_side_effect_detected", "severity": "error", "path": "rust_live_collector_authority_handoff_contract", "message": "Live collector handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_live_collector_authority_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not all([live_ready, adapter_ready, parity_ready]):
        warnings.append({"code": "rust_live_collector_authority_handoff_shadow_requirements_missing", "severity": "warning", "path": "live_collector_shadow_ready", "message": "One or more live collector shadow requirements are missing."})
    if not gates_ready:
        warnings.append({"code": "rust_live_collector_authority_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Live collector authority handoff gates are not enabled."})
    ready = not errors and gates_ready and confirmation_ok and (config_state_ready or not require_config_state) and require_fallback and live_ready and adapter_ready and parity_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and config_state_ready and live_ready and adapter_ready and parity_ready and side_effect_free
    status = "blocked" if errors else ("rust_live_collector_authority_handoff_contract_ready" if ready else ("rust_live_collector_authority_handoff_contract_review" if review else "rust_live_collector_authority_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-live-collector-authority-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_live_collector_authority_handoff_contract",
            "status": status,
            "rust_live_collector_authority_handoff_ready": ready,
            "config_state_authority_handoff_ready": config_state_ready,
            "live_collector_shadow_ready": live_ready,
            "routeros_live_adapter_shadow_ready": adapter_ready,
            "collector_parity_ready": parity_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_live_collector_authoritative": True,
            "rust_live_collector_authoritative": False,
            "rust_config_state_authoritative": False,
            "rust_run_cycle_authoritative": False,
            "rust_api_service_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_circuit_builder_authority_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_live_collector_authority_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_live_collector_authority_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-live-collector-authority-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_live_collector_authority_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_circuit_builder_authority_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_circuit_builder_authority_handoff_contract"))
    pilot = bool(rc.get("rust_circuit_builder_authority_handoff_contract_pilot"))
    mode = str(rc.get("rust_circuit_builder_authority_handoff_mode") or "contract_only")
    require_live_collector = rc.get("rust_circuit_builder_authority_handoff_require_live_collector_authority", True) is not False
    require_fallback = rc.get("rust_circuit_builder_authority_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_circuit_builder_authority_handoff_require_manual_confirmation", True) is not False
    require_circuit_shadow = rc.get("rust_circuit_builder_authority_handoff_require_circuit_shadow", True) is not False
    require_shaped_parity = rc.get("rust_circuit_builder_authority_handoff_require_shaped_devices_parity", True) is not False
    require_parent_integrity = rc.get("rust_circuit_builder_authority_handoff_require_parent_integrity", True) is not False
    require_no_side_effects = rc.get("rust_circuit_builder_authority_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_circuit_builder_authority_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_CIRCUIT_BUILDER_AUTHORITY_HANDOFF_CONTRACT"

    live = payload.get("rust_live_collector_authority_handoff_contract") or payload.get("live_collector_authority_handoff_contract") or {}
    if isinstance(live, dict) and isinstance(live.get("result"), dict):
        live = live.get("result") or {}
    live_ready = isinstance(live, dict) and live.get("status") == "rust_live_collector_authority_handoff_contract_ready" and live.get("rust_live_collector_authority_handoff_ready") is True and live.get("rust_live_collector_authoritative") is False and live.get("python_live_collector_authoritative", True) is True
    circuit_ready = (not require_circuit_shadow) or (bool(payload.get("circuit_builder_shadow_ready")) and int(payload.get("circuit_builder_shadow_count") or 0) > 0)
    shaped_score = float(payload.get("shaped_devices_render_parity_score") or 0)
    shaped_ready = (not require_shaped_parity) or (bool(payload.get("shaped_devices_render_parity_ready")) and shaped_score >= 99.0)
    parent_ready = (not require_parent_integrity) or (bool(payload.get("parent_node_integrity_ready")) and int(payload.get("parent_node_error_count") or 0) == 0)
    side_effect_free = not any([
        payload.get("circuit_builder_authority_switched_to_rust"), payload.get("python_backend_removed"), payload.get("shaped_devices_write_attempted"), payload.get("config_write_attempted"), payload.get("state_write_attempted"), payload.get("apply_attempted"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-builder", "production", "authoritative", "build-live"}:
        errors.append({"code": "rust_circuit_builder_authority_handoff_execute_not_implemented", "severity": "error", "path": "rust_circuit_builder_authority_handoff_contract", "message": "Python fallback cannot execute circuit builder authority handoff or remove Python."})
    if require_live_collector and not live_ready:
        warnings.append({"code": "rust_circuit_builder_authority_handoff_live_collector_not_ready", "severity": "warning", "path": "rust_live_collector_authority_handoff_contract", "message": "Live collector authority handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_circuit_builder_authority_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Circuit builder authority handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_circuit_builder_authority_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_circuit_builder_authority_handoff_require_python_fallback", "message": "v5.6 still requires Python backend fallback."})
    if not all([circuit_ready, shaped_ready, parent_ready]):
        warnings.append({"code": "rust_circuit_builder_authority_handoff_shadow_requirements_missing", "severity": "warning", "path": "circuit_builder_shadow_ready", "message": "One or more circuit builder shadow requirements are missing."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_circuit_builder_authority_handoff_side_effect_detected", "severity": "error", "path": "rust_circuit_builder_authority_handoff_contract", "message": "Circuit builder handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_circuit_builder_authority_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_circuit_builder_authority_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Circuit builder authority handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (live_ready or not require_live_collector) and require_fallback and circuit_ready and shaped_ready and parent_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and live_ready and circuit_ready and shaped_ready and parent_ready and side_effect_free
    status = "blocked" if errors else ("rust_circuit_builder_authority_handoff_contract_ready" if ready else ("rust_circuit_builder_authority_handoff_contract_review" if review else "rust_circuit_builder_authority_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-circuit-builder-authority-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_circuit_builder_authority_handoff_contract",
            "status": status,
            "rust_circuit_builder_authority_handoff_ready": ready,
            "live_collector_authority_handoff_ready": live_ready,
            "circuit_builder_shadow_ready": circuit_ready,
            "shaped_devices_render_parity_ready": shaped_ready,
            "parent_node_integrity_ready": parent_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_circuit_builder_authoritative": True,
            "rust_circuit_builder_authoritative": False,
            "python_live_collector_authoritative": True,
            "rust_live_collector_authoritative": False,
            "rust_config_state_authoritative": False,
            "rust_run_cycle_authoritative": False,
            "rust_api_service_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_sync_engine_authority_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_circuit_builder_authority_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_circuit_builder_authority_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-circuit-builder-authority-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_circuit_builder_authority_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_sync_engine_authority_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_sync_engine_authority_handoff_contract"))
    pilot = bool(rc.get("rust_sync_engine_authority_handoff_contract_pilot"))
    mode = str(rc.get("rust_sync_engine_authority_handoff_mode") or "contract_only")
    require_circuit = rc.get("rust_sync_engine_authority_handoff_require_circuit_builder_authority", True) is not False
    require_fallback = rc.get("rust_sync_engine_authority_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_sync_engine_authority_handoff_require_manual_confirmation", True) is not False
    require_sync_plan = rc.get("rust_sync_engine_authority_handoff_require_sync_plan_shadow", True) is not False
    require_diff = rc.get("rust_sync_engine_authority_handoff_require_diff_parity", True) is not False
    require_apply_preview = rc.get("rust_sync_engine_authority_handoff_require_apply_manifest_preview", True) is not False
    require_cleanup = rc.get("rust_sync_engine_authority_handoff_require_cleanup_safety", True) is not False
    require_no_side_effects = rc.get("rust_sync_engine_authority_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_sync_engine_authority_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_SYNC_ENGINE_AUTHORITY_HANDOFF_CONTRACT"

    circuit = payload.get("rust_circuit_builder_authority_handoff_contract") or payload.get("circuit_builder_authority_handoff_contract") or {}
    if isinstance(circuit, dict) and isinstance(circuit.get("result"), dict):
        circuit = circuit.get("result") or {}
    circuit_ready = isinstance(circuit, dict) and circuit.get("status") == "rust_circuit_builder_authority_handoff_contract_ready" and circuit.get("rust_circuit_builder_authority_handoff_ready") is True and circuit.get("rust_circuit_builder_authoritative") is False and circuit.get("python_circuit_builder_authoritative", True) is True
    sync_ready = (not require_sync_plan) or (bool(payload.get("sync_plan_shadow_ready")) and int(payload.get("sync_plan_shadow_count") or 0) > 0)
    diff_score = float(payload.get("sync_diff_parity_score") or 0)
    diff_ready = (not require_diff) or (bool(payload.get("sync_diff_parity_ready")) and diff_score >= 99.0)
    preview_ready = (not require_apply_preview) or (bool(payload.get("apply_manifest_preview_ready")) and int(payload.get("apply_manifest_preview_blocker_count") or 0) == 0)
    cleanup_ready = (not require_cleanup) or (bool(payload.get("cleanup_safety_ready")) and int(payload.get("cleanup_candidate_count") or 0) == 0)
    side_effect_free = not any([
        payload.get("sync_engine_authority_switched_to_rust"), payload.get("python_backend_removed"), payload.get("shaped_devices_write_attempted"), payload.get("config_write_attempted"), payload.get("state_write_attempted"), payload.get("apply_attempted"), payload.get("cleanup_attempted"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-sync-engine", "production", "authoritative", "sync-live", "apply"}:
        errors.append({"code": "rust_sync_engine_authority_handoff_execute_not_implemented", "severity": "error", "path": "rust_sync_engine_authority_handoff_contract", "message": "Python fallback cannot execute sync engine authority handoff or remove Python."})
    if require_circuit and not circuit_ready:
        warnings.append({"code": "rust_sync_engine_authority_handoff_circuit_builder_not_ready", "severity": "warning", "path": "rust_circuit_builder_authority_handoff_contract", "message": "Circuit builder authority handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_sync_engine_authority_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Sync engine authority handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_sync_engine_authority_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_sync_engine_authority_handoff_require_python_fallback", "message": "v5.7 still requires Python backend fallback."})
    if not all([sync_ready, diff_ready, preview_ready, cleanup_ready]):
        warnings.append({"code": "rust_sync_engine_authority_handoff_shadow_requirements_missing", "severity": "warning", "path": "sync_plan_shadow_ready", "message": "One or more sync engine shadow requirements are missing."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_sync_engine_authority_handoff_side_effect_detected", "severity": "error", "path": "rust_sync_engine_authority_handoff_contract", "message": "Sync engine handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_sync_engine_authority_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_sync_engine_authority_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Sync engine authority handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (circuit_ready or not require_circuit) and require_fallback and sync_ready and diff_ready and preview_ready and cleanup_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and circuit_ready and sync_ready and diff_ready and preview_ready and cleanup_ready and side_effect_free
    status = "blocked" if errors else ("rust_sync_engine_authority_handoff_contract_ready" if ready else ("rust_sync_engine_authority_handoff_contract_review" if review else "rust_sync_engine_authority_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-sync-engine-authority-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_sync_engine_authority_handoff_contract",
            "status": status,
            "rust_sync_engine_authority_handoff_ready": ready,
            "circuit_builder_authority_handoff_ready": circuit_ready,
            "sync_plan_shadow_ready": sync_ready,
            "sync_diff_parity_ready": diff_ready,
            "apply_manifest_preview_ready": preview_ready,
            "cleanup_safety_ready": cleanup_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_sync_engine_authoritative": True,
            "rust_sync_engine_authoritative": False,
            "python_circuit_builder_authoritative": True,
            "rust_circuit_builder_authoritative": False,
            "rust_apply_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "next_stage": "rust_apply_journal_authority_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_sync_engine_authority_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_sync_engine_authority_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-sync-engine-authority-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_sync_engine_authority_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_apply_journal_rollback_authority_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_apply_journal_rollback_authority_handoff_contract"))
    pilot = bool(rc.get("rust_apply_journal_rollback_authority_handoff_contract_pilot"))
    mode = str(rc.get("rust_apply_journal_rollback_authority_handoff_mode") or "contract_only")
    require_sync = rc.get("rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority", True) is not False
    require_fallback = rc.get("rust_apply_journal_rollback_authority_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_apply_journal_rollback_authority_handoff_require_manual_confirmation", True) is not False
    require_apply = rc.get("rust_apply_journal_rollback_authority_handoff_require_apply_shadow", True) is not False
    require_journal = rc.get("rust_apply_journal_rollback_authority_handoff_require_journal_shadow", True) is not False
    require_rollback = rc.get("rust_apply_journal_rollback_authority_handoff_require_rollback_shadow", True) is not False
    require_audit = rc.get("rust_apply_journal_rollback_authority_handoff_require_audit_shadow", True) is not False
    require_no_side_effects = rc.get("rust_apply_journal_rollback_authority_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_APPLY_JOURNAL_ROLLBACK_AUTHORITY_HANDOFF_CONTRACT"

    sync = payload.get("rust_sync_engine_authority_handoff_contract") or payload.get("sync_engine_authority_handoff_contract") or {}
    if isinstance(sync, dict) and isinstance(sync.get("result"), dict):
        sync = sync.get("result") or {}
    sync_ready = isinstance(sync, dict) and sync.get("status") == "rust_sync_engine_authority_handoff_contract_ready" and sync.get("rust_sync_engine_authority_handoff_ready") is True and sync.get("rust_sync_engine_authoritative") is False and sync.get("python_sync_engine_authoritative", True) is True
    apply_ready = (not require_apply) or (bool(payload.get("apply_transaction_shadow_ready")) and bool(payload.get("apply_manifest_replay_ready")) and int(payload.get("apply_transaction_shadow_blocker_count") or 0) == 0)
    journal_ready = (not require_journal) or (bool(payload.get("transaction_journal_shadow_ready")) and bool(payload.get("journal_replay_parity_ready")) and int(payload.get("transaction_journal_shadow_error_count") or 0) == 0)
    rollback_ready = (not require_rollback) or (bool(payload.get("rollback_manifest_shadow_ready")) and bool(payload.get("rollback_dry_run_ready")) and int(payload.get("rollback_shadow_blocker_count") or 0) == 0)
    audit_ready = (not require_audit) or (bool(payload.get("audit_shadow_ready")) and bool(payload.get("audit_redaction_ready")) and int(payload.get("audit_shadow_error_count") or 0) == 0)
    side_effect_free = not any([
        payload.get("apply_authority_switched_to_rust"), payload.get("journal_authority_switched_to_rust"), payload.get("rollback_authority_switched_to_rust"), payload.get("python_backend_removed"), payload.get("shaped_devices_write_attempted"), payload.get("config_write_attempted"), payload.get("state_write_attempted"), payload.get("audit_write_attempted"), payload.get("journal_append_attempted"), payload.get("rollback_execute_attempted"), payload.get("apply_attempted"), payload.get("cleanup_attempted"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-apply", "production", "authoritative", "apply-live", "journal-live", "rollback-live"}:
        errors.append({"code": "rust_apply_journal_rollback_authority_handoff_execute_not_implemented", "severity": "error", "path": "rust_apply_journal_rollback_authority_handoff_contract", "message": "Python fallback cannot execute apply/journal/rollback authority handoff or remove Python."})
    if require_sync and not sync_ready:
        warnings.append({"code": "rust_apply_journal_rollback_authority_handoff_sync_engine_not_ready", "severity": "warning", "path": "rust_sync_engine_authority_handoff_contract", "message": "Sync engine authority handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_apply_journal_rollback_authority_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Apply/journal/rollback authority handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_apply_journal_rollback_authority_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_apply_journal_rollback_authority_handoff_require_python_fallback", "message": "v5.8 still requires Python backend fallback."})
    if not all([apply_ready, journal_ready, rollback_ready, audit_ready]):
        warnings.append({"code": "rust_apply_journal_rollback_authority_handoff_shadow_requirements_missing", "severity": "warning", "path": "apply_transaction_shadow_ready", "message": "One or more apply/journal/rollback shadow requirements are missing."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_apply_journal_rollback_authority_handoff_side_effect_detected", "severity": "error", "path": "rust_apply_journal_rollback_authority_handoff_contract", "message": "Apply/journal/rollback handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_apply_journal_rollback_authority_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_apply_journal_rollback_authority_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Apply/journal/rollback authority handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (sync_ready or not require_sync) and require_fallback and apply_ready and journal_ready and rollback_ready and audit_ready and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and sync_ready and apply_ready and journal_ready and rollback_ready and audit_ready and side_effect_free
    status = "blocked" if errors else ("rust_apply_journal_rollback_authority_handoff_contract_ready" if ready else ("rust_apply_journal_rollback_authority_handoff_contract_review" if review else "rust_apply_journal_rollback_authority_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-apply-journal-rollback-authority-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_apply_journal_rollback_authority_handoff_contract",
            "status": status,
            "rust_apply_journal_rollback_authority_handoff_ready": ready,
            "sync_engine_authority_handoff_ready": sync_ready,
            "apply_transaction_shadow_ready": apply_ready,
            "transaction_journal_shadow_ready": journal_ready,
            "rollback_manifest_shadow_ready": rollback_ready,
            "audit_shadow_ready": audit_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_apply_journal_rollback_authoritative": True,
            "rust_apply_journal_rollback_authoritative": False,
            "python_sync_engine_authoritative": True,
            "rust_sync_engine_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "journal_append_allowed": False,
            "rollback_execute_allowed": False,
            "next_stage": "rust_backend_service_runtime_handoff_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_apply_journal_rollback_authority_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_apply_journal_rollback_authority_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-apply-journal-rollback-authority-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_apply_journal_rollback_authority_handoff_contract(req_payload, started=started)
    return response



def _python_build_rust_backend_service_runtime_handoff_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_rust_backend_service_runtime_handoff_contract"))
    pilot = bool(rc.get("rust_backend_service_runtime_handoff_contract_pilot"))
    mode = str(rc.get("rust_backend_service_runtime_handoff_mode") or "contract_only")
    require_apply = rc.get("rust_backend_service_runtime_handoff_require_apply_journal_rollback_authority", True) is not False
    require_fallback = rc.get("rust_backend_service_runtime_handoff_require_python_fallback", True) is not False
    require_confirmation = rc.get("rust_backend_service_runtime_handoff_require_manual_confirmation", True) is not False
    require_route_parity = rc.get("rust_backend_service_runtime_handoff_require_route_parity", True) is not False
    require_static_assets = rc.get("rust_backend_service_runtime_handoff_require_static_assets", True) is not False
    require_service_supervision = rc.get("rust_backend_service_runtime_handoff_require_service_supervision", True) is not False
    require_api_shadow = rc.get("rust_backend_service_runtime_handoff_require_api_shadow", True) is not False
    require_no_side_effects = rc.get("rust_backend_service_runtime_handoff_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("rust_backend_service_runtime_handoff_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_BACKEND_SERVICE_RUNTIME_HANDOFF_CONTRACT"
    apply_handoff = payload.get("rust_apply_journal_rollback_authority_handoff_contract") or payload.get("apply_journal_rollback_authority_handoff_contract") or {}
    if isinstance(apply_handoff, dict) and isinstance(apply_handoff.get("result"), dict):
        apply_handoff = apply_handoff.get("result") or {}
    apply_ready = isinstance(apply_handoff, dict) and apply_handoff.get("status") == "rust_apply_journal_rollback_authority_handoff_contract_ready" and apply_handoff.get("rust_apply_journal_rollback_authority_handoff_ready") is True and apply_handoff.get("rust_apply_journal_rollback_authoritative") is False and apply_handoff.get("python_apply_journal_rollback_authoritative", True) is True
    route_parity_score = float(payload.get("api_route_parity_score") or 0)
    route_ready = bool(payload.get("api_route_parity_ready")) and bool(payload.get("webui_ux_unchanged")) and route_parity_score >= 100.0
    static_ready = bool(payload.get("static_assets_compat_ready")) and bool(payload.get("webui_static_asset_paths_unchanged")) and int(payload.get("static_asset_compat_error_count") or 0) == 0
    supervision_ready = bool(payload.get("rust_service_supervision_shadow_ready")) and bool(payload.get("rust_daemon_socket_shadow_ready")) and bool(payload.get("rust_service_healthcheck_shadow_ready")) and int(payload.get("rust_service_supervision_error_count") or 0) == 0
    api_shadow_ready = bool(payload.get("rust_api_shadow_ready")) and bool(payload.get("rust_api_response_parity_ready")) and int(payload.get("rust_api_shadow_error_count") or 0) == 0
    side_effect_free = not any([
        payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"), payload.get("rust_backend_live_bound"), payload.get("service_runtime_switched_to_rust"), payload.get("apply_attempted"), payload.get("cleanup_attempted"), payload.get("shaped_devices_write_attempted"), payload.get("journal_append_attempted"), payload.get("rollback_execute_attempted"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-flask", "bind-live-api", "production", "authoritative"}:
        errors.append({"code": "rust_backend_service_runtime_handoff_execute_not_implemented", "severity": "error", "path": "rust_backend_service_runtime_handoff_contract", "message": "Python fallback cannot execute backend service runtime handoff or remove Python."})
    if require_apply and not apply_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_apply_journal_not_ready", "severity": "warning", "path": "rust_apply_journal_rollback_authority_handoff_contract", "message": "Apply/journal/rollback authority handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_backend_service_runtime_handoff_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Service runtime handoff confirmation is required."})
    if not require_fallback:
        errors.append({"code": "rust_backend_service_runtime_handoff_requires_python_fallback", "severity": "error", "path": "rust_core.rust_backend_service_runtime_handoff_require_python_fallback", "message": "v5.9 still requires Python backend fallback."})
    if require_route_parity and not route_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_route_parity_required", "severity": "warning", "path": "api_route_parity_ready", "message": "API route parity is required."})
    if require_static_assets and not static_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_static_assets_required", "severity": "warning", "path": "static_assets_compat_ready", "message": "Static asset compatibility is required."})
    if require_service_supervision and not supervision_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_service_supervision_required", "severity": "warning", "path": "rust_service_supervision_shadow_ready", "message": "Rust service supervision shadow verification is required."})
    if require_api_shadow and not api_shadow_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_api_shadow_required", "severity": "warning", "path": "rust_api_shadow_ready", "message": "Rust API shadow response parity is required."})
    if require_no_side_effects and not side_effect_free:
        errors.append({"code": "rust_backend_service_runtime_handoff_side_effect_detected", "severity": "error", "path": "rust_backend_service_runtime_handoff_contract", "message": "Service runtime handoff side effects are forbidden."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_backend_service_runtime_handoff_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_backend_service_runtime_handoff_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Service runtime handoff gates are not enabled."})

    ready = not errors and gates_ready and confirmation_ok and (apply_ready or not require_apply) and require_fallback and (route_ready or not require_route_parity) and (static_ready or not require_static_assets) and (supervision_ready or not require_service_supervision) and (api_shadow_ready or not require_api_shadow) and side_effect_free and shadow_age <= max_shadow_age
    review = not errors and apply_ready and route_ready and static_ready and supervision_ready and api_shadow_ready and side_effect_free
    status = "blocked" if errors else ("rust_backend_service_runtime_handoff_contract_ready" if ready else ("rust_backend_service_runtime_handoff_contract_review" if review else "rust_backend_service_runtime_handoff_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-backend-service-runtime-handoff-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_backend_service_runtime_handoff_contract",
            "status": status,
            "rust_backend_service_runtime_handoff_ready": ready,
            "apply_journal_rollback_authority_handoff_ready": apply_ready,
            "api_route_parity_ready": route_ready,
            "static_assets_compat_ready": static_ready,
            "service_supervision_shadow_ready": supervision_ready,
            "rust_api_shadow_ready": api_shadow_ready,
            "webui_ux_unchanged": True,
            "full_rust_backend": False,
            "python_backend_removable": False,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_service_runtime_authoritative": True,
            "rust_service_runtime_authoritative": False,
            "python_api_routes_authoritative": True,
            "rust_api_routes_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "api_traffic_switch_allowed": False,
            "flask_disable_allowed": False,
            "next_stage": "full_rust_backend_production_readiness_gate",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_rust_backend_service_runtime_handoff_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_backend_service_runtime_handoff_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-backend-service-runtime-handoff-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_backend_service_runtime_handoff_contract(req_payload, started=started)
    return response



def _python_build_full_rust_backend_production_readiness_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_full_rust_backend_production_readiness_contract"))
    pilot = bool(rc.get("full_rust_backend_production_readiness_contract_pilot"))
    mode = str(rc.get("full_rust_backend_production_readiness_mode") or "contract_only")
    require_service = rc.get("full_rust_backend_production_readiness_require_service_runtime", True) is not False
    require_fallback = rc.get("full_rust_backend_production_readiness_require_python_fallback", True) is not False
    require_confirmation = rc.get("full_rust_backend_production_readiness_require_manual_confirmation", True) is not False
    require_webui = rc.get("full_rust_backend_production_readiness_require_webui_unchanged", True) is not False
    require_operator = rc.get("full_rust_backend_production_readiness_require_operator_final_review", True) is not False
    require_no_side_effects = rc.get("full_rust_backend_production_readiness_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("full_rust_backend_production_readiness_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT"
    service = payload.get("rust_backend_service_runtime_handoff_contract") or payload.get("backend_service_runtime_handoff_contract") or payload.get("rust_backend_service_runtime_handoff") or {}
    if isinstance(service, dict) and isinstance(service.get("result"), dict):
        service = service.get("result") or {}
    if not isinstance(service, dict) or not service:
        nested = dict(payload)
        nested["confirmation"] = payload.get("rust_backend_service_runtime_handoff_confirmation") or "CONFIRM_RUST_BACKEND_SERVICE_RUNTIME_HANDOFF_CONTRACT"
        service = rust_build_rust_backend_service_runtime_handoff_contract(payload.get("config") or {}, nested).get("result") or {}
    service_ready = isinstance(service, dict) and service.get("status") == "rust_backend_service_runtime_handoff_contract_ready" and service.get("rust_backend_service_runtime_handoff_ready") is True and service.get("rust_service_runtime_authoritative") is False and service.get("python_service_runtime_authoritative", True) is True
    webui_unchanged = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True)) and (not isinstance(service, dict) or service.get("webui_ux_unchanged", True) is True)
    operator_ok = (not require_operator) or bool(payload.get("operator_final_review_ack")) or str(payload.get("operator_ack") or "") == "FULL_RUST_BACKEND_REVIEWED"
    side_effect = any([
        payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"), payload.get("rust_backend_live_bound"), payload.get("service_runtime_switched_to_rust"), payload.get("rust_service_runtime_authoritative"), payload.get("rust_api_routes_authoritative"), payload.get("apply_attempted"), payload.get("cleanup_attempted"), payload.get("shaped_devices_write_attempted"), payload.get("journal_append_attempted"), payload.get("rollback_execute_attempted"),
        isinstance(service, dict) and service.get("python_backend_removed"), isinstance(service, dict) and service.get("api_traffic_switch_allowed"), isinstance(service, dict) and service.get("flask_disable_allowed"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "commit", "switch", "remove-python", "replace-flask", "bind-live-api", "production", "authoritative", "cutover"}:
        errors.append({"code": "full_rust_backend_production_readiness_execute_not_implemented", "severity": "error", "path": "full_rust_backend_production_readiness_contract", "message": "Python fallback cannot execute full Rust backend production cutover or remove Python."})
    if require_service and not service_ready:
        warnings.append({"code": "full_rust_backend_production_readiness_service_runtime_not_ready", "severity": "warning", "path": "rust_backend_service_runtime_handoff_contract", "message": "Service/runtime handoff has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "full_rust_backend_production_readiness_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Full Rust backend production-readiness confirmation is required."})
    if not require_fallback:
        errors.append({"code": "full_rust_backend_production_readiness_requires_python_fallback", "severity": "error", "path": "rust_core.full_rust_backend_production_readiness_require_python_fallback", "message": "v6.0 still requires Python backend fallback."})
    if require_webui and not webui_unchanged:
        warnings.append({"code": "full_rust_backend_production_readiness_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_operator and not operator_ok:
        warnings.append({"code": "full_rust_backend_production_readiness_operator_review_required", "severity": "warning", "path": "operator_final_review_ack", "message": "Operator final review acknowledgement is required."})
    if require_no_side_effects and side_effect:
        errors.append({"code": "full_rust_backend_production_readiness_side_effect_detected", "severity": "error", "path": "full_rust_backend_production_readiness_contract", "message": "Side effects are forbidden in this package."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "full_rust_backend_production_readiness_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "full_rust_backend_production_readiness_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Full backend readiness gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (service_ready or not require_service) and require_fallback and (webui_unchanged or not require_webui) and operator_ok and not side_effect and shadow_age <= max_shadow_age
    review = not errors and service_ready and webui_unchanged and not side_effect
    status = "blocked" if errors else ("full_rust_backend_production_readiness_contract_ready" if ready else ("full_rust_backend_production_readiness_contract_review" if review else "full_rust_backend_production_readiness_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-full-rust-backend-production-readiness-contract",
        "ok": not errors,
        "result": {
            "mode": "full_rust_backend_production_readiness_contract",
            "status": status,
            "full_rust_backend_production_readiness_ready": ready,
            "rust_backend_service_runtime_handoff_ready": service_ready,
            "webui_ux_unchanged": webui_unchanged,
            "operator_final_review_ack": operator_ok,
            "full_rust_backend": False,
            "full_rust_backend_candidate": ready,
            "full_rust_backend_production_enabled": False,
            "python_backend_removable": False,
            "python_backend_retirement_candidate": ready,
            "python_backend_removed": False,
            "python_backend_required": True,
            "python_backend_fallback_required": True,
            "python_service_runtime_authoritative": True,
            "rust_service_runtime_authoritative": False,
            "python_api_routes_authoritative": True,
            "rust_api_routes_authoritative": False,
            "safe_for_cleanup": False,
            "write_allowed": False,
            "apply_allowed": False,
            "api_traffic_switch_allowed": False,
            "flask_disable_allowed": False,
            "python_removal_allowed": False,
            "next_stage": "full_rust_backend_production_cutover_and_python_retirement_plan",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_full_rust_backend_production_readiness_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_full_rust_backend_production_readiness_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-full-rust-backend-production-readiness-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_full_rust_backend_production_readiness_contract(req_payload, started=started)
    return response




def _python_build_full_rust_backend_cutover_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_full_rust_backend_cutover_plan"))
    pilot = bool(rc.get("full_rust_backend_cutover_plan_pilot"))
    mode = str(rc.get("full_rust_backend_cutover_mode") or "plan_only")
    require_readiness = rc.get("full_rust_backend_cutover_require_production_readiness", True) is not False
    require_fallback = rc.get("full_rust_backend_cutover_require_python_fallback", True) is not False
    require_confirmation = rc.get("full_rust_backend_cutover_require_manual_confirmation", True) is not False
    require_webui = rc.get("full_rust_backend_cutover_require_webui_unchanged", True) is not False
    require_rollback = rc.get("full_rust_backend_cutover_require_rollback_path", True) is not False
    require_operator = rc.get("full_rust_backend_cutover_require_operator_approval", True) is not False
    require_no_side_effects = rc.get("full_rust_backend_cutover_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("full_rust_backend_cutover_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_FULL_RUST_BACKEND_CUTOVER_PLAN"
    readiness = payload.get("full_rust_backend_production_readiness_contract") or payload.get("full_rust_backend_readiness_contract") or {}
    if isinstance(readiness, dict) and isinstance(readiness.get("result"), dict):
        readiness = readiness.get("result") or {}
    if not isinstance(readiness, dict) or not readiness:
        nested = dict(payload)
        nested["confirmation"] = payload.get("full_rust_backend_production_readiness_confirmation") or "CONFIRM_FULL_RUST_BACKEND_PRODUCTION_READINESS_CONTRACT"
        readiness = rust_build_full_rust_backend_production_readiness_contract(payload.get("config") or {}, nested).get("result") or {}
    readiness_ready = isinstance(readiness, dict) and readiness.get("status") == "full_rust_backend_production_readiness_contract_ready" and readiness.get("full_rust_backend_production_readiness_ready") is True and readiness.get("python_backend_removed") is False
    webui_ok = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True))
    rollback_path = str(payload.get("rollback_path") or "python_backend_reenable_and_flask_route_restore")
    rollback_ready = (not require_rollback) or bool(rollback_path.strip())
    operator_ok = (not require_operator) or bool(payload.get("operator_cutover_approval_ack")) or payload.get("operator_ack") == "FULL_RUST_BACKEND_CUTOVER_REVIEWED"
    side_effects = any([payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"), payload.get("rust_service_runtime_authoritative"), payload.get("generated_files_written"), payload.get("libreqos_apply_executed"), payload.get("cleanup_authority_transferred"), payload.get("remove_python")])
    gates_ready = bool(allow and pilot and mode == "plan_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "remove-python", "replace-flask", "bind-live-api", "switch", "authoritative", "production", "cutover-now"}:
        errors.append({"code": "full_rust_backend_cutover_execute_not_implemented", "severity": "error", "path": "full_rust_backend_cutover_plan", "message": "Python fallback cannot execute full Rust backend cutover or remove Python."})
    if require_readiness and not readiness_ready:
        warnings.append({"code": "full_rust_backend_cutover_readiness_not_ready", "severity": "warning", "path": "full_rust_backend_production_readiness_contract", "message": "Full backend production-readiness has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "full_rust_backend_cutover_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Full Rust backend cutover confirmation is required."})
    if not require_fallback:
        errors.append({"code": "full_rust_backend_cutover_requires_python_fallback", "severity": "error", "path": "rust_core.full_rust_backend_cutover_require_python_fallback", "message": "v6.1 still requires Python backend fallback."})
    if require_webui and not webui_ok:
        warnings.append({"code": "full_rust_backend_cutover_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_rollback and not rollback_ready:
        warnings.append({"code": "full_rust_backend_cutover_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Python backend rollback path is required."})
    if require_operator and not operator_ok:
        warnings.append({"code": "full_rust_backend_cutover_operator_approval_required", "severity": "warning", "path": "operator_cutover_approval_ack", "message": "Operator cutover approval is required."})
    if require_no_side_effects and side_effects:
        errors.append({"code": "full_rust_backend_cutover_side_effect_detected", "severity": "error", "path": "full_rust_backend_cutover_plan", "message": "Side effects are forbidden in this package."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "full_rust_backend_cutover_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "full_rust_backend_cutover_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Full Rust backend cutover gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (readiness_ready or not require_readiness) and shadow_age <= max_shadow_age and webui_ok and rollback_ready and operator_ok and require_fallback and not side_effects
    review = not errors and readiness_ready and webui_ok and rollback_ready and not side_effects
    status = "blocked" if errors else ("full_rust_backend_cutover_plan_ready" if ready else ("full_rust_backend_cutover_plan_review" if review else "full_rust_backend_cutover_plan_shadow_only"))
    return {
        "version": "1",
        "op": "build-full-rust-backend-cutover-plan",
        "ok": not errors,
        "result": {
            "mode": "full_rust_backend_cutover_plan",
            "status": status,
            "full_rust_backend_cutover_plan_ready": ready,
            "full_rust_backend_candidate": ready,
            "python_backend_retirement_candidate": ready,
            "python_backend_fallback_required": True,
            "webui_ux_unchanged": webui_ok,
            "rollback_path": rollback_path,
            "rollback_ready": rollback_ready,
            "operator_cutover_approval_ok": operator_ok,
            "full_rust_backend": False,
            "full_rust_backend_production_enabled": False,
            "python_backend_removed": False,
            "python_backend_removable": False,
            "python_removal_allowed": False,
            "flask_routes_disabled": False,
            "api_traffic_switched_to_rust": False,
            "rust_service_runtime_authoritative": False,
            "generated_files_written": False,
            "libreqos_apply_executed": False,
            "next_stage": "python_backend_retirement_and_rust_service_cutover_package",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_full_rust_backend_cutover_plan_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_full_rust_backend_cutover_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-full-rust-backend-cutover-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_full_rust_backend_cutover_plan(req_payload, started=started)
    return response




def _python_build_full_rust_backend_cutover_execution_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = _rust_core_config(payload)
    allow = bool(rc.get("allow_full_rust_backend_cutover_execution_contract"))
    pilot = bool(rc.get("full_rust_backend_cutover_execution_contract_pilot"))
    mode = str(rc.get("full_rust_backend_cutover_execution_mode") or "contract_only")
    require_plan = rc.get("full_rust_backend_cutover_execution_require_cutover_plan", True) is not False
    require_fallback = rc.get("full_rust_backend_cutover_execution_require_python_fallback", True) is not False
    require_confirmation = rc.get("full_rust_backend_cutover_execution_require_manual_confirmation", True) is not False
    require_webui = rc.get("full_rust_backend_cutover_execution_require_webui_unchanged", True) is not False
    require_rollback = rc.get("full_rust_backend_cutover_execution_require_rollback_path", True) is not False
    require_operator = rc.get("full_rust_backend_cutover_execution_require_operator_ack", True) is not False
    require_no_side_effects = rc.get("full_rust_backend_cutover_execution_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("full_rust_backend_cutover_execution_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_FULL_RUST_BACKEND_CUTOVER_EXECUTION_CONTRACT"
    plan = payload.get("full_rust_backend_cutover_plan") or payload.get("full_backend_cutover_plan") or {}
    if isinstance(plan, dict) and isinstance(plan.get("result"), dict):
        plan = plan.get("result") or {}
    plan_ready = isinstance(plan, dict) and plan.get("status") == "full_rust_backend_cutover_plan_ready" and plan.get("full_rust_backend_cutover_plan_ready") is True and plan.get("python_backend_removed") is False and plan.get("api_traffic_switched_to_rust") is False
    webui_ok = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True)) and (not isinstance(plan, dict) or plan.get("webui_ux_unchanged", True) is not False)
    rollback_path = str(payload.get("rollback_path") or "python_backend_reenable_and_flask_route_restore")
    rollback_ready = (not require_rollback) or bool(rollback_path.strip())
    operator_ok = (not require_operator) or bool(payload.get("operator_cutover_execution_ack")) or payload.get("operator_ack") == "FULL_RUST_BACKEND_CUTOVER_EXECUTION_REVIEWED"
    side_effects = any([payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"), payload.get("rust_service_runtime_authoritative"), payload.get("full_rust_backend_production_enabled"), payload.get("generated_files_written"), payload.get("libreqos_apply_executed"), payload.get("cleanup_authority_transferred"), payload.get("remove_python")])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "remove-python", "replace-flask", "bind-live-api", "switch", "authoritative", "production", "cutover-now", "enable"}:
        errors.append({"code": "full_rust_backend_cutover_execution_not_implemented", "severity": "error", "path": "full_rust_backend_cutover_execution_contract", "message": "Python fallback cannot execute full Rust backend cutover or remove Python."})
    if require_plan and not plan_ready:
        warnings.append({"code": "full_rust_backend_cutover_execution_plan_not_ready", "severity": "warning", "path": "full_rust_backend_cutover_plan", "message": "Full Rust backend cutover plan has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "full_rust_backend_cutover_execution_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Full Rust backend cutover execution confirmation is required."})
    if not require_fallback:
        errors.append({"code": "full_rust_backend_cutover_execution_requires_python_fallback", "severity": "error", "path": "rust_core.full_rust_backend_cutover_execution_require_python_fallback", "message": "v6.2 still requires Python backend fallback."})
    if require_webui and not webui_ok:
        warnings.append({"code": "full_rust_backend_cutover_execution_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_rollback and not rollback_ready:
        warnings.append({"code": "full_rust_backend_cutover_execution_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Python backend rollback path is required."})
    if require_operator and not operator_ok:
        warnings.append({"code": "full_rust_backend_cutover_execution_operator_ack_required", "severity": "warning", "path": "operator_cutover_execution_ack", "message": "Operator execution acknowledgment is required."})
    if require_no_side_effects and side_effects:
        errors.append({"code": "full_rust_backend_cutover_execution_side_effect_detected", "severity": "error", "path": "full_rust_backend_cutover_execution_contract", "message": "Side effects are forbidden in this package."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "full_rust_backend_cutover_execution_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "full_rust_backend_cutover_execution_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Full Rust backend cutover execution gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (plan_ready or not require_plan) and shadow_age <= max_shadow_age and webui_ok and rollback_ready and operator_ok and require_fallback and not side_effects
    review = not errors and plan_ready and webui_ok and rollback_ready and not side_effects
    status = "blocked" if errors else ("full_rust_backend_cutover_execution_contract_ready" if ready else ("full_rust_backend_cutover_execution_contract_review" if review else "full_rust_backend_cutover_execution_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-full-rust-backend-cutover-execution-contract",
        "ok": not errors,
        "result": {
            "mode": "full_rust_backend_cutover_execution_contract",
            "status": status,
            "full_rust_backend_cutover_execution_contract_ready": ready,
            "full_rust_backend_candidate": ready,
            "python_backend_retirement_candidate": ready,
            "python_backend_fallback_required": True,
            "webui_ux_unchanged": webui_ok,
            "rollback_path": rollback_path,
            "rollback_ready": rollback_ready,
            "operator_cutover_execution_ack": operator_ok,
            "full_rust_backend": False,
            "full_rust_backend_production_enabled": False,
            "python_backend_removed": False,
            "python_backend_removable": False,
            "python_removal_allowed": False,
            "flask_routes_disabled": False,
            "api_traffic_switched_to_rust": False,
            "rust_service_runtime_authoritative": False,
            "generated_files_written": False,
            "libreqos_apply_executed": False,
            "next_stage": "full_rust_backend_enablement_and_python_retirement_preflight",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_full_rust_backend_cutover_execution_contract_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_full_rust_backend_cutover_execution_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-full-rust-backend-cutover-execution-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_full_rust_backend_cutover_execution_contract(req_payload, started=started)
    return response




def _python_build_python_backend_retirement_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rc = dict(((payload.get("config") or {}).get("rust_core") or payload.get("rust_core") or {}) if isinstance(payload, dict) else {})
    allow = bool(rc.get("allow_python_backend_retirement_plan"))
    pilot = bool(rc.get("python_backend_retirement_plan_pilot"))
    mode = str(rc.get("python_backend_retirement_mode") or "plan_only")
    require_execution = rc.get("python_backend_retirement_require_cutover_execution_contract", True) is not False
    require_fallback = rc.get("python_backend_retirement_require_python_fallback", True) is not False
    require_confirmation = rc.get("python_backend_retirement_require_manual_confirmation", True) is not False
    require_webui = rc.get("python_backend_retirement_require_webui_unchanged", True) is not False
    require_rollback = rc.get("python_backend_retirement_require_rollback_path", True) is not False
    require_ack = rc.get("python_backend_retirement_require_operator_ack", True) is not False
    require_no_side_effects = rc.get("python_backend_retirement_require_no_side_effects", True) is not False
    max_shadow_age = int(rc.get("python_backend_retirement_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_PYTHON_BACKEND_RETIREMENT_PLAN"
    execution = payload.get("full_rust_backend_cutover_execution_contract") or payload.get("full_backend_cutover_execution_contract") or {}
    if isinstance(execution, dict) and isinstance(execution.get("result"), dict):
        execution = execution.get("result") or {}
    execution_ready = isinstance(execution, dict) and execution.get("status") == "full_rust_backend_cutover_execution_contract_ready" and execution.get("full_rust_backend_cutover_execution_contract_ready") is True and execution.get("python_backend_removed") is False and execution.get("api_traffic_switched_to_rust") is False
    webui_unchanged = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True))
    rollback_path = str(payload.get("rollback_path") or "restore_python_backend_and_flask_routes")
    rollback_ready = (not require_rollback) or bool(rollback_path.strip())
    operator_ack = bool(payload.get("operator_python_retirement_ack") or payload.get("operator_acknowledged"))
    side_effects = any([
        payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"),
        payload.get("rust_service_runtime_authoritative"), payload.get("full_rust_backend_production_enabled"), payload.get("remove_python"), payload.get("disable_flask"), payload.get("execute_removal"),
        isinstance(execution, dict) and execution.get("python_backend_removed"), isinstance(execution, dict) and execution.get("api_traffic_switched_to_rust"),
    ])
    gates_ready = bool(allow and pilot and mode == "plan_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "remove-python", "disable-flask", "replace-flask", "switch-api", "authoritative", "production", "cutover-now", "enable"}:
        errors.append({"code": "python_backend_retirement_execute_not_implemented", "severity": "error", "path": "python_backend_retirement_plan", "message": "Python fallback cannot remove Python or switch API traffic."})
    if require_execution and not execution_ready:
        warnings.append({"code": "python_backend_retirement_cutover_execution_not_ready", "severity": "warning", "path": "full_rust_backend_cutover_execution_contract", "message": "Full Rust backend cutover execution contract has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "python_backend_retirement_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Python backend retirement plan confirmation is required."})
    if require_webui and not webui_unchanged:
        warnings.append({"code": "python_backend_retirement_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_rollback and not rollback_ready:
        warnings.append({"code": "python_backend_retirement_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Rollback path is required."})
    if require_ack and not operator_ack:
        warnings.append({"code": "python_backend_retirement_operator_ack_required", "severity": "warning", "path": "operator_python_retirement_ack", "message": "Operator acknowledgment is required."})
    if not require_fallback:
        errors.append({"code": "python_backend_retirement_requires_python_fallback", "severity": "error", "path": "rust_core.python_backend_retirement_require_python_fallback", "message": "v6.3 still requires Python backend fallback."})
    if require_no_side_effects and side_effects:
        errors.append({"code": "python_backend_retirement_side_effect_detected", "severity": "error", "path": "python_backend_retirement_plan", "message": "Python retirement planning detected mutation side effects."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "python_backend_retirement_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "python_backend_retirement_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Python backend retirement plan gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (execution_ready or not require_execution) and webui_unchanged and rollback_ready and operator_ack and require_fallback and not side_effects and shadow_age <= max_shadow_age
    review = not errors and execution_ready and webui_unchanged and rollback_ready and not side_effects
    status = "blocked" if errors else ("python_backend_retirement_plan_ready" if ready else ("python_backend_retirement_plan_review" if review else "python_backend_retirement_plan_shadow_only"))
    return {
        "version": "1",
        "op": "build-python-backend-retirement-plan",
        "ok": not errors,
        "result": {
            "mode": "python_backend_retirement_plan",
            "status": status,
            "python_backend_retirement_plan_ready": ready,
            "full_rust_backend_candidate": ready,
            "python_backend_retirement_candidate": ready,
            "webui_ux_unchanged": webui_unchanged,
            "rollback_path": rollback_path,
            "rollback_ready": rollback_ready,
            "operator_python_retirement_ack": operator_ack,
            "cutover_execution_contract_status": execution.get("status") if isinstance(execution, dict) else None,
            "cutover_execution_contract_ready": execution_ready,
            "python_backend_fallback_required": True,
            "full_rust_backend": False,
            "full_rust_backend_production_enabled": False,
            "python_backend_removed": False,
            "python_backend_removable": False,
            "python_removal_allowed": False,
            "flask_routes_disabled": False,
            "api_traffic_switched_to_rust": False,
            "rust_service_runtime_authoritative": False,
            "generated_files_written": False,
            "libreqos_apply_executed": False,
            "next_stage": "python_backend_retirement_execution_preflight",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_backend_retirement_plan_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_python_backend_retirement_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-python-backend-retirement-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_python_backend_retirement_plan(req_payload, started=started)
    return response



def _python_build_rust_backend_production_enablement_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_rust_backend_production_enablement_contract"))
    pilot = bool(rust_core.get("rust_backend_production_enablement_contract_pilot"))
    mode = str(rust_core.get("rust_backend_production_enablement_mode") or "contract_only")
    require_retirement = rust_core.get("rust_backend_production_enablement_require_python_retirement_plan", True) is not False
    require_fallback = rust_core.get("rust_backend_production_enablement_require_python_fallback", True) is not False
    require_confirmation = rust_core.get("rust_backend_production_enablement_require_manual_confirmation", True) is not False
    require_webui = rust_core.get("rust_backend_production_enablement_require_webui_unchanged", True) is not False
    require_rollback = rust_core.get("rust_backend_production_enablement_require_rollback_path", True) is not False
    require_ack = rust_core.get("rust_backend_production_enablement_require_operator_ack", True) is not False
    require_no_side_effects = rust_core.get("rust_backend_production_enablement_require_no_side_effects", True) is not False
    max_shadow_age = int(rust_core.get("rust_backend_production_enablement_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_RUST_BACKEND_PRODUCTION_ENABLEMENT_CONTRACT"
    retirement = payload.get("python_backend_retirement_plan") or payload.get("python_retirement_plan") or {}
    if isinstance(retirement, dict) and isinstance(retirement.get("result"), dict):
        retirement = retirement.get("result") or {}
    retirement_ready = isinstance(retirement, dict) and retirement.get("status") == "python_backend_retirement_plan_ready" and retirement.get("python_backend_retirement_plan_ready") is True and retirement.get("python_backend_removed") is False and retirement.get("api_traffic_switched_to_rust") is False
    webui_unchanged = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True)) and (not isinstance(retirement, dict) or retirement.get("webui_ux_unchanged", True) is not False)
    rollback_path = str(payload.get("rollback_path") or "restore_python_backend_and_flask_routes")
    rollback_ready = (not require_rollback) or bool(rollback_path.strip())
    operator_ack = bool(payload.get("operator_rust_backend_enablement_ack") or payload.get("operator_acknowledged"))
    side_effects = any([
        payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"),
        payload.get("rust_service_runtime_authoritative"), payload.get("full_rust_backend_production_enabled"), payload.get("remove_python"), payload.get("disable_flask"), payload.get("switch_api"), payload.get("enable_rust_production"),
        isinstance(retirement, dict) and retirement.get("python_backend_removed"), isinstance(retirement, dict) and retirement.get("api_traffic_switched_to_rust"), isinstance(retirement, dict) and retirement.get("full_rust_backend_production_enabled"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "enable", "enable-production", "remove-python", "disable-flask", "replace-flask", "switch-api", "authoritative", "production", "cutover-now"}:
        errors.append({"code": "rust_backend_production_enablement_execute_not_implemented", "severity": "error", "path": "rust_backend_production_enablement_contract", "message": "Python fallback cannot enable Rust production or remove Python."})
    if require_retirement and not retirement_ready:
        warnings.append({"code": "rust_backend_production_enablement_retirement_plan_not_ready", "severity": "warning", "path": "python_backend_retirement_plan", "message": "Python backend retirement plan has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "rust_backend_production_enablement_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Rust backend production enablement confirmation is required."})
    if require_webui and not webui_unchanged:
        warnings.append({"code": "rust_backend_production_enablement_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_rollback and not rollback_ready:
        warnings.append({"code": "rust_backend_production_enablement_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Rollback path is required."})
    if require_ack and not operator_ack:
        warnings.append({"code": "rust_backend_production_enablement_operator_ack_required", "severity": "warning", "path": "operator_rust_backend_enablement_ack", "message": "Operator acknowledgment is required."})
    if not require_fallback:
        errors.append({"code": "rust_backend_production_enablement_requires_python_fallback", "severity": "error", "path": "rust_core.rust_backend_production_enablement_require_python_fallback", "message": "v6.4 still requires Python backend fallback."})
    if require_no_side_effects and side_effects:
        errors.append({"code": "rust_backend_production_enablement_side_effect_detected", "severity": "error", "path": "rust_backend_production_enablement_contract", "message": "Rust backend production enablement detected mutation side effects."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "rust_backend_production_enablement_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "rust_backend_production_enablement_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Rust backend production enablement gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (retirement_ready or not require_retirement) and webui_unchanged and rollback_ready and operator_ack and require_fallback and not side_effects and shadow_age <= max_shadow_age
    review = not errors and retirement_ready and webui_unchanged and rollback_ready and not side_effects
    status = "blocked" if errors else ("rust_backend_production_enablement_contract_ready" if ready else ("rust_backend_production_enablement_contract_review" if review else "rust_backend_production_enablement_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-rust-backend-production-enablement-contract",
        "ok": not errors,
        "result": {
            "mode": "rust_backend_production_enablement_contract",
            "status": status,
            "rust_backend_production_enablement_contract_ready": ready,
            "full_rust_backend_candidate": ready,
            "python_backend_retirement_candidate": ready,
            "python_backend_retirement_plan_status": retirement.get("status") if isinstance(retirement, dict) else None,
            "python_backend_retirement_plan_ready": retirement_ready,
            "webui_ux_unchanged": webui_unchanged,
            "rollback_path": rollback_path,
            "rollback_ready": rollback_ready,
            "operator_rust_backend_enablement_ack": operator_ack,
            "python_backend_fallback_required": True,
            "full_rust_backend": False,
            "full_rust_backend_production_enabled": False,
            "rust_backend_production_enablement_allowed": False,
            "python_backend_removed": False,
            "python_backend_removable": False,
            "python_removal_allowed": False,
            "flask_routes_disabled": False,
            "api_traffic_switched_to_rust": False,
            "rust_service_runtime_authoritative": False,
            "generated_files_written": False,
            "libreqos_apply_executed": False,
            "next_stage": "python_backend_retirement_execution_contract",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "rust_backend_production_enablement_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_rust_backend_production_enablement_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-rust-backend-production-enablement-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_rust_backend_production_enablement_contract(req_payload, started=started)
    return response




def _python_build_python_backend_removal_execution_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    rust_core = _rust_core_config(payload)
    allow = bool(rust_core.get("allow_python_backend_removal_execution_contract"))
    pilot = bool(rust_core.get("python_backend_removal_execution_contract_pilot"))
    mode = str(rust_core.get("python_backend_removal_execution_mode") or "contract_only")
    require_enablement = rust_core.get("python_backend_removal_execution_require_rust_enablement_contract", True) is not False
    require_fallback = rust_core.get("python_backend_removal_execution_require_python_fallback", True) is not False
    require_confirmation = rust_core.get("python_backend_removal_execution_require_manual_confirmation", True) is not False
    require_webui = rust_core.get("python_backend_removal_execution_require_webui_unchanged", True) is not False
    require_rollback = rust_core.get("python_backend_removal_execution_require_rollback_path", True) is not False
    require_ack = rust_core.get("python_backend_removal_execution_require_operator_ack", True) is not False
    require_no_side_effects = rust_core.get("python_backend_removal_execution_require_no_side_effects", True) is not False
    max_shadow_age = int(rust_core.get("python_backend_removal_execution_max_shadow_age_seconds") or 900)
    shadow_age = int(payload.get("shadow_age_seconds") or 0)
    confirmation_ok = (not require_confirmation) or payload.get("confirmation") == "CONFIRM_PYTHON_BACKEND_REMOVAL_EXECUTION_CONTRACT"
    enablement = payload.get("rust_backend_production_enablement_contract") or payload.get("rust_backend_enablement_contract") or {}
    if isinstance(enablement, dict) and isinstance(enablement.get("result"), dict):
        enablement = enablement.get("result") or {}
    enablement_ready = isinstance(enablement, dict) and enablement.get("status") == "rust_backend_production_enablement_contract_ready" and enablement.get("rust_backend_production_enablement_contract_ready") is True and enablement.get("full_rust_backend_candidate") is True and enablement.get("python_backend_removed") is False and enablement.get("api_traffic_switched_to_rust") is False
    webui_unchanged = bool(payload.get("webui_ux_unchanged", True)) and bool(payload.get("webui_static_asset_paths_unchanged", True)) and (not isinstance(enablement, dict) or enablement.get("webui_ux_unchanged", True) is not False)
    rollback_path = str(payload.get("rollback_path") or "restore_python_backend_and_flask_routes")
    rollback_ready = (not require_rollback) or bool(rollback_path.strip())
    operator_ack = bool(payload.get("operator_python_backend_removal_execution_ack") or payload.get("operator_acknowledged"))
    side_effects = any([
        payload.get("python_backend_removed"), payload.get("flask_routes_disabled"), payload.get("api_traffic_switched_to_rust"),
        payload.get("rust_service_runtime_authoritative"), payload.get("full_rust_backend_production_enabled"), payload.get("remove_python"), payload.get("disable_flask"), payload.get("switch_api"), payload.get("execute_removal"),
        isinstance(enablement, dict) and enablement.get("python_backend_removed"), isinstance(enablement, dict) and enablement.get("api_traffic_switched_to_rust"), isinstance(enablement, dict) and enablement.get("full_rust_backend_production_enabled"), isinstance(enablement, dict) and enablement.get("rust_backend_production_enablement_allowed"),
    ])
    gates_ready = bool(allow and pilot and mode == "contract_only")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"execute", "remove-python", "disable-flask", "replace-flask", "switch-api", "authoritative", "production", "cutover-now", "delete-python"}:
        errors.append({"code": "python_backend_removal_execution_not_implemented", "severity": "error", "path": "python_backend_removal_execution_contract", "message": "Python fallback cannot remove Python, disable Flask, or switch API traffic."})
    if require_enablement and not enablement_ready:
        warnings.append({"code": "python_backend_removal_execution_enablement_not_ready", "severity": "warning", "path": "rust_backend_production_enablement_contract", "message": "Rust backend production enablement contract has not passed."})
    if require_confirmation and not confirmation_ok:
        warnings.append({"code": "python_backend_removal_execution_confirmation_required", "severity": "warning", "path": "confirmation", "message": "Python backend removal execution confirmation is required."})
    if require_webui and not webui_unchanged:
        warnings.append({"code": "python_backend_removal_execution_webui_changed", "severity": "warning", "path": "webui_ux_unchanged", "message": "WebUI/UX must remain unchanged."})
    if require_rollback and not rollback_ready:
        warnings.append({"code": "python_backend_removal_execution_rollback_path_required", "severity": "warning", "path": "rollback_path", "message": "Rollback path is required."})
    if require_ack and not operator_ack:
        warnings.append({"code": "python_backend_removal_execution_operator_ack_required", "severity": "warning", "path": "operator_python_backend_removal_execution_ack", "message": "Operator acknowledgment is required."})
    if not require_fallback:
        errors.append({"code": "python_backend_removal_execution_requires_python_fallback", "severity": "error", "path": "rust_core.python_backend_removal_execution_require_python_fallback", "message": "v6.5 still requires Python backend fallback."})
    if require_no_side_effects and side_effects:
        errors.append({"code": "python_backend_removal_execution_side_effect_detected", "severity": "error", "path": "python_backend_removal_execution_contract", "message": "Python backend removal execution detected mutation side effects."})
    if shadow_age > max_shadow_age:
        warnings.append({"code": "python_backend_removal_execution_shadow_stale", "severity": "warning", "path": "shadow_age_seconds", "message": "Rust-shadow data is stale."})
    if not gates_ready:
        warnings.append({"code": "python_backend_removal_execution_gates_not_enabled", "severity": "warning", "path": "rust_core", "message": "Python backend removal execution gates are not fully enabled."})
    ready = not errors and gates_ready and confirmation_ok and (enablement_ready or not require_enablement) and webui_unchanged and rollback_ready and operator_ack and require_fallback and not side_effects and shadow_age <= max_shadow_age
    review = not errors and enablement_ready and webui_unchanged and rollback_ready and not side_effects
    status = "blocked" if errors else ("python_backend_removal_execution_contract_ready" if ready else ("python_backend_removal_execution_contract_review" if review else "python_backend_removal_execution_contract_shadow_only"))
    return {
        "version": "1",
        "op": "build-python-backend-removal-execution-contract",
        "ok": not errors,
        "result": {
            "mode": "python_backend_removal_execution_contract",
            "status": status,
            "python_backend_removal_execution_contract_ready": ready,
            "full_rust_backend_candidate": ready,
            "python_backend_retirement_candidate": ready,
            "python_backend_removal_candidate": ready,
            "rust_backend_production_enablement_status": enablement.get("status") if isinstance(enablement, dict) else None,
            "rust_backend_production_enablement_ready": enablement_ready,
            "webui_ux_unchanged": webui_unchanged,
            "rollback_path": rollback_path,
            "rollback_ready": rollback_ready,
            "operator_python_backend_removal_execution_ack": operator_ack,
            "python_backend_fallback_required": True,
            "full_rust_backend": False,
            "full_rust_backend_production_enabled": False,
            "rust_backend_production_enablement_allowed": False,
            "python_backend_removed": False,
            "python_backend_removable": False,
            "python_removal_allowed": False,
            "python_removal_executed": False,
            "flask_routes_disabled": False,
            "api_traffic_switched_to_rust": False,
            "rust_service_runtime_authoritative": False,
            "generated_files_written": False,
            "libreqos_apply_executed": False,
            "next_stage": "full_rust_backend_removal_rehearsal",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_backend_removal_execution_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_python_backend_removal_execution_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-python-backend-removal-execution-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_python_backend_removal_execution_contract(req_payload, started=started)
    return response

def rust_validate_routeros_read_results(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    response = call_rust_core("validate-routeros-read-results", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_validate_routeros_read_results(req_payload, started=started)
    return response

def rust_build_collector_circuit_bundle(config: dict, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a shadow ShapedDevices-compatible circuit bundle from raw collector snapshots.

    This is a bridge toward Rust collector/circuit migration. Python collectors remain
    authoritative; the Rust result is diagnostic unless explicitly used by future
    authority stages.
    """
    return call_rust_core("build-collector-circuit-bundle", payload or {}, config=config)



def _python_compare_collector_bundle_parity(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()

    def _rows(value):
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
        if isinstance(value, dict):
            return [r for r in value.values() if isinstance(r, dict)]
        return []

    def _rust_rows(payload):
        rows = _rows(payload.get("rust_rows")) or _rows(payload.get("normalized_rows"))
        if rows:
            return rows
        bundle = payload.get("rust_bundle") if isinstance(payload.get("rust_bundle"), dict) else {}
        result = bundle.get("result") if isinstance(bundle.get("result"), dict) else bundle
        return _rows(result.get("normalized_rows"))

    def _key(row):
        for field in ("Circuit Name", "Circuit ID", "Device ID", "Device Name"):
            value = str(row.get(field) or "").strip()
            if value:
                return value
        return ""

    fields = payload.get("compare_fields") if isinstance(payload.get("compare_fields"), list) else None
    fields = [str(f) for f in fields if str(f).strip()] if fields else ["Parent Node", "MAC", "IPv4", "Download Min Mbps", "Upload Min Mbps", "Download Max Mbps", "Upload Max Mbps", "Comment"]
    python_rows = _rows(payload.get("python_rows"))
    rust_rows = _rust_rows(payload)
    py = {_key(r): r for r in python_rows if _key(r)}
    rs = {_key(r): r for r in rust_rows if _key(r)}
    missing = sorted(set(py) - set(rs))
    extra = sorted(set(rs) - set(py))
    mismatches = []
    mismatch_count = 0
    max_mismatches = int(payload.get("max_mismatches") or 50)
    for key in sorted(set(py) & set(rs)):
        for field in fields:
            pv = str(py[key].get(field) or "").strip()
            rv = str(rs[key].get(field) or "").strip()
            if pv != rv:
                mismatch_count += 1
                if len(mismatches) < max_mismatches:
                    mismatches.append({"circuit": key, "field": field, "python": pv, "rust": rv})
    total_key_checks = len(set(py) | set(rs))
    total_checks = total_key_checks + (len(set(py) & set(rs)) * len(fields))
    failed = len(missing) + len(extra) + mismatch_count
    score = 100.0 if total_checks <= 0 else round(((total_checks - failed) / total_checks) * 100.0, 2)
    verdict = "parity_pass" if failed == 0 else ("parity_warning" if score >= float(payload.get("warning_threshold_percent") or 95.0) else "parity_failed")
    warnings = [] if failed == 0 else [{"code": "collector_bundle_parity_mismatch", "severity": "warning", "path": "collector_bundle_parity", "message": f"Python authoritative rows and Rust shadow rows differ: score={score}%."}]
    strict = bool(payload.get("strict"))
    errors = []
    if strict and verdict == "parity_failed":
        errors.append({"code": "collector_bundle_parity_failed", "severity": "error", "path": "collector_bundle_parity", "message": "Strict collector bundle parity failed."})
    return {
        "version": PROTOCOL_VERSION,
        "op": "compare-collector-bundle-parity",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "collector_bundle_parity_shadow",
            "verdict": verdict,
            "exact_match": failed == 0,
            "parity_score": score,
            "python_count": len(py),
            "rust_count": len(rs),
            "matched_count": len(set(py) & set(rs)),
            "missing_in_rust_count": len(missing),
            "extra_in_rust_count": len(extra),
            "field_mismatch_count": mismatch_count,
            "mismatch_sample_count": len(mismatches),
            "missing_in_rust": missing,
            "extra_in_rust": extra,
            "field_mismatches": mismatches,
            "compare_fields": fields,
            "authority_note": "Python collector/builders remain authoritative. This fallback parity report is diagnostic.",
        },
        "errors": errors,
        "warnings": warnings,
        "meta": {"engine": "python-wrapper", "mode": "python_collector_parity_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_compare_collector_bundle_parity(config: dict, payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = call_rust_core("compare-collector-bundle-parity", payload or {}, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_compare_collector_bundle_parity(payload or {}, started=started)
    return response


def _python_build_routeros_auth_plan(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    router = payload.get("router") if isinstance(payload.get("router"), dict) else {}
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    routers = cfg.get("routers") if isinstance(cfg.get("routers"), list) else []
    if not router and routers:
        requested = str(payload.get("router") or "")
        for item in routers:
            if isinstance(item, dict) and item.get("enabled", True) and (not requested or str(item.get("name") or "") == requested):
                router = item
                break
    username_present = bool(str(payload.get("username") or router.get("username") or "").strip())
    password_present = bool(str(payload.get("password") or router.get("password") or ""))
    address_present = bool(str(payload.get("address") or router.get("address") or "").strip())
    errors = []
    if not address_present:
        errors.append({"code": "routeros_auth_address_missing", "severity": "error", "path": "router.address", "message": "RouterOS authentication plan requires a router address."})
    if not username_present:
        errors.append({"code": "routeros_auth_username_missing", "severity": "error", "path": "router.username", "message": "RouterOS authentication plan requires a username."})
    if not password_present:
        errors.append({"code": "routeros_auth_password_missing", "severity": "error", "path": "router.password", "message": "RouterOS authentication plan requires password material, but the value is never emitted."})
    execute = bool(payload.get("execute")) or str(payload.get("mode") or "").lower() in {"auth", "live", "execute"}
    if execute:
        errors.append({"code": "routeros_auth_adapter_not_implemented", "severity": "error", "path": "routeros_auth_plan", "message": "Python fallback does not execute Rust RouterOS authentication."})
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-routeros-auth-plan",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "auth_pilot" if execute else "auth_plan",
            "status": "blocked" if errors else "auth_plan_ready",
            "router": str(router.get("name") or payload.get("router") or "unknown"),
            "address_redacted": "configured" if address_present else "missing",
            "port": int(payload.get("port") or router.get("port") or 8728),
            "username_present": username_present,
            "password_present": password_present,
            "credential_material": "redacted",
            "password_emitted": False,
            "login_sentence_emitted": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "live_auth_supported": False,
            "full_rust_backend": False,
            "authority_note": "Python fallback only builds a redacted auth plan. It never authenticates."
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_auth_plan_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_routeros_auth_plan(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-routeros-auth-plan", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_auth_plan(req_payload, started=started)
    return response


def _python_run_routeros_auth_handshake(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for the v3.1 RouterOS auth handshake fixture.

    This never opens sockets and never emits credential material. It only
    simulates the future auth state machine using fixture reply words.
    """
    started = started or time.perf_counter()
    plan = _python_build_routeros_auth_plan({**(payload or {}), "execute": False}, started=started)
    errors = list(plan.get("errors") or [])
    adapter = str((payload or {}).get("adapter") or "fixture")
    live_requested = adapter in {"live", "tcp", "routeros"} or str((payload or {}).get("mode") or "").lower() in {"live", "auth", "execute_live"}
    if live_requested:
        errors.append({"code": "routeros_auth_handshake_live_adapter_not_implemented", "severity": "error", "path": "adapter", "message": "RouterOS auth handshake fallback is fixture-only and cannot authenticate live."})
    words = (payload or {}).get("fixture_reply_words") or (payload or {}).get("reply_words") or ["!done"]
    trap_count = sum(1 for w in words if str(w).strip() in {"!trap", "!fatal"}) if isinstance(words, list) else 0
    done_count = sum(1 for w in words if str(w).strip() == "!done") if isinstance(words, list) else 0
    if errors:
        status = "blocked"
    elif trap_count:
        status = "auth_fixture_rejected"
    elif done_count:
        status = "auth_fixture_accepted"
    else:
        status = "auth_fixture_incomplete"
    return {
        "version": PROTOCOL_VERSION,
        "op": "run-routeros-auth-handshake",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "routeros_auth_handshake_fixture",
            "status": status,
            "adapter": adapter,
            "fixture_executed": not live_requested,
            "credential_material": "redacted",
            "username_emitted": False,
            "password_emitted": False,
            "login_sentence_emitted": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "fixture_handshake_count": 0 if live_requested else 1,
            "reply_done_count": done_count,
            "reply_trap_count": trap_count,
            "live_auth_supported": False,
            "full_rust_backend": False,
            "authority_note": "Python fallback only simulates RouterOS auth handshake fixtures. It never authenticates."
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_auth_handshake_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_run_routeros_auth_handshake(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("run-routeros-auth-handshake", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_run_routeros_auth_handshake(req_payload, started=started)
    return response



def _python_build_routeros_auth_session_contract(payload: dict[str, Any], *, started: float | None = None) -> dict[str, Any]:
    """Fallback for the v3.2 RouterOS authenticated-session contract.

    This never opens sockets, authenticates, emits credentials, or persists tokens.
    """
    started = started or time.perf_counter()
    hs = _python_run_routeros_auth_handshake({**(payload or {}), "execute": bool((payload or {}).get("execute", False))}, started=started)
    errors = list(hs.get("errors") or [])
    result_hs = hs.get("result") or {}
    authenticated = not errors and result_hs.get("status") == "auth_fixture_accepted"
    adapter = str((payload or {}).get("adapter") or "fixture")
    router = (payload or {}).get("router") or {}
    router_name = router.get("name") if isinstance(router, dict) else ((payload or {}).get("router") or "unknown")
    address = router.get("address") if isinstance(router, dict) else (payload or {}).get("address")
    if adapter in {"live", "tcp", "routeros"}:
        errors.append({"code": "routeros_auth_session_live_adapter_not_implemented", "severity": "error", "path": "adapter", "message": "RouterOS auth session fallback is fixture-only and cannot create live sessions."})
    import hashlib
    sid = "ros-session-" + hashlib.sha256(f"{router_name}|{address or ''}|{result_hs.get('status')}".encode()).hexdigest()[:16]
    status = "blocked" if errors else ("auth_session_contract_ready" if authenticated else "auth_session_not_established")
    return {
        "version": PROTOCOL_VERSION,
        "op": "build-routeros-auth-session-contract",
        "available": False,
        "ok": not errors,
        "result": {
            "mode": "routeros_auth_session_contract",
            "status": status,
            "adapter": adapter,
            "router": router_name or "unknown",
            "router_address_present": bool(address),
            "session_id": sid,
            "session_state": "authenticated_fixture" if authenticated else "not_authenticated",
            "authenticated": authenticated,
            "auth_status": result_hs.get("status"),
            "auth_handshake": result_hs,
            "credential_material": "redacted",
            "username_emitted": False,
            "password_emitted": False,
            "session_token_emitted": False,
            "connection_attempt_count": 0,
            "authentication_attempt_count": 0,
            "api_sentence_write_count": 0,
            "api_reply_read_count": 0,
            "live_session_supported": False,
            "full_rust_backend": False,
            "authority_note": "Python fallback only builds redacted auth session contracts from fixtures. It never authenticates."
        },
        "errors": errors,
        "warnings": [],
        "meta": {"engine": "python-wrapper", "mode": "python_routeros_auth_session_contract_fallback", "duration_ms": round((time.perf_counter() - started) * 1000, 3)},
    }


def rust_build_routeros_auth_session_contract(config: dict, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    req_payload = dict(payload or {})
    req_payload.setdefault("config", config)
    response = call_rust_core("build-routeros-auth-session-contract", req_payload, config=config)
    error_codes = {str(e.get("code")) for e in (response.get("errors") or []) if isinstance(e, dict)}
    if response.get("skipped") or not response.get("available", True) or "unknown_operation" in error_codes:
        return _python_build_routeros_auth_session_contract(req_payload, started=started)
    return response
