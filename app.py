import json
import os
import secrets
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, abort
from dotenv import load_dotenv

from auth.users import (
    authenticate, ensure_users_file, list_users, add_user, update_user,
    set_user_password, delete_user
)
from engine.config_loader import load_config, save_config, validate_config
from engine.run_cycle import run_cycle
from engine.state import load_state, update_state
from scheduler.runner import LQoSyncScheduler
from builders.shaped_devices import read_shaped_devices_csv, render_shaped_devices_csv
from builders.network_json import read_network_json, render_network_json, flatten_nodes
from applier.backup import list_backups
from applier.libreqos_runner import run_libreqos_update
from applier.rollback import restore_backup
from collectors.mikrotik_client import test_router_connection, connect_to_router, get_resource_data
from engine.audit import write_audit, tail_audit
from engine.policy_state import load_policy_state, save_policy_state, confirm_cleanup, dismiss_confirmation
from engine.setup_repair import compute_setup_repair_report, apply_policy_preset
from engine.setup_wizard import compute_setup_wizard, NETWORK_MODE_OPTIONS
from engine.policy_schema import grouped_policy_schema, policy_diff_from_preset, closest_preset, parse_policy_form, normalize_policies, POLICY_SCHEMA, get_by_path
from engine.config_simulator import simulate_config_change
from engine.reports import compute_operator_report, report_to_csv, report_to_markdown
from engine.config_schema import migrate_config_schema, validate_schema, CONFIG_SCHEMA_VERSION
from engine.release_integrity import compute_release_integrity, repair_config_defaults
from engine.lifecycle import lifecycle_summary, client_event_timeline
from engine.lifecycle_report import compute_lifecycle_report, lifecycle_report_to_csv, lifecycle_report_to_markdown
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


def admin_required(view_func):
    """Decorator for actions that require admin role."""
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "login_required"}), 401
            return redirect(url_for("login", next=request.path))
        if user.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "admin_required"}), 403
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


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
    return render_template("dashboard.html", cfg=cfg, state=state, services=services, git_status=_git_status(), config_errors=errors, config_warnings=warnings, user=current_user())


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
        sched["enabled"] = True
        message = "Scheduler enabled/resumed."
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
@admin_required
def settings_users():
    users = list_users(USERS_PATH)
    return render_template("settings_users.html", users=users, user=current_user())


@app.route("/settings/users/add", methods=["POST"])
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def api_users():
    return jsonify(list_users(USERS_PATH))


@app.route("/config", methods=["GET", "POST"])
@admin_required
def config_page():
    if request.method == "POST":
        raw = request.form.get("config_json", "")
        try:
            data = json.loads(raw)
            save_config(data, CONFIG_PATH)
            write_audit(load_config(CONFIG_PATH), "config_saved", actor=current_user().get("username"))
            flash("config.json saved.")
        except Exception as e:
            flash(f"Config save failed: {e}")
    cfg = load_config(CONFIG_PATH)
    errors, warnings = validate_config(cfg)
    schema_report = validate_schema(cfg)
    return render_template(
        "config.html",
        config_json=json.dumps(cfg, indent=2),
        config=cfg,
        config_errors=errors,
        config_warnings=warnings,
        schema_report=schema_report,
        schema_version=CONFIG_SCHEMA_VERSION,
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
    cfg, state = get_status()
    normalize_policies(cfg)
    pstate = load_policy_state(cfg)
    last = state.get("last_run") or state.get("last_dry_run") or {}
    decision = (last.get("diff") or {}).get("policy_decision") or pstate.get("last_policy_decision") or {}
    preset = request.args.get("compare") or (cfg.get("policies") or {}).get("mode") or "balanced"
    if preset == "custom":
        preset = "balanced"
    return render_template(
        "policy_center.html",
        cfg=cfg,
        state=state,
        policy_state=pstate,
        decision=decision,
        policy_schema=grouped_policy_schema(),
        policy_values={item["path"]: get_by_path(cfg, item["path"]) for item in POLICY_SCHEMA},
        preset_diff=policy_diff_from_preset(cfg, preset),
        preset_compare=preset,
        closest_preset=closest_preset(cfg),
        user=current_user(),
    )


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
    return redirect(url_for("policy_center"))


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
    return redirect(url_for("policy_center"))


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
    report = compute_lifecycle_report(pstate, status=status, source=source, search=search, code=code, limit=limit)
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
@admin_required
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
@admin_required
def api_release_integrity():
    return jsonify(compute_release_integrity(Path(__file__).resolve().parent))


@app.route("/updates")
@admin_required
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



@app.route("/services")
@login_required
def services_page():
    cfg, state = get_status()
    services = all_service_status(cfg)
    groups = allowed_groups(cfg)
    last = state.get("last_run") or {}
    apply_runs = list_apply_runs(cfg, limit=10)
    selected_unit = request.args.get("unit") or next(iter(services.keys()), "lqos_shaped_sync")
    lines = int(request.args.get("lines", cfg.get("services", {}).get("journal_lines_default", 100)))
    journal = journal_lines(cfg, selected_unit, lines=lines) if selected_unit else {"stdout": "", "stderr": ""}
    return render_template("services.html", cfg=cfg, state=state, services=services, groups=groups, last=last, apply_runs=apply_runs, selected_unit=selected_unit, journal=journal, user=current_user())


@app.route("/services/group/<group>/restart", methods=["POST"])
@admin_required
def restart_service_group_form(group):
    cfg = load_config(CONFIG_PATH)
    res = restart_group(cfg, group)
    write_audit(cfg, "service_group_restart", actor=current_user().get("username"), details={"group": group, "units": res.get("units"), "ok": res.get("ok"), "stderr": res.get("stderr", "")[:500]})
    flash(f"Restart group {group}: {'OK' if res.get('ok') else 'FAILED'}")
    return redirect(request.referrer or url_for("services_page"))

@app.route("/logs")
@login_required
def logs_page():
    cfg = load_config(CONFIG_PATH)
    log_file = Path(cfg["paths"].get("log_file", "logs/lqos_shaped_sync.log"))
    lines = []
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
    backups = list_backups(cfg)
    audit_events = tail_audit(cfg, limit=500)
    return render_template("logs.html", lines=lines, backups=backups, audit_events=audit_events, user=current_user())


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
    return redirect(url_for("logs_page"))


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
    )
    write_audit(cfg, "libreqos_force_apply", actor=current_user().get("username"), details={"ok": lq.get("ok"), "exit_code": lq.get("exit_code"), "run_id": lq.get("run_id")})
    flash("LibreQoS force apply completed." if lq.get("ok") else "LibreQoS force apply failed. Check Services & Journals logs.")
    return redirect(url_for("services_page"))


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


@app.route("/api/performance/last-cycle")
@login_required
def api_performance_last_cycle():
    _cfg, state = get_status()
    last = state.get("last_run") or {}
    return jsonify({"timings": last.get("timings", {}), "timeline": last.get("timeline", []), "duration_seconds": last.get("duration_seconds")})

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
        sched["enabled"] = True
        save_config(cfg, CONFIG_PATH)
        return jsonify({"ok": True, "scheduler_enabled": True})
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


@app.route("/download/log")
@login_required
def download_log():
    cfg = load_config(CONFIG_PATH)
    p = Path(cfg["paths"].get("log_file", "logs/lqos_shaped_sync.log"))
    data = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    return Response(data, mimetype="text/plain", headers={"Content-Disposition": "attachment; filename=lqos_shaped_sync.log"})

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "lqos_shaped_sync"})


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9202"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug, threaded=True)
