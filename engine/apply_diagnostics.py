"""LibreQoS apply diagnostics and resolution helpers.

This module is read-only. It turns a saved LibreQoS apply run into an
operator-facing diagnostic: what failed, where to see the logs, and which UI page
or command is the next best place to resolve the problem.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from monitoring.service_monitor import list_apply_runs, read_apply_file


def _first_nonempty_line(text: str, limit: int = 500) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return ""


def _tail(text: str, lines: int = 80, chars: int = 12000) -> str:
    raw = text or ""
    if len(raw) > chars:
        raw = raw[-chars:]
    parts = raw.splitlines()
    if len(parts) > lines:
        parts = parts[-lines:]
    return "\n".join(parts)


def _find_run(config: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    for run in list_apply_runs(config, limit=500):
        if str(run.get("run_id") or "") == str(run_id):
            return run
    return None


def _classify(stderr: str, stdout: str, meta: dict[str, Any]) -> dict[str, Any]:
    text = f"{stderr}\n{stdout}\n{meta.get('error') or ''}".lower()
    if "invalid libreqos.working_dir" in text or "working_dir" in text and "not found" in text:
        return {
            "category": "invalid_working_dir",
            "summary": "LibreQoS working_dir is invalid or not accessible.",
            "resolution": "Open Setup / System Validation and Config Center paths. Set libreqos.working_dir to the directory that contains LibreQoS.py, usually /opt/libreqos/src.",
            "target": "/setup-repair",
            "commands": [
                "cd /opt/LQoSync",
                "python3 scripts/doctor.py --config /opt/libreqos/src/config.json",
                "ls -lah /opt/libreqos/src/LibreQoS.py /opt/libreqos/src/ShapedDevices.csv",
            ],
        }
    if "nsenter" in text or "cannot open /proc/1/ns" in text:
        return {
            "category": "nsenter_mode_mismatch",
            "summary": "LibreQoS apply is trying to use nsenter/host namespace mode but the install appears to be bare-metal or lacks permissions.",
            "resolution": "Use direct/bare-metal run mode or set LQOSYNC_INSTALL_MODE=baremetal / LQOSYNC_FORCE_DIRECT=true, then retry apply.",
            "target": "/setup-repair",
            "commands": [
                "cd /opt/LQoSync",
                "sudo systemctl edit lqosync",
                "# add Environment=LQOSYNC_INSTALL_MODE=baremetal if needed",
                "sudo systemctl daemon-reload && sudo systemctl restart lqosync",
            ],
        }
    if "permission denied" in text:
        return {
            "category": "permission_denied",
            "summary": "LibreQoS apply hit a permission denied error.",
            "resolution": "Restore LibreQoS/LQoSync file permissions and verify the service user can read/write generated files and execute LibreQoS.py.",
            "target": "/setup-repair",
            "commands": [
                "cd /opt/LQoSync",
                "sudo bash scripts/restore_libreqos_permissions.sh",
                "sudo systemctl restart lqosync",
            ],
        }
    if "no such file" in text or "filenotfounderror" in text or "not found" in text:
        return {
            "category": "missing_file_or_command",
            "summary": "LibreQoS apply could not find a required file or command.",
            "resolution": "Verify libreqos.cmd, libreqos.working_dir, ShapedDevices.csv, network.json, and Python path settings.",
            "target": "/config?tab=paths",
            "commands": [
                "cd /opt/LQoSync",
                "python3 scripts/doctor.py --config /opt/libreqos/src/config.json",
                "ls -lah /opt/libreqos/src/LibreQoS.py /opt/libreqos/src/ShapedDevices.csv /opt/libreqos/src/network.json",
            ],
        }
    if "timed out" in text or meta.get("timed_out"):
        return {
            "category": "timeout",
            "summary": "LibreQoS apply timed out.",
            "resolution": "Inspect LibreQoS service health and increase libreqos.timeout_seconds only after confirming LibreQoS is not stuck.",
            "target": "/operations?tab=services",
            "commands": [
                "systemctl status lqosd lqos_scheduler --no-pager",
                "journalctl -u lqosd -n 100 --no-pager",
                "journalctl -u lqos_scheduler -n 100 --no-pager",
            ],
        }
    if "traceback" in text or "exception" in text:
        return {
            "category": "libreqos_exception",
            "summary": "LibreQoS.py raised an exception during apply.",
            "resolution": "Open stderr, inspect the traceback, validate generated files, then run LibreQoS.py manually from /opt/libreqos/src if needed.",
            "target": "/operations?tab=apply",
            "commands": [
                "cd /opt/libreqos/src",
                "sudo python3 LibreQoS.py --updateonly",
            ],
        }
    return {
        "category": "unknown_apply_failure",
        "summary": _first_nonempty_line(stderr) or _first_nonempty_line(stdout) or "LibreQoS apply failed; inspect stdout/stderr for details.",
        "resolution": "Open the apply detail page, inspect stderr/stdout, validate paths and generated files, then retry apply after the root cause is fixed.",
        "target": "/operations?tab=apply",
        "commands": [
            "cd /opt/LQoSync",
            "python3 scripts/release_check.py",
            "python3 scripts/policy_path_audit.py",
            "cd /opt/libreqos/src && sudo python3 LibreQoS.py --updateonly",
        ],
    }


def get_apply_diagnostic(config: dict[str, Any], run_id: str) -> dict[str, Any]:
    run = _find_run(config, run_id) or {"run_id": run_id, "ok": False, "missing_meta": True}
    stdout = read_apply_file(config, run_id, "stdout")
    stderr = read_apply_file(config, run_id, "stderr")
    classification = _classify(stderr, stdout, run)
    detail_target = f"/libreqos/apply/{run_id}" if run_id else "/operations?tab=apply"
    return {
        "run": run,
        "run_id": run_id,
        "ok": bool(run.get("ok")),
        "exit_code": run.get("exit_code"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "duration_seconds": run.get("duration_seconds"),
        "working_dir": run.get("working_dir"),
        "mode": run.get("mode"),
        "command": run.get("command") or [],
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "stderr_first_line": _first_nonempty_line(stderr),
        "stdout_first_line": _first_nonempty_line(stdout),
        "has_stdout": bool(stdout.strip()),
        "has_stderr": bool(stderr.strip()),
        "detail_target": detail_target,
        **classification,
    }


def latest_failed_apply_diagnostic(config: dict[str, Any]) -> dict[str, Any] | None:
    for run in list_apply_runs(config, limit=50):
        if run.get("ok") is False and run.get("run_id"):
            return get_apply_diagnostic(config, str(run.get("run_id")))
    return None
