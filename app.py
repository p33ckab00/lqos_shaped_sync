import json
import os
import secrets
import subprocess
import io
import zipfile
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort
from dotenv import load_dotenv

from auth.users import (
    authenticate, ensure_users_file, list_users, add_user, update_user,
    set_user_password, delete_user, role_at_least, role_options, ROLE_DEFINITIONS
)
from engine.config_loader import load_config, save_config, validate_config
from engine.run_cycle import run_cycle
from engine.state import load_state, update_state
from scheduler.runner import LQoSyncScheduler
from builders.shaped_devices import read_shaped_devices_csv, render_shaped_devices_csv
from builders.network_json import read_network_json, render_network_json, flatten_nodes
from applier.backup import list_backups, delete_backup, inspect_backup, compare_backup_to_live, retention_preview
from applier.libreqos_runner import run_libreqos_update
from applier.rollback import restore_backup
from collectors.mikrotik_client import test_router_connection, connect_to_router, get_resource_data
from engine.audit import write_audit, tail_audit
from engine.policy_state import load_policy_state, save_policy_state, confirm_cleanup, dismiss_confirmation
from engine.setup_repair import compute_setup_repair_report, apply_policy_preset
from engine.setup_wizard import compute_setup_wizard, NETWORK_MODE_OPTIONS, is_setup_wizard_complete
from engine.policy_schema import grouped_policy_schema, policy_diff_from_preset, closest_preset, parse_policy_form, normalize_policies, reconcile_policy_mode, policy_context_changed, POLICY_SCHEMA, get_by_path
from engine.policy_conflicts import evaluate_policy_conflicts, enhanced_preset_comparison, client_identity_report
from engine.health_trends import compute_health_report
from engine.production_readiness import compute_production_readiness
from engine.apply_diagnostics import get_apply_diagnostic
from engine.stable_release import compute_stable_release_check
from engine.router_overview import compute_router_overview
from engine.notifications import telegram_settings_summary, send_test_message, dispatch_telegram_notifications
from engine.docs_search import search_docs, build_docs_index, get_doc
from engine.config_simulator import simulate_config_change
from engine.reports import compute_operator_report, report_to_csv, report_to_markdown
from engine.config_schema import migrate_config_schema, validate_schema, CONFIG_SCHEMA_VERSION
from engine.release_integrity import compute_release_integrity, repair_config_defaults
from engine.lifecycle import lifecycle_summary, client_event_timeline
from engine.lifecycle_report import compute_lifecycle_report, lifecycle_report_to_csv, lifecycle_report_to_markdown
from engine.rust_core import (
    rust_build_routeros_collector_plan,
    rust_build_routeros_transport_session,
    rust_build_routeros_live_read_pilot,
    rust_run_routeros_read_pilot,
    rust_build_routeros_api_sentence,
    rust_decode_routeros_api_reply,
    rust_codec_routeros_api_frame,
    rust_run_routeros_offline_session,
    rust_run_routeros_tcp_connectivity_pilot,
    rust_build_routeros_auth_plan,
    rust_run_routeros_auth_handshake,
    rust_build_routeros_auth_session_contract,
    rust_run_routeros_authenticated_read_fixture,
    rust_run_routeros_live_read_adapter_pilot,
    rust_evaluate_collector_authority_pilot,
    rust_build_collector_authority_manifest,
    rust_build_collector_authority_selection,
    rust_build_collector_authority_dry_run_bundle,
    rust_build_run_cycle_rust_shadow_report,
    rust_build_collector_authority_activation_plan,
    rust_build_collector_authority_runtime_contract,
    rust_build_collector_authority_switch_rehearsal,
    rust_build_collector_authority_pilot_execution_contract,
    rust_evaluate_collector_authority_pilot_result,
    rust_build_collector_authority_promotion_readiness,
    rust_build_collector_authority_promotion_execution_rehearsal,
    rust_build_collector_authority_promotion_commit_plan,
    rust_build_collector_authority_promotion_cutover_ledger,
    rust_build_collector_authority_production_freeze_gate,
    rust_build_collector_authority_production_switch_contract,
    rust_build_rust_backend_api_handoff_plan,
    rust_validate_routeros_read_results,
    rust_build_collector_circuit_bundle,
    rust_compare_collector_bundle_parity,
    rust_core_status,
    rust_core_self_test,
    rust_read_transaction_journal,
    rust_build_rollback_from_journal,
    rust_execute_rollback,
    rust_authority_readiness,
    rust_full_backend_readiness,
    rust_authority_pilot_plan,
)
from applier.atomic_writer import atomic_write_text
from monitoring.service_monitor import (
    all_service_status, service_status, restart_service as monitor_restart_service,
    restart_group, journal_lines, allowed_units, allowed_groups, list_apply_runs, read_apply_file,
)

load_dotenv()
CONFIG_PATH = os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
USERS_PATH = os.getenv("USERS_PATH") or "users.json"
ensure_users_file(USERS_PATH)


def _startup_config_normalize():
    """Persist missing safe defaults into config.json at process startup.

    This is intentionally conservative: it deep-merges defaults, forces valid
    network mode flags, ensures libreqos.working_dir and failed-apply retry are
    present, and prevents Docker-only host_nsenter from surviving on bare metal.
    It closes the gap where an operator updates by git pull + service restart
    without re-running install.sh.
    """
    try:
        cfg = load_config(CONFIG_PATH)
        save_config(cfg, CONFIG_PATH, backup_existing=True)
    except Exception as exc:
        # Do not prevent the UI from booting. The dashboard/config page will show
        # the real config state and logs will surface the startup migration error.
        print(f"[LQoSync] WARNING: startup config normalization failed: {exc}")


_startup_config_normalize()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev-change-me"
scheduler = LQoSyncScheduler(CONFIG_PATH)
scheduler.start()


# =========================
# Auth/session helpers
# =========================
def current_user():
    """Return the currently logged-in user dict, or None."""
    user = session.get("user")
    return user if isinstance(user, dict) else None


def login_required(view_func):
    """Decorator for pages/API routes that require a logged-in user."""
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "login_required"}), 401
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def _require_min_role(min_role: str, error_name: str):
    """Build a route decorator for role-based access control.

    Role hierarchy: owner > admin > operator > viewer.
    Older installs with only an admin account are normalized to owner by
    auth.users.load_users(), so owner-only routes remain reachable after upgrade.
    """
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "login_required"}), 401
                return redirect(url_for("login", next=request.path))
            if not role_at_least(user.get("role", "viewer"), min_role):
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": error_name, "required_role": min_role, "role": user.get("role", "viewer")}), 403
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def owner_required(view_func):
    """Decorator for owner-only actions: users, updates, and high-trust repair controls."""
    return _require_min_role("owner", "owner_required")(view_func)


def admin_required(view_func):
    """Decorator for config, policy, scheduler, backup, and live action routes."""
    return _require_min_role("admin", "admin_required")(view_func)


def operator_required(view_func):
    """Decorator for routes/actions available to operators and above."""
    return _require_min_role("operator", "operator_required")(view_func)


def _csrf_token():
    """Return/create per-session CSRF token."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _csrf_field():
    return f'<input type="hidden" name="csrf_token" value="{_csrf_token()}">'


@app.before_request
def _csrf_protect():
    """Protect write requests. Accept token from form, JSON, or X-CSRFToken header."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    # Login must be allowed to create a session, but still set token later.
    if request.endpoint in ("login", "healthz"):
        return None
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not supplied:
        supplied = request.form.get("csrf_token")
    if not supplied and request.is_json:
        try:
            payload = request.get_json(silent=True) or {}
            supplied = payload.get("csrf_token")
        except Exception:
            supplied = None
    if not expected or not supplied or not secrets.compare_digest(str(expected), str(supplied)):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "csrf_failed"}), 400
        abort(400)
    return None




def get_status():
    """Load current config and runtime state for pages/API routes.

    This helper is intentionally small and side-effect safe: config.json is the
    persistent settings source, while runtime_state.json holds live scheduler and
    last-run status. The dashboard and API routes call this instead of accessing
    state paths directly.
    """
    cfg = load_config(CONFIG_PATH)
    state_path = cfg.get("paths", {}).get("runtime_state", "state/runtime_state.json")
    state = load_state(state_path)
    try:
        state["scheduler_enabled"] = bool(cfg.get("scheduler", {}).get("enabled", False))
        state["sync_lock_running"] = bool(scheduler.is_running())
    except Exception:
        pass
    return cfg, state


def _compute_setup_wizard_status(cfg=None, state=None):
    """Compute Setup Wizard status for dashboard banners and production gates."""
    try:
        if cfg is None or state is None:
            cfg, state = get_status()
        errors, warnings = validate_config(cfg)
        services = all_service_status(cfg)
        setup_report = compute_setup_repair_report(
            cfg,
            state,
            git_status=_git_status(fetch_remote=False),
            services=services,
            config_errors=errors,
            config_warnings=warnings,
        )
        return compute_setup_wizard(cfg, state, setup_report)
    except Exception as exc:
        return {
            "readiness": "unknown",
            "production_ready": False,
            "setup_complete": False,
            "first_run_completed": False,
            "dashboard_banner": True,
            "go_live_blockers": [f"setup wizard status failed: {exc}"],
            "next_action": "Open Setup & Repair and run Environment Doctor.",
            "progress": 0,
        }


def _setup_wizard_allows_scheduler_enable(cfg, state=None):
    wizard_cfg = cfg.get("setup_wizard") or {}
    if not wizard_cfg.get("enabled", True):
        return True, [], {}
    wizard = _compute_setup_wizard_status(cfg, state)
    if wizard.get("production_ready") or wizard_cfg.get("allow_force_scheduler_enable", False):
        return True, wizard.get("go_live_blockers", []), wizard
    return False, wizard.get("go_live_blockers", []), wizard


@app.before_request
def _setup_wizard_first_run_redirect():
    """On fresh installs, guide admins to the Setup Wizard until acknowledged.

    This does not block Config Center, Policy Center, Setup & Repair, docs, API
    health checks, or static assets because those pages are needed to complete
    setup. It only keeps the operator landing flow from silently entering the
    normal dashboard before first-run readiness has been reviewed.
    """
    user = current_user()
    if not user or user.get("role") != "admin":
        return None
    if request.method != "GET":
        return None
    allowed_prefixes = (
        "/setup-wizard", "/setup-repair", "/config", "/policy", "/network",
        "/docs", "/about", "/updates", "/services", "/logout", "/static", "/api", "/healthz"
    )
    if request.path.startswith(allowed_prefixes):
        return None
    try:
        cfg, state = get_status()
        wc = cfg.get("setup_wizard") or {}
        if not wc.get("enabled", True) or not wc.get("redirect_after_login_until_complete", True):
            return None
        wizard = _compute_setup_wizard_status(cfg, state)
        if wizard.get("enforce_redirect") and not wizard.get("setup_complete"):
            return redirect(url_for("setup_wizard_center"))
    except Exception:
        return None
    return None


def _manual_sync_blocked(cfg):
    """Disable manual Run Sync Now when scheduler auto-apply is active.

    In live production mode, scheduler.enabled + app.auto_apply means the
    scheduled loop is already responsible for writing file changes and applying
    LibreQoS immediately. This prevents accidental double-runs from the UI.
    """
    return bool(cfg.get("scheduler", {}).get("enabled", False)) and bool(cfg.get("app", {}).get("auto_apply", True))




def _git_status(fetch_remote: bool = False):
    """Return lightweight Git/update status for the installed app code.

    This is read-only and safe for dashboard display. The Update Center can ask
    for ``fetch_remote=True`` so origin/main is refreshed before comparing local
    and remote commits. Dashboard/status polling uses the local cached refs to
    avoid network waits on every refresh.
    """
    root = Path(__file__).resolve().parent
    version_path = root / "VERSION"
    data = {
        "path": str(root),
        "git_managed": (root / ".git").exists(),
        "branch": "unknown",
        "commit": "unknown",
        "short_commit": "unknown",
        "remote_commit": "unknown",
        "remote_short_commit": "unknown",
        "remote": "unknown",
        "upstream": "unknown",
        "relation": "unknown",
        "ahead": "?",
        "behind": "?",
        "dirty": False,
        "fetch_attempted": bool(fetch_remote),
        "fetch_ok": False,
        "fetch_error": None,
        "local_version": version_path.read_text(encoding="utf-8", errors="ignore").strip() if version_path.exists() else "unknown",
        "remote_version": "unknown",
        "version_relation": "unknown",
        "error": None,
    }
    if not data["git_managed"]:
        data["relation"] = "not_git_managed"
        return data

    def run_git(args, timeout=10):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=timeout)

    try:
        res = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if res.returncode == 0:
            data["branch"] = res.stdout.strip() or "unknown"
        res = run_git(["rev-parse", "HEAD"])
        if res.returncode == 0:
            data["commit"] = res.stdout.strip()
            data["short_commit"] = data["commit"][:7]
        res = run_git(["remote", "get-url", "origin"])
        if res.returncode == 0:
            data["remote"] = res.stdout.strip() or "unknown"

        if fetch_remote and data["remote"] != "unknown":
            fetch = run_git(["fetch", "origin", "main", "--prune"], timeout=20)
            if fetch.returncode == 0:
                data["fetch_ok"] = True
            else:
                data["fetch_error"] = (fetch.stderr or fetch.stdout or "git fetch failed").strip()

        res = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        if res.returncode == 0:
            data["upstream"] = res.stdout.strip() or "unknown"
        elif data["remote"] != "unknown":
            data["upstream"] = "origin/main"

        upstream = data["upstream"] if data["upstream"] != "unknown" else "origin/main"
        remote = run_git(["rev-parse", upstream])
        if remote.returncode == 0:
            data["remote_commit"] = remote.stdout.strip()
            data["remote_short_commit"] = data["remote_commit"][:7]

        cnt = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
        if cnt.returncode == 0:
            parts = cnt.stdout.strip().split()
            if len(parts) >= 2:
                ahead, behind = int(parts[0]), int(parts[1])
                data["ahead"] = ahead
                data["behind"] = behind
                if ahead and behind:
                    data["relation"] = "diverged"
                elif ahead:
                    data["relation"] = "ahead"
                elif behind:
                    data["relation"] = "behind"
                else:
                    data["relation"] = "up_to_date"

        show_ver = run_git(["show", f"{upstream}:VERSION"])
        if show_ver.returncode == 0:
            data["remote_version"] = show_ver.stdout.strip() or "unknown"
            if data["remote_version"] == data["local_version"]:
                data["version_relation"] = "same"
            elif data["remote_version"] != "unknown" and data["local_version"] != "unknown":
                data["version_relation"] = "different"

        show_local = run_git(["show", "-s", "--format=%h%x09%cs%x09%s", "HEAD"])
        if show_local.returncode == 0:
            parts = show_local.stdout.strip().split("	", 2)
            if len(parts) == 3:
                data["local_change"] = {"short_commit": parts[0], "date": parts[1], "subject": parts[2]}

        if data.get("remote_commit") not in (None, "unknown"):
            show_remote = run_git(["show", "-s", "--format=%h%x09%cs%x09%s", data["remote_commit"]])
            if show_remote.returncode == 0:
                parts = show_remote.stdout.strip().split("	", 2)
                if len(parts) == 3:
                    data["remote_change"] = {"short_commit": parts[0], "date": parts[1], "subject": parts[2]}

        log_range = f"HEAD..{upstream}" if data.get("relation") == "behind" else upstream
        git_log = run_git(["log", "--pretty=format:%h%x09%cs%x09%s", "-n", "8", log_range])
        if git_log.returncode == 0 and git_log.stdout.strip():
            commits = []
            for line in git_log.stdout.strip().splitlines():
                parts = line.split("	", 2)
                if len(parts) == 3:
                    commits.append({"short_commit": parts[0], "date": parts[1], "subject": parts[2]})
            data["latest_changes"] = commits

        res = run_git(["status", "--porcelain"])
        if res.returncode == 0:
            data["dirty"] = bool(res.stdout.strip())
    except Exception as exc:
        data["error"] = str(exc)
    return data

def _service_status(service):
    cfg = load_config(CONFIG_PATH)
    return service_status(cfg, service).get("active", "unknown")


def _restart_allowed_service(service):
    cfg = load_config(CONFIG_PATH)
    return monitor_restart_service(cfg, service)

@app.context_processor
def inject_globals():
    default_theme = "light"
    try:
        default_theme = (load_config(CONFIG_PATH).get("ui", {}).get("default_theme") or "light").strip().lower()
        if default_theme not in ("light", "dark"):
            default_theme = "light"
    except Exception:
        default_theme = "light"
    return {
        "version": Path("VERSION").read_text(encoding="utf-8").strip() if Path("VERSION").exists() else "dev",
        "csrf_token": _csrf_token,
        "csrf_field": _csrf_field,
        "default_theme": default_theme,
        "role_at_least": role_at_least,
        "role_definitions": ROLE_DEFINITIONS,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = authenticate(request.form.get("username", ""), request.form.get("password", ""))
        if user:
            session["user"] = user
            try:
                write_audit(load_config(CONFIG_PATH), "login_success", actor=user.get("username"), details={"role": user.get("role")})
            except Exception:
                pass
            return redirect(url_for("dashboard"))
        flash("Invalid credentials")
        try:
            write_audit(load_config(CONFIG_PATH), "login_failed", actor=request.form.get("username", ""))
        except Exception:
            pass
    return render_template("login.html")


@app.route("/logout")
def logout():
    user = current_user() or {}
    try:
        write_audit(load_config(CONFIG_PATH), "logout", actor=user.get("username", "unknown"))
    except Exception:
        pass
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    cfg, state = get_status()
    services = all_service_status(cfg)
    errors, warnings = validate_config(cfg)
    policy_state = load_policy_state(cfg)
    apply_runs = list_apply_runs(cfg, limit=25)
    health_report = compute_health_report(cfg, state, policy_state=policy_state, services=services, apply_runs=apply_runs)
    setup_wizard_status = _compute_setup_wizard_status(cfg, state)
    production_readiness = compute_production_readiness(
        cfg,
        state,
        setup_wizard=setup_wizard_status,
        health_report=health_report,
        config_errors=errors,
        config_warnings=warnings,
    )
    return render_template(
        "dashboard.html",
        cfg=cfg,
        state=state,
        services=services,
        git_status=_git_status(),
        config_errors=errors,
        config_warnings=warnings,
        health_report=health_report,
        production_readiness=production_readiness,
        setup_wizard=setup_wizard_status,
        user=current_user(),
    )


@app.route("/sync/run", methods=["POST"])
@admin_required
def sync_run():
    cfg = load_config(CONFIG_PATH)
    if _manual_sync_blocked(cfg):
        flash("Manual sync is disabled while scheduler auto-apply is active. Disable scheduler first, or use Dry Run for preview.")
        return redirect(url_for("dashboard"))
    ok = scheduler.run_now_background("manual")
    flash("Sync started in background." if ok else "Sync already running. Request ignored.")
    return redirect(url_for("dashboard"))


@app.route("/sync/dry-run", methods=["GET", "POST"])
@login_required
def dry_run():
    result = None
    if request.method == "POST":
        user = current_user() or {}
        if not role_at_least(user.get("role", "viewer"), "operator"):
            abort(403)
        result = run_cycle(mode="dry_run", config_path=CONFIG_PATH).to_dict()
    else:
        _cfg, state = get_status()
        result = state.get("last_dry_run")
    return render_template("dry_run.html", result=result, user=current_user())


@app.route("/scheduler/<action>", methods=["POST"])
@admin_required
def scheduler_action(action):
    cfg = load_config(CONFIG_PATH)
    sched = cfg.setdefault("scheduler", {})
    if action in ("enable", "resume"):
        allowed, blockers, wizard = _setup_wizard_allows_scheduler_enable(cfg)
        if not allowed:
            flash("Scheduler enable blocked by First Run Setup Wizard: " + "; ".join(blockers or ["setup is not production-ready"]))
            return redirect(url_for("setup_wizard_center"))
        sched["enabled"] = True
        cfg.setdefault("setup_wizard", {})["first_run_completed"] = True
        message = "Scheduler enabled/resumed. First Run Setup marked complete."
    elif action in ("disable", "pause"):
        sched["enabled"] = False
        message = "Scheduler disabled/paused."
    elif action == "run-now":
        if _manual_sync_blocked(cfg):
            flash("Manual run is disabled while scheduler auto-apply is active. Disable scheduler first, or use Dry Run for preview.")
            return redirect(url_for("dashboard"))
        ok = scheduler.run_now_background("manual")
        flash("Sync started in background." if ok else "Sync already running. Request ignored.")
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid scheduler action.")
        return redirect(url_for("dashboard"))
    save_config(cfg, CONFIG_PATH)
    write_audit(cfg, f"scheduler_{action}", actor=current_user().get("username"))
    flash(message)
    return redirect(url_for("dashboard"))


@app.route("/scheduler/settings", methods=["POST"])
@admin_required
def scheduler_settings():
    cfg = load_config(CONFIG_PATH)
    sched = cfg.setdefault("scheduler", {})
    for key in ("active_interval_seconds", "idle_interval_seconds", "error_retry_interval_seconds", "apply_cooldown_seconds"):
        if key in request.form:
            sched[key] = int(request.form.get(key) or 0)
    save_config(cfg, CONFIG_PATH)
    flash("Scheduler settings saved.")
    return redirect(url_for("config_page"))


def _network_validation(network: dict, cfg: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    seen = set()
    duplicates = set()
    for item in flatten_nodes(network):
        name = item.get("name")
        if name in seen:
            duplicates.add(name)
        seen.add(name)
        try:
            if float(item.get("downloadBandwidthMbps") or 0) < 0 or float(item.get("uploadBandwidthMbps") or 0) < 0:
                errors.append(f"Node {name} has negative bandwidth")
        except Exception:
            errors.append(f"Node {name} has invalid bandwidth")
    if duplicates:
        errors.append("Duplicate node names: " + ", ".join(sorted(duplicates)))
    rows = read_shaped_devices_csv(cfg["paths"]["shaped_devices_csv"])
    missing = []
    for row in rows.values():
        parent = str(row.get("Parent Node") or "").strip()
        if parent and parent not in seen:
            missing.append(parent)
    if missing:
        errors.append("Missing parent nodes referenced by ShapedDevices.csv: " + ", ".join(sorted(set(missing))[:10]))
    if any(item.get("virtual") for item in flatten_nodes(network)):
        warnings.append("Virtual/logical nodes are present. LibreQoS may promote children to the nearest non-virtual ancestor during shaping; avoid name collisions.")
    return errors, warnings


@app.route("/network")
@login_required
def network_layout():
    cfg, state = get_status()
    network = read_network_json(cfg["paths"]["network_json"])
    last_run = state.get("last_run") or state.get("last_dry_run") or {}
    node_math = last_run.get("node_math", {}) if isinstance(last_run, dict) else {}
    rows = read_shaped_devices_csv(cfg["paths"]["shaped_devices_csv"])
    return render_template("network_layout.html", network=network, node_math=node_math, config=cfg, nodes_flat=flatten_nodes(network), shaped_rows=rows, user=current_user())


@app.route("/api/network_layout/save", methods=["POST"])
@admin_required
def api_network_layout_save():
    cfg = load_config(CONFIG_PATH)
    data = request.get_json(force=True) or {}
    network = data.get("network")
    if not isinstance(network, dict):
        return jsonify({"ok": False, "error": "network must be a JSON object"}), 400
    errors, warnings = _network_validation(network, cfg)
    if errors:
        return jsonify({"ok": False, "errors": errors, "warnings": warnings}), 400
    text = render_network_json(network)
    atomic_write_text(cfg["paths"]["network_json"], text)
    write_audit(cfg, "network_layout_saved", actor=(current_user() or {}).get("username"), details={"nodes": len(flatten_nodes(network)), "warnings": warnings})
    return jsonify({"ok": True, "warnings": warnings, "nodes": len(flatten_nodes(network))})


@app.route("/routers")
@login_required
def router_overview_center():
    """Compatibility alias: router overview now lives inside Config Center.

    Avoid a duplicate top-level router page; keep old links working by opening
    the Config Center Routers tab where router settings and read-only insight
    are shown together.
    """
    return redirect(url_for("config_page", tab="routers"))


@app.route("/api/routers/overview")
@login_required
def api_router_overview():
    cfg, state = get_status()
    rows = read_shaped_devices_csv(cfg["paths"].get("shaped_devices_csv", ""))
    return jsonify(compute_router_overview(cfg, state, rows=rows))


@app.route("/devices")
@login_required
def shaped_devices():
    cfg, state = get_status()
    rows = read_shaped_devices_csv(cfg["paths"]["shaped_devices_csv"])
    last_run = state.get("last_run") or state.get("last_dry_run") or {}
    meta = last_run.get("meta", {}) if isinstance(last_run, dict) else {}
    return render_template("shaped_devices.html", rows=rows, meta=meta, user=current_user())




# =========================
# Settings / user management
# =========================
@app.route("/settings/users")
@owner_required
def settings_users():
    users = list_users(USERS_PATH)
    return render_template("settings_users.html", users=users, role_options=role_options(), role_definitions=ROLE_DEFINITIONS, user=current_user())


@app.route("/settings/users/add", methods=["POST"])
@owner_required
def settings_users_add():
    actor = current_user() or {}
    try:
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        role = request.form.get("role", "viewer")
        created = add_user(username, password, role, USERS_PATH)
        write_audit(load_config(CONFIG_PATH), "user_added", actor=actor.get("username"), details={"username": created.get("username"), "role": created.get("role")})
        flash(f"User {created.get('username')} created.")
    except Exception as e:
        flash(f"Add user failed: {e}")
    return redirect(url_for("settings_users"))


@app.route("/settings/users/<path:username>/update", methods=["POST"])
@owner_required
def settings_users_update(username):
    actor = current_user() or {}
    try:
        new_username = request.form.get("username", "")
        role = request.form.get("role", "viewer")
        updated = update_user(username, new_username, role, USERS_PATH)
        # If admin renamed their own account, refresh current session.
        if actor.get("username") == username:
            session["user"] = {"username": updated.get("username"), "role": updated.get("role")}
        write_audit(load_config(CONFIG_PATH), "user_updated", actor=actor.get("username"), details={"old_username": username, "username": updated.get("username"), "role": updated.get("role")})
        flash(f"User {username} updated.")
    except Exception as e:
        flash(f"Update user failed: {e}")
    return redirect(url_for("settings_users"))


@app.route("/settings/users/<path:username>/password", methods=["POST"])
@owner_required
def settings_users_password(username):
    actor = current_user() or {}
    try:
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")
        if password != confirm:
            raise ValueError("Password confirmation does not match.")
        changed = set_user_password(username, password, USERS_PATH)
        write_audit(load_config(CONFIG_PATH), "user_password_changed", actor=actor.get("username"), details={"username": changed.get("username")})
        flash(f"Password updated for {username}.")
    except Exception as e:
        flash(f"Password update failed: {e}")
    return redirect(url_for("settings_users"))


@app.route("/settings/users/<path:username>/delete", methods=["POST"])
@owner_required
def settings_users_delete(username):
    actor = current_user() or {}
    try:
        deleted = delete_user(username, current_username=actor.get("username"), path=USERS_PATH)
        write_audit(load_config(CONFIG_PATH), "user_deleted", actor=actor.get("username"), details={"username": deleted.get("username"), "role": deleted.get("role")})
        flash(f"User {username} deleted.")
    except Exception as e:
        flash(f"Delete user failed: {e}")
    return redirect(url_for("settings_users"))


@app.route("/api/users")
@owner_required
def api_users():
    return jsonify(list_users(USERS_PATH))


@app.route("/config", methods=["GET", "POST"])
@admin_required
def config_page():
    if request.method == "POST":
        raw = request.form.get("config_json", "")
        try:
            data = json.loads(raw)
            previous = load_config(CONFIG_PATH)
            previous_mode = ((previous.get("policies") or {}).get("mode") if isinstance(previous.get("policies"), dict) else None)
            # Policy Overview controls include a few app.* runtime settings.
            # They must still turn preset mode into Custom when edited from
            # Config Center → Policies. This protects server-side saves even if
            # browser JS misses markPolicyCustom().
            if previous_mode in {"conservative", "balanced", "aggressive"} and policy_context_changed(previous, data):
                data.setdefault("policies", {})["mode"] = "custom"
            data = reconcile_policy_mode(data)
            new_mode = ((data.get("policies") or {}).get("mode") if isinstance(data.get("policies"), dict) else None)
            save_config(data, CONFIG_PATH, backup_existing=True)
            write_audit(load_config(CONFIG_PATH), "config_saved", actor=current_user().get("username"), details={"previous_policy_mode": previous_mode, "policy_mode": new_mode})
            if previous_mode != new_mode and new_mode == "custom":
                flash("config.json saved. Policy mode changed to Custom because saved policy values differ from the selected preset.")
            else:
                flash("config.json saved.")
        except Exception as e:
            flash(f"Config save failed: {e}")
    cfg = load_config(CONFIG_PATH)
    errors, warnings = validate_config(cfg)
    schema_report = validate_schema(cfg)
    allowed_tabs = {"overview", "apply", "paths", "collector", "scheduler", "services", "policies", "notifications", "defaults", "routers", "router"}
    initial_tab = request.args.get("tab") or "overview"
    if initial_tab not in allowed_tabs:
        initial_tab = "overview"
    try:
        router_rows = read_shaped_devices_csv(cfg["paths"].get("shaped_devices_csv", ""))
    except Exception:
        router_rows = {}
    router_overview = compute_router_overview(cfg, get_status()[1], rows=router_rows)
    return render_template(
        "config.html",
        config_json=json.dumps(cfg, indent=2),
        config=cfg,
        config_errors=errors,
        config_warnings=warnings,
        schema_report=schema_report,
        schema_version=CONFIG_SCHEMA_VERSION,
        policy_conflicts=evaluate_policy_conflicts(cfg),
        identity_report=client_identity_report(cfg),
        telegram=telegram_settings_summary(cfg),
        router_overview=router_overview,
        policy_hierarchy=grouped_policy_schema(),
        initial_tab=initial_tab,
        user=current_user(),
    )


@app.route("/config/simulate", methods=["POST"])
@admin_required
def config_simulate():
    """Read-only preview for unsaved Config Center changes.

    Accepts JSON or form data containing config_json and returns config schema
    health, diff, policy simulation, and operator-readable impact hints. It never
    writes config.json or generated LibreQoS files.
    """
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        raw = payload.get("config_json") if isinstance(payload, dict) else None
        proposed = json.loads(raw) if raw else payload.get("config") if isinstance(payload, dict) else None
        if not isinstance(proposed, dict):
            return jsonify({"ok": False, "error": "config_json or config object is required"}), 400
        migrated, migration_notes = migrate_config_schema(proposed)
        saved = load_config(CONFIG_PATH)
        _cfg, state = get_status()
        report = simulate_config_change(saved, migrated, state)
        report["migration_notes"] = sorted(set((report.get("migration_notes") or []) + migration_notes))
        return jsonify(report)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/config/dhcp/<int:router_idx>/<int:server_idx>/toggle", methods=["POST"])
@admin_required
def toggle_dhcp_server(router_idx, server_idx):
    cfg = load_config(CONFIG_PATH)
    try:
        server = cfg["routers"][router_idx]["dhcp"]["servers"][server_idx]
        server["enabled"] = not bool(server.get("enabled", True))
        save_config(cfg, CONFIG_PATH)
        write_audit(cfg, "dhcp_server_toggled", actor=current_user().get("username"), details={"router_idx": router_idx, "server": server.get("name"), "enabled": server.get("enabled")})
        flash(f"DHCP server {server.get('name')} set enabled={server['enabled']}")
    except Exception as e:
        flash(f"Toggle failed: {e}")
    return redirect(url_for("config_page"))


def _posted_or_saved_config():
    raw = request.form.get("config_json", "").strip()
    if raw:
        data = json.loads(raw)
        # Validate using same loader rules without writing first.
        errors, _warnings = validate_config(data)
        if errors:
            raise ValueError("Invalid current UI config: " + "; ".join(errors))
        return data
    return load_config(CONFIG_PATH)


def _router_index_from_form() -> int:
    raw = request.form.get("router_idx", "0")
    try:
        idx = int(raw)
    except Exception:
        idx = 0
    return max(idx, 0)


def _get_router_from_cfg(cfg: dict, router_idx: int) -> dict:
    routers = cfg.get("routers") or []
    if not routers:
        raise ValueError("No routers configured in current UI config.")
    if router_idx >= len(routers):
        raise IndexError(f"Router index {router_idx} is out of range. Available routers: 0..{len(routers)-1}")
    return routers[router_idx]


@app.route("/config/router/test-current", methods=["POST"])
@admin_required
def test_current_router():
    router_idx = _router_index_from_form()
    try:
        cfg = _posted_or_saved_config()
        router = _get_router_from_cfg(cfg, router_idx)
        status = test_router_connection(router)
        flash(f"Router {router.get('name')} test using current UI config: {status}")
    except Exception as e:
        flash(f"Router test failed: {e}")
    return redirect(url_for("config_page"))


@app.route("/config/router/discover-dhcp-current", methods=["POST"])
@admin_required
def discover_current_dhcp():
    router_idx = _router_index_from_form()
    try:
        cfg = _posted_or_saved_config()
        router = _get_router_from_cfg(cfg, router_idx)
        pool, api, err = connect_to_router(router, retries=1)
        if not api:
            flash(f"DHCP discovery failed: {err}")
            return redirect(url_for("config_page"))
        try:
            rows = get_resource_data(api, "/ip/dhcp-server")
        finally:
            try: pool.disconnect()
            except Exception: pass
        existing = {s.get("name") for s in router.setdefault("dhcp", {}).setdefault("servers", [])}
        added = 0
        for row in rows:
            name = row.get("name")
            if name and name not in existing:
                router["dhcp"]["servers"].append({
                    "name": name,
                    "enabled": False,
                    "mode": "per_site",
                    "plan_source": "config_default",
                    "default_plan_down_mbps": cfg.get("defaults", {}).get("default_dhcp_per_client_mbps", 15),
                    "default_plan_up_mbps": cfg.get("defaults", {}).get("default_dhcp_per_client_mbps", 15),
                    "download_factor": 0.5,
                    "upload_factor": 0.5,
                    "node_type": "site",
                    "node_name": "DHCP-{server}-{router}",
                })
                existing.add(name)
                added += 1
        save_config(cfg, CONFIG_PATH)
        write_audit(cfg, "dhcp_discovered", actor=current_user().get("username"), details={"router_idx": router_idx, "added": added})
        flash(f"DHCP discovery complete using current UI config. Added {added} server(s), default excluded and saved config.json.")
    except Exception as e:
        flash(f"DHCP discovery failed: {e}")
    return redirect(url_for("config_page"))


# Backward-compatible routes from v1.4/v1.6. The UI no longer uses them,
# but keeping them prevents old bookmarks/forms from breaking.
@app.route("/config/router/<int:router_idx>/test", methods=["POST"])
@admin_required
def test_router(router_idx):
    try:
        cfg = _posted_or_saved_config()
        router = _get_router_from_cfg(cfg, router_idx)
        status = test_router_connection(router)
        flash(f"Router {router.get('name')} test using current UI config: {status}")
    except Exception as e:
        flash(f"Router test failed: {e}")
    return redirect(url_for("config_page"))


@app.route("/config/router/<int:router_idx>/discover-dhcp", methods=["POST"])
@admin_required
def discover_dhcp(router_idx):
    # Reuse the safer current-config implementation by injecting form router_idx.
    # Flask request.form is immutable, so duplicate the logic instead of mutating it.
    try:
        cfg = _posted_or_saved_config()
        router = _get_router_from_cfg(cfg, router_idx)
        pool, api, err = connect_to_router(router, retries=1)
        if not api:
            flash(f"DHCP discovery failed: {err}")
            return redirect(url_for("config_page"))
        try:
            rows = get_resource_data(api, "/ip/dhcp-server")
        finally:
            try: pool.disconnect()
            except Exception: pass
        existing = {s.get("name") for s in router.setdefault("dhcp", {}).setdefault("servers", [])}
        added = 0
        for row in rows:
            name = row.get("name")
            if name and name not in existing:
                router["dhcp"]["servers"].append({
                    "name": name, "enabled": False, "mode": "per_site", "plan_source": "config_default",
                    "default_plan_down_mbps": cfg.get("defaults", {}).get("default_dhcp_per_client_mbps", 15),
                    "default_plan_up_mbps": cfg.get("defaults", {}).get("default_dhcp_per_client_mbps", 15),
                    "download_factor": 0.5, "upload_factor": 0.5, "node_type": "site", "node_name": "DHCP-{server}-{router}",
                })
                existing.add(name)
                added += 1
        save_config(cfg, CONFIG_PATH)
        write_audit(cfg, "dhcp_discovered", actor=current_user().get("username"), details={"router_idx": router_idx, "added": added})
        flash(f"DHCP discovery complete using current UI config. Added {added} server(s), default excluded and saved config.json.")
    except Exception as e:
        flash(f"DHCP discovery failed: {e}")
    return redirect(url_for("config_page"))






@app.route("/policy")
@admin_required
def policy_center():
    """Compatibility alias: policies now live inside Config Center."""
    return redirect(url_for("config_page", tab="policies"))


@app.route("/api/policy/conflicts")
@admin_required
def api_policy_conflicts():
    cfg, state = get_status()
    normalize_policies(cfg)
    return jsonify({
        "conflicts": evaluate_policy_conflicts(cfg),
        "identity": client_identity_report(cfg),
        "closest_preset": closest_preset(cfg),
    })


@app.route("/policy/save", methods=["POST"])
@admin_required
def policy_save_settings():
    cfg = load_config(CONFIG_PATH)
    before = cfg.get("policies", {})
    cfg = parse_policy_form(request.form, cfg)
    cfg.setdefault("policies", {})["mode"] = "custom"
    save_config(cfg, CONFIG_PATH, backup_existing=True)
    write_audit(cfg, "policy_settings_saved", actor=(current_user() or {}).get("username"), details={"mode": "custom", "previous_mode": before.get("mode") if isinstance(before, dict) else None})
    flash("Policy settings saved. Preset changed to Custom because values were edited manually. Run Dry Run to preview decisions before enabling auto-apply.")
    return redirect(url_for("config_page", tab="policies"))


@app.route("/policy/apply-preset/<preset>", methods=["POST"])
@admin_required
def policy_apply_preset(preset):
    cfg = load_config(CONFIG_PATH)
    try:
        new_cfg = apply_policy_preset(cfg, preset)
        save_config(new_cfg, CONFIG_PATH, backup_existing=True)
        write_audit(new_cfg, "policy_preset_applied", actor=(current_user() or {}).get("username"), details={"preset": preset})
        flash(f"Policy preset applied: {preset}. Run Dry Run to preview cleanup/apply behavior.")
    except Exception as exc:
        flash(f"Unable to apply policy preset: {exc}")
    return redirect(url_for("config_page", tab="policies"))


@app.route("/policy/confirm/<path:confirmation_id>", methods=["POST"])
@admin_required
def policy_confirm_cleanup(confirmation_id):
    cfg = load_config(CONFIG_PATH)
    pstate = load_policy_state(cfg)
    actor = (current_user() or {}).get("username", "admin")
    if confirm_cleanup(pstate, confirmation_id, actor=actor):
        save_policy_state(cfg, pstate)
        write_audit(cfg, "cleanup_confirmed", actor=actor, details={"confirmation_id": confirmation_id})
        flash("Cleanup confirmation saved. Confirmed cleanup can be applied on the next successful sync run.")
    else:
        flash("Cleanup confirmation was not found or already expired.")
    return redirect(url_for("policy_center"))


@app.route("/policy/dismiss/<path:confirmation_id>", methods=["POST"])
@admin_required
def policy_dismiss_confirmation(confirmation_id):
    cfg = load_config(CONFIG_PATH)
    pstate = load_policy_state(cfg)
    actor = (current_user() or {}).get("username", "admin")
    if dismiss_confirmation(pstate, confirmation_id, actor=actor):
        save_policy_state(cfg, pstate)
        write_audit(cfg, "cleanup_confirmation_dismissed", actor=actor, details={"confirmation_id": confirmation_id})
        flash("Pending cleanup confirmation dismissed.")
    else:
        flash("Cleanup confirmation was not found.")
    return redirect(url_for("policy_center"))






@app.route("/health")
@login_required
def health_trends_center():
    """Compatibility redirect: health trends are now consolidated into Dashboard."""
    return redirect(url_for("dashboard") + "#source-health-performance")


@app.route("/api/health/trends")
@login_required
def api_health_trends():
    cfg, state = get_status()
    policy_state = load_policy_state(cfg)
    services = all_service_status(cfg)
    apply_runs = list_apply_runs(cfg, limit=25)
    return jsonify(compute_health_report(cfg, state, policy_state=policy_state, services=services, apply_runs=apply_runs))


@app.route("/api/production/readiness")
@login_required
def api_production_readiness():
    cfg, state = get_status()
    services = all_service_status(cfg)
    errors, warnings = validate_config(cfg)
    policy_state = load_policy_state(cfg)
    apply_runs = list_apply_runs(cfg, limit=25)
    health_report = compute_health_report(cfg, state, policy_state=policy_state, services=services, apply_runs=apply_runs)
    setup_wizard_status = _compute_setup_wizard_status(cfg, state)
    return jsonify(compute_production_readiness(
        cfg,
        state,
        setup_wizard=setup_wizard_status,
        health_report=health_report,
        config_errors=errors,
        config_warnings=warnings,
    ))


@app.route("/reports")
@admin_required
def smart_reports_center():
    """Smart Reports / Operator Audit Center."""
    cfg, state = get_status()
    policy_state = load_policy_state(cfg)
    services = all_service_status(cfg)
    backups = list_backups(cfg)
    report = compute_operator_report(
        cfg,
        state,
        policy_state=policy_state,
        services=services,
        backups=backups,
    )
    return render_template(
        "reports.html",
        cfg=cfg,
        state=state,
        report=report,
        user=current_user(),
    )


@app.route("/api/reports/operator")
@admin_required
def api_operator_report():
    """Return the Smart Reports / Operator Audit payload as JSON."""
    cfg, state = get_status()
    policy_state = load_policy_state(cfg)
    services = all_service_status(cfg)
    backups = list_backups(cfg)
    report = compute_operator_report(
        cfg,
        state,
        policy_state=policy_state,
        services=services,
        backups=backups,
    )
    return jsonify(report)


@app.route("/reports/export/<fmt>")
@admin_required
def reports_export(fmt):
    """Export the Smart Reports / Operator Audit payload."""
    cfg, state = get_status()
    policy_state = load_policy_state(cfg)
    services = all_service_status(cfg)
    backups = list_backups(cfg)
    report = compute_operator_report(
        cfg,
        state,
        policy_state=policy_state,
        services=services,
        backups=backups,
    )

    if fmt == "json":
        return Response(
            json.dumps(report, indent=2, ensure_ascii=False),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=lqos_operator_report.json"},
        )

    if fmt == "csv":
        return Response(
            report_to_csv(report),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=lqos_operator_report.csv"},
        )

    if fmt in {"md", "markdown"}:
        return Response(
            report_to_markdown(report),
            mimetype="text/markdown",
            headers={"Content-Disposition": "attachment; filename=lqos_operator_report.md"},
        )

    abort(404)


@app.route("/lifecycle")
@admin_required
def lifecycle_center():
    """Client Lifecycle Timeline Center: read-only view of client state, cleanup queue, and per-client events."""
    cfg, state = get_status()
    pstate = load_policy_state(cfg)
    status = request.args.get("status", "all")
    source = request.args.get("source", "all")
    search = request.args.get("search", "")
    code = request.args.get("code") or ""
    limit = int(request.args.get("limit", 500))
    event = request.args.get("event", "all")
    event_limit = int(request.args.get("event_limit", 50))
    event_page = int(request.args.get("event_page", 1))
    report = compute_lifecycle_report(pstate, status=status, source=source, search=search, code=code, limit=limit, event=event, event_limit=event_limit, event_page=event_page)
    return render_template(
        "lifecycle.html",
        cfg=cfg,
        state=state,
        policy_state=pstate,
        summary=report.get("summary", {}),
        report=report,
        events=report.get("events", []),
        client_items=[(c.get("code"), c) for c in report.get("clients", [])],
        selected_code=code,
        user=current_user(),
    )


@app.route("/api/lifecycle/report")
@admin_required
def api_lifecycle_report():
    cfg = load_config(CONFIG_PATH)
    pstate = load_policy_state(cfg)
    report = compute_lifecycle_report(
        pstate,
        status=request.args.get("status", "all"),
        source=request.args.get("source", "all"),
        search=request.args.get("search", ""),
        code=request.args.get("code", ""),
        limit=int(request.args.get("limit", 500)),
        event=request.args.get("event", "all"),
        event_limit=int(request.args.get("event_limit", 50)),
        event_page=int(request.args.get("event_page", 1)),
    )
    return jsonify(report)


@app.route("/lifecycle/export/<fmt>")
@admin_required
def lifecycle_export(fmt):
    cfg = load_config(CONFIG_PATH)
    pstate = load_policy_state(cfg)
    report = compute_lifecycle_report(
        pstate,
        status=request.args.get("status", "all"),
        source=request.args.get("source", "all"),
        search=request.args.get("search", ""),
        code=request.args.get("code", ""),
        limit=int(request.args.get("limit", 500)),
        event=request.args.get("event", "all"),
        event_limit=int(request.args.get("event_limit", 50)),
        event_page=int(request.args.get("event_page", 1)),
    )
    if fmt == "json":
        return Response(json.dumps(report, indent=2, ensure_ascii=False), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=lqos_lifecycle_report.json"})
    if fmt == "csv":
        return Response(lifecycle_report_to_csv(report), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=lqos_lifecycle_report.csv"})
    if fmt in {"md", "markdown"}:
        return Response(lifecycle_report_to_markdown(report), mimetype="text/markdown", headers={"Content-Disposition": "attachment; filename=lqos_lifecycle_report.md"})
    abort(404)


@app.route("/setup-wizard")
@admin_required
def setup_wizard_center():
    """First Run Setup Wizard: step-by-step operator onboarding."""
    cfg, state = get_status()
    errors, warnings = validate_config(cfg)
    services = all_service_status(cfg)
    setup_report = compute_setup_repair_report(
        cfg,
        state,
        git_status=_git_status(fetch_remote=False),
        services=services,
        config_errors=errors,
        config_warnings=warnings,
    )
    wizard = compute_setup_wizard(cfg, state, setup_report)
    return render_template(
        "setup_wizard.html",
        cfg=cfg,
        state=state,
        report=setup_report,
        wizard=wizard,
        network_modes=NETWORK_MODE_OPTIONS,
        services=services,
        config_errors=errors,
        config_warnings=warnings,
        user=current_user(),
    )


@app.route("/setup-wizard/policy-preset", methods=["POST"])
@admin_required
def setup_wizard_policy_preset():
    cfg = load_config(CONFIG_PATH)
    preset = request.form.get("preset", "balanced")
    try:
        new_cfg = apply_policy_preset(cfg, preset)
        save_config(new_cfg, CONFIG_PATH)
        write_audit(new_cfg, "wizard_policy_preset_applied", actor=(current_user() or {}).get("username"), details={"preset": preset})
        flash(f"Wizard policy preset applied: {preset}. Run Dry Run before enabling scheduler or auto-apply.")
    except Exception as exc:
        flash(f"Wizard policy preset update failed: {exc}")
    return redirect(url_for("setup_wizard_center"))


@app.route("/setup-wizard/network-mode", methods=["POST"])
@admin_required
def setup_wizard_network_mode():
    cfg = load_config(CONFIG_PATH)
    mode = request.form.get("network_mode", "router_children")
    valid = {m for m, _label in NETWORK_MODE_OPTIONS}
    if mode not in valid:
        flash("Invalid network layout mode.")
        return redirect(url_for("setup_wizard_center"))
    cfg["network_mode"] = mode
    if mode == "flat_no_parent":
        cfg["flat_network"] = True
        cfg["no_parent"] = True
    elif mode == "flat_router_root":
        cfg["flat_network"] = True
        cfg["no_parent"] = False
    else:
        cfg["flat_network"] = False
        cfg["no_parent"] = False
    save_config(cfg, CONFIG_PATH)
    write_audit(cfg, "wizard_network_mode_saved", actor=(current_user() or {}).get("username"), details={"network_mode": mode})
    flash(f"Network layout mode saved: {mode}. Run Dry Run to preview generated parent nodes.")
    return redirect(url_for("setup_wizard_center"))




@app.route("/setup-wizard/complete", methods=["POST"])
@admin_required
def setup_wizard_mark_complete():
    cfg, state = get_status()
    wizard = _compute_setup_wizard_status(cfg, state)
    if not wizard.get("production_ready") and not cfg.get("setup_wizard", {}).get("allow_force_scheduler_enable", False):
        flash("Setup Wizard cannot be marked complete yet: " + "; ".join(wizard.get("go_live_blockers") or ["setup is not production-ready"]))
        return redirect(url_for("setup_wizard_center"))
    cfg.setdefault("setup_wizard", {})["first_run_completed"] = True
    save_config(cfg, CONFIG_PATH)
    write_audit(cfg, "setup_wizard_completed", actor=current_user().get("username"), details={"readiness": wizard.get("readiness"), "progress": wizard.get("progress")})
    flash("First Run Setup marked complete. Dashboard is now the default landing page.")
    return redirect(url_for("dashboard"))


@app.route("/setup-wizard/reset", methods=["POST"])
@admin_required
def setup_wizard_reset():
    cfg = load_config(CONFIG_PATH)
    cfg.setdefault("setup_wizard", {})["first_run_completed"] = False
    save_config(cfg, CONFIG_PATH)
    write_audit(cfg, "setup_wizard_reset", actor=current_user().get("username"))
    flash("First Run Setup was reset. The wizard will guide administrators again until completed.")
    return redirect(url_for("setup_wizard_center"))


@app.route("/notifications", methods=["GET", "POST"])
@admin_required
def notifications_center():
    """Compatibility alias: Telegram notification settings now live inside Config Center."""
    cfg, state = get_status()
    if request.method == "POST":
        tg = cfg.setdefault("notifications", {}).setdefault("telegram", {})
        tg["enabled"] = bool(request.form.get("telegram_enabled"))
        tg["bot_token"] = request.form.get("bot_token", "").strip()
        tg["chat_id"] = request.form.get("chat_id", "").strip()
        tg["base_url"] = request.form.get("base_url", "").strip().rstrip("/")
        tg["parse_mode"] = request.form.get("parse_mode", "HTML").strip() or "HTML"
        tg["notify_levels"] = request.form.getlist("notify_levels") or ["critical", "warning"]
        for key in ["timeout_seconds", "minimum_interval_seconds", "dedupe_window_minutes", "max_items_per_digest"]:
            try:
                tg[key] = max(0, int(request.form.get(key, tg.get(key, 0)) or 0))
            except Exception:
                pass
        tg["send_digest"] = bool(request.form.get("send_digest"))
        tg["send_individual"] = bool(request.form.get("send_individual"))
        for key in [
            "notify_on_apply_failed", "notify_on_policy_block", "notify_on_confirmation_required",
            "notify_on_update_available", "notify_on_source_health_warning", "notify_on_performance_slow",
        ]:
            tg[key] = bool(request.form.get(key))
        save_config(cfg, CONFIG_PATH, backup_existing=True)
        write_audit(cfg, "telegram_notifications_saved", actor=(current_user() or {}).get("username"), details={"enabled": tg.get("enabled"), "levels": tg.get("notify_levels")})
        flash("Telegram notification settings saved. Notifications now live under Config Center.")
    return redirect(url_for("config_page", tab="notifications"))


@app.route("/notifications/test", methods=["POST"])
@admin_required
def notifications_test():
    cfg = load_config(CONFIG_PATH)
    result = send_test_message(cfg, actor=(current_user() or {}).get("username"))
    write_audit(cfg, "telegram_test_sent", actor=(current_user() or {}).get("username"), details={"ok": result.get("ok"), "error": result.get("error")})
    flash("Telegram test sent successfully." if result.get("ok") else f"Telegram test failed: {result.get('error') or result.get('response') or 'unknown error'}")
    return redirect(url_for("config_page", tab="notifications"))


@app.route("/notifications/send-current", methods=["POST"])
@admin_required
def notifications_send_current():
    cfg, state = get_status()
    policy_state = load_policy_state(cfg)
    services = all_service_status(cfg)
    apply_runs = list_apply_runs(cfg, limit=25)
    report = compute_health_report(cfg, state, policy_state=policy_state, services=services, apply_runs=apply_runs)
    result = dispatch_telegram_notifications(cfg, report.get("notifications", []), force=bool(request.form.get("force")), title="LQoSync current health alerts")
    write_audit(cfg, "telegram_current_alerts_sent", actor=(current_user() or {}).get("username"), details={"ok": result.get("ok"), "sent": result.get("sent"), "reason": result.get("reason")})
    if result.get("ok"):
        flash(f"Telegram current alerts sent: {result.get('sent', 0)} item(s).")
    else:
        flash(f"Telegram alert delivery skipped/failed: {result.get('reason') or result.get('error') or result.get('response') or 'unknown'}")
    return redirect(url_for("config_page", tab="notifications"))


@app.route("/api/notifications/telegram/test", methods=["POST"])
@admin_required
def api_notifications_telegram_test():
    cfg = load_config(CONFIG_PATH)
    result = send_test_message(cfg, actor=(current_user() or {}).get("username"))
    return jsonify(result)


@app.route("/setup-repair")
@admin_required
def setup_repair_center():
    """Smart Setup / Repair Center: read-only diagnostics and safe repair guidance."""
    cfg, state = get_status()
    errors, warnings = validate_config(cfg)
    services = all_service_status(cfg)
    report = compute_setup_repair_report(
        cfg,
        state,
        git_status=_git_status(fetch_remote=False),
        services=services,
        config_errors=errors,
        config_warnings=warnings,
    )
    return render_template(
        "setup_repair.html",
        cfg=cfg,
        state=state,
        report=report,
        services=services,
        config_errors=errors,
        config_warnings=warnings,
        user=current_user(),
    )


@app.route("/setup-repair/policy-preset", methods=["POST"])
@admin_required
def setup_repair_policy_preset():
    cfg = load_config(CONFIG_PATH)
    preset = request.form.get("preset", "balanced")
    try:
        new_cfg = apply_policy_preset(cfg, preset)
        save_config(new_cfg, CONFIG_PATH)
        write_audit(new_cfg, "policy_preset_applied", actor=(current_user() or {}).get("username"), details={"preset": preset})
        flash(f"Smart Policy preset applied: {preset}. Run Dry Run before enabling scheduler or auto-apply.")
    except Exception as exc:
        flash(f"Policy preset update failed: {exc}")
    return redirect(url_for("setup_repair_center"))


@app.route("/setup-repair/repair-defaults", methods=["POST"])
@owner_required
def setup_repair_repair_defaults():
    cfg = load_config(CONFIG_PATH)
    result = repair_config_defaults(CONFIG_PATH)
    write_audit(cfg, "smart_defaults_repair", actor=(current_user() or {}).get("username"), details=result)
    if result.get("ok"):
        flash("Smart Defaults Repair completed. Missing safe defaults were merged and config.json was backed up first.")
    else:
        flash("Smart Defaults Repair completed with errors. Review Setup & Repair checks.")
    return redirect(url_for("setup_repair_center"))


@app.route("/api/release/integrity")
@owner_required
def api_release_integrity():
    return jsonify(compute_release_integrity(Path(__file__).resolve().parent))


@app.route("/api/stable-release/check")
@login_required
def api_stable_release_check():
    return jsonify(compute_stable_release_check(Path(__file__).resolve().parent))


@app.route("/updates")
@owner_required
def update_center():
    """Read-only Git/update operations center.

    The UI intentionally shows commands and status instead of running arbitrary
    git operations from the browser. Operators can copy the recommended safe
    commands and run them in SSH, where sudo prompts, backups, and policy
    choices are visible.
    """
    cfg, state = get_status()
    return render_template(
        "updates.html",
        cfg=cfg,
        state=state,
        git_status=_git_status(fetch_remote=True),
        user=current_user(),
    )


@app.route("/docs")
@login_required
def docs_home():
    return redirect(url_for("docs_search_page"))


@app.route("/docs/search")
@login_required
def docs_search_page():
    query = request.args.get("q", "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 25)), 100))
    except Exception:
        limit = 25
    results = search_docs(query, Path(__file__).resolve().parent, limit=limit)
    return render_template("docs_search.html", query=query, results=results, user=current_user())


@app.route("/docs/view/<doc_id>")
@login_required
def docs_view_page(doc_id):
    doc = get_doc(doc_id, Path(__file__).resolve().parent)
    if not doc:
        abort(404)
    query = request.args.get("q", "").strip()
    return render_template("docs_view.html", doc=doc, query=query, user=current_user())


@app.route("/api/docs/search")
@login_required
def api_docs_search():
    query = request.args.get("q", "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 25)), 100))
    except Exception:
        limit = 25
    return jsonify(search_docs(query, Path(__file__).resolve().parent, limit=limit))


@app.route("/api/docs/index")
@login_required
def api_docs_index():
    entries = [entry.public_dict() for entry in build_docs_index(Path(__file__).resolve().parent)]
    return jsonify({"total": len(entries), "docs": entries})


@app.route("/about")
@login_required
def about_page():
    cfg, state = get_status()
    services = cfg.get("services", {}) if isinstance(cfg, dict) else {}
    return render_template("about.html", cfg=cfg, state=state, services_cfg=services, user=current_user())

@app.route("/services/<service>/restart", methods=["POST"])
@admin_required
def restart_service_form(service):
    cfg = load_config(CONFIG_PATH)
    res = _restart_allowed_service(service)
    write_audit(cfg, "service_restart", actor=current_user().get("username"), details={"service": service, "ok": res.get("ok"), "stderr": res.get("stderr", "")[:500]})
    flash(f"Restart {service}: {'OK' if res.get('ok') else 'FAILED'}")
    return redirect(request.referrer or url_for("dashboard"))




@app.route("/operations")
@login_required
def operations_center():
    """Compact Operations Center: services, journals, apply logs, app logs, audit, backups."""
    cfg, state = get_status()
    services = all_service_status(cfg)
    groups = allowed_groups(cfg)
    last = state.get("last_run") or {}
    # Apply history pagination keeps Operations Center compact and consistent with backups/audit.
    allowed_apply_limits = [5, 10, 20, 50]
    try:
        apply_limit = int(request.args.get("apply_limit", 10))
    except Exception:
        apply_limit = 10
    if apply_limit not in allowed_apply_limits:
        apply_limit = 10
    try:
        apply_page = int(request.args.get("apply_page", 1))
    except Exception:
        apply_page = 1
    apply_runs_all = list_apply_runs(cfg, limit=200)
    total_apply_runs = len(apply_runs_all)
    apply_pages = max(1, (total_apply_runs + apply_limit - 1) // apply_limit)
    apply_page = max(1, min(apply_page, apply_pages))
    apply_start = (apply_page - 1) * apply_limit
    apply_runs = apply_runs_all[apply_start:apply_start + apply_limit]
    # Make failed apply runs actionable directly from Operations Center.
    for _run in apply_runs:
        try:
            if _run.get("ok") is False and _run.get("run_id"):
                _run["diagnostic"] = get_apply_diagnostic(cfg, str(_run.get("run_id")))
        except Exception:
            pass
    apply_pagination = {
        "page": apply_page,
        "pages": apply_pages,
        "limit": apply_limit,
        "total": total_apply_runs,
        "start": apply_start + 1 if total_apply_runs else 0,
        "end": min(apply_start + apply_limit, total_apply_runs),
        "allowed_limits": allowed_apply_limits,
    }

    selected_unit = request.args.get("unit") or next(iter(services.keys()), "lqosync")
    try:
        lines_count = int(request.args.get("lines", cfg.get("services", {}).get("journal_lines_default", 100)))
    except Exception:
        lines_count = 100
    journal = journal_lines(cfg, selected_unit, lines=lines_count) if selected_unit else {"stdout": "", "stderr": ""}

    log_file = Path(cfg["paths"].get("log_file", "logs/lqosync.log"))
    app_log_lines = []
    if log_file.exists():
        app_log_lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-500:]

    backups_all = list_backups(cfg)
    allowed_backup_limits = [5, 10, 20, 50, 100]
    try:
        backup_limit = int(request.args.get("backup_limit", 10))
    except Exception:
        backup_limit = 10
    if backup_limit not in allowed_backup_limits:
        backup_limit = 10
    try:
        backup_page = int(request.args.get("backup_page", 1))
    except Exception:
        backup_page = 1
    total_backups = len(backups_all)
    backup_pages = max(1, (total_backups + backup_limit - 1) // backup_limit)
    backup_page = max(1, min(backup_page, backup_pages))
    start = (backup_page - 1) * backup_limit
    backups = backups_all[start:start + backup_limit]
    backup_pagination = {
        "page": backup_page,
        "pages": backup_pages,
        "limit": backup_limit,
        "total": total_backups,
        "start": start + 1 if total_backups else 0,
        "end": min(start + backup_limit, total_backups),
        "allowed_limits": allowed_backup_limits,
    }

    # Audit pagination mirrors the backup/apply table behavior so Operations Center does not overflow.
    allowed_audit_limits = [25, 50, 100, 200, 500]
    try:
        audit_limit = int(request.args.get("audit_limit", 50))
    except Exception:
        audit_limit = 50
    if audit_limit not in allowed_audit_limits:
        audit_limit = 50
    try:
        audit_page = int(request.args.get("audit_page", 1))
    except Exception:
        audit_page = 1
    audit_all = tail_audit(cfg, limit=1000)
    total_audit = len(audit_all)
    audit_pages = max(1, (total_audit + audit_limit - 1) // audit_limit)
    audit_page = max(1, min(audit_page, audit_pages))
    audit_start = (audit_page - 1) * audit_limit
    audit_events = audit_all[audit_start:audit_start + audit_limit]
    audit_pagination = {
        "page": audit_page,
        "pages": audit_pages,
        "limit": audit_limit,
        "total": total_audit,
        "start": audit_start + 1 if total_audit else 0,
        "end": min(audit_start + audit_limit, total_audit),
        "allowed_limits": allowed_audit_limits,
    }

    active_tab = request.args.get("tab", "services")
    if active_tab not in {"services", "journals", "apply", "logs", "audit", "backups"}:
        active_tab = "services"
    return render_template(
        "operations.html",
        cfg=cfg,
        state=state,
        services=services,
        groups=groups,
        last=last,
        apply_runs=apply_runs,
        apply_pagination=apply_pagination,
        selected_unit=selected_unit,
        lines=app_log_lines,
        journal_lines_count=lines_count,
        journal=journal,
        backups=backups,
        backup_pagination=backup_pagination,
        audit_events=audit_events,
        audit_pagination=audit_pagination,
        active_tab=active_tab,
        user=current_user(),
    )


@app.route("/services")
@login_required
def services_page():
    args = request.args.to_dict(flat=True)
    args.setdefault("tab", "journals" if args.get("unit") else "services")
    return redirect(url_for("operations_center", **args))


@app.route("/services/group/<group>/restart", methods=["POST"])
@admin_required
def restart_service_group_form(group):
    cfg = load_config(CONFIG_PATH)
    res = restart_group(cfg, group)
    write_audit(cfg, "service_group_restart", actor=current_user().get("username"), details={"group": group, "units": res.get("units"), "ok": res.get("ok"), "stderr": res.get("stderr", "")[:500]})
    flash(f"Restart group {group}: {'OK' if res.get('ok') else 'FAILED'}")
    return redirect(request.referrer or url_for("operations_center", tab="services"))

@app.route("/logs")
@login_required
def logs_page():
    args = request.args.to_dict(flat=True)
    args.setdefault("tab", "logs")
    return redirect(url_for("operations_center", **args))


@app.route("/backups/<backup_id>/preview")
@login_required
def backup_preview(backup_id):
    """Read-only backup inspection and restore preview."""
    cfg = load_config(CONFIG_PATH)
    try:
        inspection = inspect_backup(cfg, backup_id)
        comparison = compare_backup_to_live(cfg, backup_id)
    except Exception as e:
        flash(f"Backup preview failed: {e}")
        return redirect(url_for("operations_center", tab="backups"))
    return render_template(
        "backup_preview.html",
        backup_id=backup_id,
        inspection=inspection,
        comparison=comparison,
        user=current_user(),
    )


@app.route("/backups/<backup_id>/download")
@login_required
def backup_download(backup_id):
    """Download a single backup directory as a zip archive."""
    cfg = load_config(CONFIG_PATH)
    inspection = inspect_backup(cfg, backup_id)
    backup_path = Path(inspection["path"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in backup_path.rglob("*"):
            if item.is_file():
                zf.write(item, item.relative_to(backup_path.parent))
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename=lqos_backup_{backup_id}.zip"},
    )


@app.route("/api/backups/<backup_id>/preview")
@login_required
def api_backup_preview(backup_id):
    cfg = load_config(CONFIG_PATH)
    try:
        return jsonify({"ok": True, "inspection": inspect_backup(cfg, backup_id), "comparison": compare_backup_to_live(cfg, backup_id)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/backups/retention-preview")
@login_required
def api_backup_retention_preview():
    cfg = load_config(CONFIG_PATH)
    return jsonify(retention_preview(cfg))


@app.route("/backups/<backup_id>/restore", methods=["POST"])
@admin_required
def restore(backup_id):
    cfg = load_config(CONFIG_PATH)
    try:
        restored = restore_backup(cfg, backup_id)
        write_audit(cfg, "backup_restored", actor=current_user().get("username"), details={"backup_id": backup_id, "restored": restored})
        flash(f"Restored backup {backup_id}: {', '.join(restored)}")
    except Exception as e:
        flash(f"Restore failed: {e}")
    return redirect(url_for("operations_center", tab="backups"))




@app.route("/backups/<backup_id>/delete", methods=["POST"])
@admin_required
def delete_backup_form(backup_id):
    cfg = load_config(CONFIG_PATH)
    try:
        deleted = delete_backup(cfg, backup_id)
        write_audit(cfg, "backup_deleted", actor=current_user().get("username"), details={"backup_id": backup_id, "deleted": deleted})
        flash(f"Deleted backup {backup_id}")
    except Exception as e:
        flash(f"Delete backup failed: {e}")
    return redirect(url_for("operations_center", tab="backups"))


@app.route("/download/csv")
@login_required
def download_csv():
    cfg = load_config(CONFIG_PATH)
    data = Path(cfg["paths"]["shaped_devices_csv"]).read_text(encoding="utf-8", errors="ignore") if Path(cfg["paths"]["shaped_devices_csv"]).exists() else ""
    return Response(data, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=ShapedDevices.csv"})


@app.route("/download/network")
@login_required
def download_network():
    cfg = load_config(CONFIG_PATH)
    data = Path(cfg["paths"]["network_json"]).read_text(encoding="utf-8", errors="ignore") if Path(cfg["paths"]["network_json"]).exists() else "{}\n"
    return Response(data, mimetype="application/json", headers={"Content-Disposition": "attachment; filename=network.json"})


@app.route("/api/status")
@login_required
def api_status():
    _cfg, state = get_status()
    state["sync_lock_running"] = scheduler.is_running()
    state["git_status"] = _git_status()
    return jsonify(state)


@app.route("/api/services/status")
@login_required
def api_services_status():
    return jsonify(all_service_status(load_config(CONFIG_PATH)))


@app.route("/api/services/<service>/restart", methods=["POST"])
@admin_required
def restart_service(service):
    cfg = load_config(CONFIG_PATH)
    if service not in allowed_units(cfg):
        return jsonify({"error": "not allowed"}), 400
    res = monitor_restart_service(cfg, service)
    try:
        write_audit(cfg, "api_service_restart", actor=current_user().get("username"), details={"service": service, "ok": res.get("ok")})
    except Exception:
        pass
    return jsonify(res)




@app.route("/api/services/<service>/journal")
@login_required
def api_service_journal(service):
    cfg = load_config(CONFIG_PATH)
    lines = int(request.args.get("lines", cfg.get("services", {}).get("journal_lines_default", 100)))
    return jsonify(journal_lines(cfg, service, lines=lines))


@app.route("/api/services/group/<group>/restart", methods=["POST"])
@admin_required
def api_restart_service_group(group):
    cfg = load_config(CONFIG_PATH)
    res = restart_group(cfg, group)
    write_audit(cfg, "api_service_group_restart", actor=current_user().get("username"), details={"group": group, "units": res.get("units"), "ok": res.get("ok")})
    return jsonify(res)


@app.route("/libreqos/force-apply", methods=["POST"])
@admin_required
def libreqos_force_apply():
    cfg = load_config(CONFIG_PATH)
    if scheduler.is_running():
        flash("Cannot force apply while a sync cycle is running.")
        return redirect(url_for("services_page"))
    lq = run_libreqos_update(cfg)
    state_path = cfg.get("paths", {}).get("runtime_state", "state/runtime_state.json")
    update_state(
        state_path,
        last_libreqos_apply_success=bool(lq.get("ok")),
        last_libreqos_apply_failed=not bool(lq.get("ok")),
        pending_libreqos_apply=not bool(lq.get("ok")),
        last_libreqos_apply_reason="force_apply",
        last_libreqos_exit_code=lq.get("exit_code"),
        last_libreqos_run_id=lq.get("run_id"),
    )
    write_audit(cfg, "libreqos_force_apply", actor=current_user().get("username"), details={"ok": lq.get("ok"), "exit_code": lq.get("exit_code"), "run_id": lq.get("run_id")})
    if lq.get("ok"):
        flash("LibreQoS force apply completed.")
        return redirect(url_for("operations_center", tab="apply"))
    flash("LibreQoS force apply failed. Opening the apply diagnostic page.")
    return redirect(url_for("libreqos_apply_detail", run_id=lq.get("run_id")))


@app.route("/api/libreqos/force-apply", methods=["POST"])
@admin_required
def api_libreqos_force_apply():
    cfg = load_config(CONFIG_PATH)
    if scheduler.is_running():
        return jsonify({"ok": False, "error": "sync_running"}), 409
    lq = run_libreqos_update(cfg)
    state_path = cfg.get("paths", {}).get("runtime_state", "state/runtime_state.json")
    update_state(
        state_path,
        last_libreqos_apply_success=bool(lq.get("ok")),
        last_libreqos_apply_failed=not bool(lq.get("ok")),
        pending_libreqos_apply=not bool(lq.get("ok")),
        last_libreqos_apply_reason="force_apply",
        last_libreqos_exit_code=lq.get("exit_code"),
        last_libreqos_run_id=lq.get("run_id"),
    )
    write_audit(cfg, "api_libreqos_force_apply", actor=current_user().get("username"), details={"ok": lq.get("ok"), "exit_code": lq.get("exit_code"), "run_id": lq.get("run_id")})
    return jsonify(lq)


@app.route("/api/libreqos/apply/history")
@login_required
def api_libreqos_apply_history():
    cfg = load_config(CONFIG_PATH)
    return jsonify(list_apply_runs(cfg, limit=int(request.args.get("limit", 20))))


@app.route("/api/libreqos/apply/last")
@login_required
def api_libreqos_apply_last():
    cfg = load_config(CONFIG_PATH)
    runs = list_apply_runs(cfg, limit=1)
    return jsonify(runs[0] if runs else {})


@app.route("/api/libreqos/apply/<run_id>/<stream>")
@login_required
def api_libreqos_apply_stream(run_id, stream):
    if stream not in ("stdout", "stderr"):
        return jsonify({"error": "invalid stream"}), 400
    cfg = load_config(CONFIG_PATH)
    return Response(read_apply_file(cfg, run_id, stream), mimetype="text/plain")


@app.route("/libreqos/apply/<run_id>")
@login_required
def libreqos_apply_detail(run_id):
    cfg = load_config(CONFIG_PATH)
    diagnostic = get_apply_diagnostic(cfg, run_id)
    return render_template("apply_detail.html", diagnostic=diagnostic, run_id=run_id, user=current_user())


@app.route("/api/libreqos/apply/<run_id>/diagnostic")
@login_required
def api_libreqos_apply_diagnostic(run_id):
    cfg = load_config(CONFIG_PATH)
    return jsonify(get_apply_diagnostic(cfg, run_id))


@app.route("/api/performance/last-cycle")
@login_required
def api_performance_last_cycle():
    _cfg, state = get_status()
    last = state.get("last_run") or {}
    return jsonify({"timings": last.get("timings", {}), "timeline": last.get("timeline", []), "duration_seconds": last.get("duration_seconds")})

@app.route("/api/rust-core/status")
@login_required
def api_rust_core_status():
    cfg = load_config(CONFIG_PATH)
    return jsonify(rust_core_status(cfg))


@app.route("/api/rust-core/self-test")
@login_required
def api_rust_core_self_test():
    cfg = load_config(CONFIG_PATH)
    strict = str(request.args.get("strict") or "").lower() in {"1", "true", "yes", "on"}
    return jsonify(rust_core_self_test(cfg, strict=strict))




@app.route("/api/rust-core/authority-readiness")
@login_required
def api_rust_core_authority_readiness():
    cfg = load_config(CONFIG_PATH)
    return jsonify(rust_authority_readiness(cfg))


@app.route("/api/rust-core/full-backend-readiness")
@login_required
def api_rust_core_full_backend_readiness():
    cfg = load_config(CONFIG_PATH)
    return jsonify(rust_full_backend_readiness(cfg))


@app.route("/api/rust-core/authority-pilot-plan")
@login_required
def api_rust_core_authority_pilot_plan():
    cfg = load_config(CONFIG_PATH)
    return jsonify(rust_authority_pilot_plan(cfg))




@app.route("/api/rust-core/routeros-collector-plan", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_collector_plan():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "source": request.args.get("source") or "",
            "include_disabled_routers": str(request.args.get("include_disabled_routers") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_build_routeros_collector_plan(cfg, payload))



@app.route("/api/rust-core/routeros-transport-session", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_transport_session():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "source": request.args.get("source") or "",
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_build_routeros_transport_session(cfg, payload))


@app.route("/api/rust-core/routeros-live-read-pilot", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_live_read_pilot():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "source": request.args.get("source") or "",
            "path": request.args.get("path") or "",
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_build_routeros_live_read_pilot(cfg, payload))



@app.route("/api/rust-core/routeros-read-pilot", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_read_pilot():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "source": request.args.get("source") or "",
            "path": request.args.get("path") or "",
            "adapter": request.args.get("adapter") or "fixture",
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "fixture_status": request.args.get("fixture_status") or "ok",
            "fixture_rows": [],
        }
    return jsonify(rust_run_routeros_read_pilot(cfg, payload))


@app.route("/api/rust-core/routeros-api-sentence", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_api_sentence():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "path": request.args.get("path") or "",
            "fields": [f.strip() for f in str(request.args.get("fields") or "").split(",") if f.strip()],
            "mode": request.args.get("mode") or "encode_only",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_build_routeros_api_sentence(cfg, payload))

@app.route("/api/rust-core/routeros-api-reply", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_api_reply():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "raw_text": request.args.get("raw_text") or "",
            "adapter": request.args.get("adapter") or "offline_words",
            "mode": request.args.get("mode") or "decode_only",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_decode_routeros_api_reply(cfg, payload))

@app.route("/api/rust-core/routeros-api-frame", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_api_frame():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "direction": request.args.get("direction") or "encode",
            "words": [w.strip() for w in str(request.args.get("words") or "").split(",") if w.strip()],
            "hex": request.args.get("hex") or "",
            "adapter": request.args.get("adapter") or "offline_frame",
            "mode": request.args.get("mode") or "offline",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_codec_routeros_api_frame(cfg, payload))


@app.route("/api/rust-core/routeros-offline-session", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_offline_session():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "path": request.args.get("path") or "/ppp/active",
            "fields": [f.strip() for f in str(request.args.get("fields") or "name,address").split(",") if f.strip()],
            "adapter": request.args.get("adapter") or "offline_fixture",
            "mode": request.args.get("mode") or "offline_session",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "fixture_rows": [],
        }
    return jsonify(rust_run_routeros_offline_session(cfg, payload))

@app.route("/api/rust-core/routeros-tcp-connectivity-pilot", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_tcp_connectivity_pilot():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "address": request.args.get("address") or "",
            "port": int(request.args.get("port") or 8728),
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_run_routeros_tcp_connectivity_pilot(cfg, payload))



@app.route("/api/rust-core/routeros-auth-plan", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_auth_plan():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "address": request.args.get("address") or "",
            "port": int(request.args.get("port") or 8728),
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
        }
    return jsonify(rust_build_routeros_auth_plan(cfg, payload))


@app.route("/api/rust-core/routeros-auth-handshake", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_auth_handshake():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "adapter": request.args.get("adapter") or "fixture",
            "mode": request.args.get("mode") or "fixture",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "fixture_reply_words": [w.strip() for w in str(request.args.get("fixture_reply_words") or "!done").split(",") if w.strip()],
        }
    return jsonify(rust_run_routeros_auth_handshake(cfg, payload))



@app.route("/api/rust-core/routeros-auth-session-contract", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_auth_session_contract():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "adapter": request.args.get("adapter") or "fixture",
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "fixture_reply_words": [w.strip() for w in str(request.args.get("fixture_reply_words") or "!done").split(",") if w.strip()],
        }
    return jsonify(rust_build_routeros_auth_session_contract(cfg, payload))


@app.route("/api/rust-core/routeros-authenticated-read-fixture", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_authenticated_read_fixture():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "adapter": request.args.get("adapter") or "fixture",
            "mode": request.args.get("mode") or "fixture",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "path": request.args.get("path") or "/ppp/active",
            "fields": [w.strip() for w in str(request.args.get("fields") or "name,address").split(",") if w.strip()],
            "fixture_reply_words": [w.strip() for w in str(request.args.get("fixture_reply_words") or "!done").split(",") if w.strip()],
            "fixture_rows": [],
        }
    return jsonify(rust_run_routeros_authenticated_read_fixture(cfg, payload))

@app.route("/api/rust-core/routeros-live-read-adapter-pilot", methods=["GET", "POST"])
@login_required
def api_rust_core_routeros_live_read_adapter_pilot():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "adapter": request.args.get("adapter") or "contract",
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "path": request.args.get("path") or "/ppp/active",
            "fields": [w.strip() for w in str(request.args.get("fields") or "name,address").split(",") if w.strip()],
            "fixture_reply_words": [w.strip() for w in str(request.args.get("fixture_reply_words") or "!done").split(",") if w.strip()],
        }
    return jsonify(rust_run_routeros_live_read_adapter_pilot(cfg, payload))

@app.route("/api/rust-core/collector-authority-pilot", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_pilot():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        payload = {
            "router": request.args.get("router") or "",
            "source": request.args.get("source") or "pppoe",
            "path": request.args.get("path") or "/ppp/active",
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_evaluate_collector_authority_pilot(cfg, payload))



@app.route("/api/rust-core/collector-authority-manifest", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_manifest():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "manifest",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_manifest(cfg, payload))

@app.route("/api/rust-core/collector-authority-selection", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_selection():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "dry_run",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_selection(cfg, payload))



@app.route("/api/rust-core/collector-authority-dry-run-bundle", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_dry_run_bundle():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "dry_run",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_dry_run_bundle(cfg, payload))

@app.route("/api/rust-core/run-cycle-rust-shadow-report", methods=["GET", "POST"])
@login_required
def api_rust_core_run_cycle_rust_shadow_report():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "shadow",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "include_rows": str(request.args.get("include_rows") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_run_cycle_rust_shadow_report(cfg, payload))


@app.route("/api/rust-core/collector-authority-activation-plan", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_activation_plan():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "plan",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "include_rows": str(request.args.get("include_rows") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_activation_plan(cfg, payload))



@app.route("/api/rust-core/collector-authority-runtime-contract", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_runtime_contract():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "include_rows": str(request.args.get("include_rows") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_runtime_contract(cfg, payload))



@app.route("/api/rust-core/collector-authority-switch-rehearsal", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_switch_rehearsal():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "include_rows": str(request.args.get("include_rows") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_switch_rehearsal(cfg, payload))


@app.route("/api/rust-core/collector-authority-pilot-execution-contract", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_pilot_execution_contract():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "include_rows": str(request.args.get("include_rows") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_build_collector_authority_pilot_execution_contract(cfg, payload))

@app.route("/api/rust-core/collector-authority-pilot-result", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_pilot_result():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "evaluate",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "error_count": int(request.args.get("pilot_error_count") or 0),
            },
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
        }
    return jsonify(rust_evaluate_collector_authority_pilot_result(cfg, payload))

@app.route("/api/rust-core/collector-authority-promotion-readiness", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_promotion_readiness():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "readiness",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_promotion_readiness(cfg, payload))


@app.route("/api/rust-core/collector-authority-promotion-execution-rehearsal", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_promotion_execution_rehearsal():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "rehearsal",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_promotion_readiness_confirmation": request.args.get("readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_promotion_execution_rehearsal(cfg, payload))



@app.route("/api/rust-core/collector-authority-promotion-commit-plan", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_promotion_commit_plan():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "plan",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_promotion_execution_confirmation": request.args.get("collector_authority_promotion_execution_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL",
            "collector_authority_promotion_readiness_confirmation": request.args.get("collector_authority_promotion_readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_promotion_commit_plan(cfg, payload))


@app.route("/api/rust-core/collector-authority-promotion-cutover-ledger", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_promotion_cutover_ledger():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "ledger",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_promotion_commit_confirmation": request.args.get("collector_authority_promotion_commit_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN",
            "collector_authority_promotion_execution_confirmation": request.args.get("collector_authority_promotion_execution_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL",
            "collector_authority_promotion_readiness_confirmation": request.args.get("collector_authority_promotion_readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "rollback_path": request.args.get("rollback_path") or "python_fallback_revert",
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_promotion_cutover_ledger(cfg, payload))


@app.route("/api/rust-core/collector-authority-production-freeze-gate", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_production_freeze_gate():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "freeze",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_promotion_cutover_confirmation": request.args.get("collector_authority_promotion_cutover_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER",
            "collector_authority_promotion_commit_confirmation": request.args.get("collector_authority_promotion_commit_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN",
            "collector_authority_promotion_execution_confirmation": request.args.get("collector_authority_promotion_execution_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL",
            "collector_authority_promotion_readiness_confirmation": request.args.get("collector_authority_promotion_readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "rollback_path": request.args.get("rollback_path") or "python_fallback_revert",
            "maintenance_window": request.args.get("maintenance_window") or "",
            "operator_acknowledged": str(request.args.get("operator_acknowledged") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_production_freeze_gate(cfg, payload))



@app.route("/api/rust-core/collector-authority-production-switch-contract", methods=["GET", "POST"])
@login_required
def api_rust_core_collector_authority_production_switch_contract():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "contract",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_production_freeze_confirmation": request.args.get("collector_authority_production_freeze_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_FREEZE_GATE",
            "collector_authority_promotion_cutover_confirmation": request.args.get("collector_authority_promotion_cutover_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_CUTOVER_LEDGER",
            "collector_authority_promotion_commit_confirmation": request.args.get("collector_authority_promotion_commit_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_COMMIT_PLAN",
            "collector_authority_promotion_execution_confirmation": request.args.get("collector_authority_promotion_execution_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_EXECUTION_REHEARSAL",
            "collector_authority_promotion_readiness_confirmation": request.args.get("collector_authority_promotion_readiness_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PROMOTION_READINESS",
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "rollback_path": request.args.get("rollback_path") or "python_fallback_revert",
            "maintenance_window": request.args.get("maintenance_window") or "",
            "operator_acknowledged": str(request.args.get("operator_acknowledged") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_collector_authority_production_switch_contract(cfg, payload))


@app.route("/api/rust-core/rust-backend-api-handoff-plan", methods=["GET", "POST"])
@login_required
def api_rust_core_rust_backend_api_handoff_plan():
    cfg = load_config(CONFIG_PATH)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
    else:
        raw_sources = request.args.get("sources") or request.args.get("source") or "pppoe"
        payload = {
            "router": request.args.get("router") or "",
            "sources": [s.strip() for s in str(raw_sources).split(",") if s.strip()],
            "mode": request.args.get("mode") or "plan",
            "execute": str(request.args.get("execute") or "").lower() in {"1", "true", "yes", "on"},
            "confirmation": request.args.get("confirmation") or "",
            "collector_authority_production_switch_confirmation": request.args.get("collector_authority_production_switch_confirmation") or "CONFIRM_COLLECTOR_AUTHORITY_PRODUCTION_SWITCH_CONTRACT",
            "webui_ux_unchanged": str(request.args.get("webui_ux_unchanged") or "").lower() in {"1", "true", "yes", "on"},
            "webui_static_assets_unchanged": str(request.args.get("webui_static_assets_unchanged") or "").lower() in {"1", "true", "yes", "on"},
            "api_route_parity": str(request.args.get("api_route_parity") or "").lower() in {"1", "true", "yes", "on"},
            "api_route_count": int(request.args.get("api_route_count") or 0),
            "successful_shadow_cycles": int(request.args.get("successful_shadow_cycles") or 0),
            "shadow_age_seconds": int(request.args.get("shadow_age_seconds") or 0),
            "rollback_path": request.args.get("rollback_path") or "python_fallback_revert",
            "maintenance_window": request.args.get("maintenance_window") or "",
            "operator_acknowledged": str(request.args.get("operator_acknowledged") or "").lower() in {"1", "true", "yes", "on"},
            "collector_parity": {"parity_score": float(request.args.get("parity_score") or 0), "verdict": request.args.get("parity_verdict") or "not_available"},
            "pilot_result": {
                "status": request.args.get("pilot_status") or "pilot_result_not_supplied",
                "error_count": int(request.args.get("pilot_error_count") or 0),
                "cleanup_attempted": str(request.args.get("cleanup_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "apply_attempted": str(request.args.get("apply_attempted") or "").lower() in {"1", "true", "yes", "on"},
                "write_attempted": str(request.args.get("write_attempted") or "").lower() in {"1", "true", "yes", "on"},
            },
        }
    return jsonify(rust_build_rust_backend_api_handoff_plan(cfg, payload))

@app.route("/api/rust-core/routeros-read-results", methods=["POST"])
@login_required
def api_rust_core_routeros_read_results():
    cfg = load_config(CONFIG_PATH)
    payload = request.get_json(silent=True) or {}
    return jsonify(rust_validate_routeros_read_results(cfg, payload))

@app.route("/api/rust-core/collector-bundle-shadow", methods=["POST"])
@login_required
def api_rust_core_collector_bundle_shadow():
    cfg = load_config(CONFIG_PATH)
    payload = request.get_json(silent=True) or {}
    return jsonify(rust_build_collector_circuit_bundle(cfg, payload))


@app.route("/api/rust-core/collector-bundle-parity", methods=["POST"])
@login_required
def api_rust_core_collector_bundle_parity():
    cfg = load_config(CONFIG_PATH)
    payload = request.get_json(silent=True) or {}
    return jsonify(rust_compare_collector_bundle_parity(cfg, payload))

@app.route("/api/rust-core/transaction-journal")
@login_required
def api_rust_core_transaction_journal():
    cfg = load_config(CONFIG_PATH)
    try:
        limit = int(request.args.get("limit") or 50)
        offset = int(request.args.get("offset") or 0)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_limit_or_offset"}), 400
    executed_raw = request.args.get("executed")
    executed = None
    if executed_raw is not None and str(executed_raw).strip() != "":
        executed = str(executed_raw).lower() in {"1", "true", "yes", "on"}
    include_event = str(request.args.get("include_event", "1")).lower() not in {"0", "false", "no", "off"}
    reverse = str(request.args.get("reverse", "1")).lower() not in {"0", "false", "no", "off"}
    return jsonify(rust_read_transaction_journal(
        cfg,
        limit=limit,
        offset=offset,
        journal_id=request.args.get("journal_id") or "",
        manifest_id=request.args.get("manifest_id") or "",
        transaction_status=request.args.get("transaction_status") or "",
        executed=executed,
        include_event=include_event,
        reverse=reverse,
    ))


@app.route("/api/rust-core/rollback-plan")
@login_required
def api_rust_core_rollback_plan():
    cfg = load_config(CONFIG_PATH)
    journal_id = request.args.get("journal_id") or ""
    manifest_id = request.args.get("manifest_id") or ""
    if not journal_id and not manifest_id:
        return jsonify({"ok": False, "error": "journal_id_or_manifest_id_required"}), 400
    return jsonify(rust_build_rollback_from_journal(cfg, journal_id=journal_id, manifest_id=manifest_id))




@app.route("/api/rust-core/rollback-execute", methods=["POST"])
@admin_required
def api_rust_core_rollback_execute():
    cfg = load_config(CONFIG_PATH)
    payload = request.get_json(silent=True) or {}
    journal_id = str(payload.get("journal_id") or request.args.get("journal_id") or "")
    manifest_id = str(payload.get("manifest_id") or request.args.get("manifest_id") or "")
    confirmation = str(payload.get("confirmation") or "")
    execute = bool(payload.get("execute", False))
    allow_checksum_mismatch = bool(payload.get("allow_checksum_mismatch", False))
    if not journal_id and not manifest_id and not isinstance(payload.get("rollback_manifest"), dict):
        return jsonify({"ok": False, "error": "journal_id_or_manifest_id_or_rollback_manifest_required"}), 400
    result = rust_execute_rollback(
        cfg,
        journal_id=journal_id,
        manifest_id=manifest_id,
        rollback_manifest=payload.get("rollback_manifest") if isinstance(payload.get("rollback_manifest"), dict) else None,
        execute=execute,
        confirmation=confirmation,
        allow_checksum_mismatch=allow_checksum_mismatch,
    )
    write_audit(cfg, "rust_rollback_execute_requested", actor=(current_user() or {}).get("username"), details={
        "journal_id": journal_id,
        "manifest_id": manifest_id,
        "execute_requested": execute,
        "executed": (result.get("result") or {}).get("executed"),
        "status": (result.get("result") or {}).get("status"),
    })
    return jsonify(result)


@app.route("/api/sync/run", methods=["POST"])
@admin_required
def api_sync_run():
    cfg = load_config(CONFIG_PATH)
    if _manual_sync_blocked(cfg):
        return jsonify({"ok": False, "blocked": True, "message": "manual sync disabled while scheduler auto-apply is active"}), 409
    ok = scheduler.run_now_background("manual")
    return jsonify({"ok": ok, "message": "sync started" if ok else "sync already running"})


@app.route("/api/sync/dry-run", methods=["POST"])
@login_required
def api_sync_dry_run():
    result = run_cycle(mode="dry_run", config_path=CONFIG_PATH).to_dict()
    return jsonify(result)


@app.route("/api/sync/apply-last-preview", methods=["POST"])
@admin_required
def api_sync_apply_last_preview():
    # Safety policy: do not apply stale preview; start a fresh manual sync.
    ok = scheduler.run_now_background("manual")
    return jsonify({"ok": ok, "message": "fresh apply sync started" if ok else "sync already running"})


@app.route("/api/sync/status")
@login_required
def api_sync_status_alias():
    return api_status()


@app.route("/api/sync/last-result")
@login_required
def api_sync_last_result():
    _cfg, state = get_status()
    return jsonify(state.get("last_run") or {})


@app.route("/api/scheduler/<action>", methods=["POST"])
@admin_required
def api_scheduler_action(action):
    cfg = load_config(CONFIG_PATH)
    sched = cfg.setdefault("scheduler", {})
    if action in ("enable", "resume"):
        allowed, blockers, wizard = _setup_wizard_allows_scheduler_enable(cfg)
        if not allowed:
            return jsonify({"ok": False, "blocked": True, "error": "setup_not_ready", "blockers": blockers, "wizard": wizard}), 409
        sched["enabled"] = True
        cfg.setdefault("setup_wizard", {})["first_run_completed"] = True
        save_config(cfg, CONFIG_PATH)
        return jsonify({"ok": True, "scheduler_enabled": True, "setup_complete": True})
    if action in ("disable", "pause"):
        sched["enabled"] = False
        save_config(cfg, CONFIG_PATH)
        return jsonify({"ok": True, "scheduler_enabled": False})
    if action == "run-now":
        if _manual_sync_blocked(cfg):
            return jsonify({"ok": False, "blocked": True, "message": "manual run disabled while scheduler auto-apply is active"}), 409
        ok = scheduler.run_now_background("manual")
        return jsonify({"ok": ok, "message": "sync started" if ok else "sync already running"})
    return jsonify({"ok": False, "error": "invalid scheduler action"}), 400


@app.route("/api/scheduler/intervals", methods=["PUT", "POST"])
@admin_required
def api_scheduler_intervals():
    cfg = load_config(CONFIG_PATH)
    sched = cfg.setdefault("scheduler", {})
    data = request.get_json(silent=True) or request.form.to_dict()
    allowed = ("active_interval_seconds", "idle_interval_seconds", "error_retry_interval_seconds", "apply_cooldown_seconds", "max_instances")
    for key in allowed:
        if key in data and data[key] not in (None, ""):
            sched[key] = int(data[key])
    save_config(cfg, CONFIG_PATH)
    return jsonify({"ok": True, "scheduler": sched})


@app.route("/api/config", methods=["GET", "PUT"])
@admin_required
def api_config():
    if request.method == "GET":
        return jsonify(load_config(CONFIG_PATH))
    try:
        data = request.get_json(force=True)
        save_config(data, CONFIG_PATH)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/circuits")
@login_required
def api_circuits():
    cfg = load_config(CONFIG_PATH)
    return jsonify(read_shaped_devices_csv(cfg["paths"]["shaped_devices_csv"]))


@app.route("/api/nodes")
@login_required
def api_nodes():
    cfg = load_config(CONFIG_PATH)
    return jsonify(read_network_json(cfg["paths"]["network_json"]))


@app.route("/api/generated/csv")
@login_required
def api_generated_csv():
    cfg = load_config(CONFIG_PATH)
    return Response(render_shaped_devices_csv(read_shaped_devices_csv(cfg["paths"]["shaped_devices_csv"])), mimetype="text/csv")


@app.route("/api/generated/network")
@login_required
def api_generated_network():
    cfg = load_config(CONFIG_PATH)
    return Response(render_network_json(read_network_json(cfg["paths"]["network_json"])), mimetype="application/json")


@app.route("/api/audit")
@login_required
def api_audit():
    cfg = load_config(CONFIG_PATH)
    return jsonify(tail_audit(cfg, limit=int(request.args.get("limit", 100))))


@app.route("/api/backups")
@login_required
def api_backups():
    return jsonify(list_backups(load_config(CONFIG_PATH)))


@app.route("/api/backups/<backup_id>/restore", methods=["POST"])
@admin_required
def api_restore_backup(backup_id):
    cfg = load_config(CONFIG_PATH)
    try:
        restored = restore_backup(cfg, backup_id)
        write_audit(cfg, "api_backup_restored", actor=current_user().get("username"), details={"backup_id": backup_id, "restored": restored})
        return jsonify({"ok": True, "restored": restored})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400




@app.route("/api/backups/<backup_id>/delete", methods=["POST"])
@admin_required
def api_delete_backup(backup_id):
    cfg = load_config(CONFIG_PATH)
    try:
        deleted = delete_backup(cfg, backup_id)
        write_audit(cfg, "api_backup_deleted", actor=current_user().get("username"), details={"backup_id": backup_id, "deleted": deleted})
        return jsonify({"ok": True, "deleted": deleted})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/download/log")
@login_required
def download_log():
    cfg = load_config(CONFIG_PATH)
    p = Path(cfg["paths"].get("log_file", "logs/lqosync.log"))
    data = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    return Response(data, mimetype="text/plain", headers={"Content-Disposition": "attachment; filename=lqosync.log"})

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "lqosync"})


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9202"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug, threaded=True)
