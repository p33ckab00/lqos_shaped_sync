import json
import os
from copy import deepcopy
from pathlib import Path
from applier.atomic_writer import atomic_write_text
from rules.network_mode import normalize_network_mode, VALID_NETWORK_MODES
from datetime import datetime, timezone
import shutil
from engine.policy_defaults import smart_policy_defaults, CLEANUP_ACTIONS, POLICY_PRESETS
from engine.config_schema import CONFIG_SCHEMA_VERSION, migrate_config_schema, validate_schema

DEFAULT_CONFIG = {
    "config_schema_version": CONFIG_SCHEMA_VERSION,
    "network_mode": "router_children",
    "flat_network": False,
    "no_parent": False,
    "preserve_network_config": False,
    "app": {
        "name": "LQoSync",
        "operation_mode": "automatic",  # automatic | manual
        "auto_apply": True,
        "dry_run_default": False,
        "backup_before_apply": False,  # optional storage-saving default; manual backups still available
        "backup_retention": 10,
        "file_drift_policy": "overwrite_with_backup",  # overwrite_with_backup | warn_only | block
    },
    "paths": {
        "shaped_devices_csv": "/opt/libreqos/src/ShapedDevices.csv",
        "network_json": "/opt/libreqos/src/network.json",
        "backup_dir": "/opt/lqosync/backups",
        "log_file": "/opt/lqosync/logs/lqosync.log",
        "runtime_state": "/opt/lqosync/state/runtime_state.json",
        "lock_file": "/opt/lqosync/state/lqosync.lock",
        "audit_log": "/opt/lqosync/logs/audit.jsonl",
        "libreqos_apply_log_dir": "/opt/lqosync/logs/libreqos_apply",
        "collector_cache": "/opt/lqosync/state/collector_cache.json",
        "policy_state": "/opt/lqosync/state/policy_state.json",
        "transaction_journal": "/opt/lqosync/logs/transaction_journal.jsonl",
    },
    "libreqos": {
        "cmd": "/opt/libreqos/src/LibreQoS.py",
        "args": ["--updateonly"],
        "working_dir": "/opt/libreqos/src",
        "timeout_seconds": 300,
        "run_only_when_files_changed": True,
        "retry_if_last_apply_failed": True,
        "sudo": True,
        "run_mode": "direct",
    },
    "scheduler": {
        "enabled": False,
        "active_interval_seconds": 30,
        "idle_interval_seconds": 120,
        "error_retry_interval_seconds": 30,
        "apply_cooldown_seconds": 20,
        "max_instances": 1,
    },
    "defaults": {
        "id_length": 8,
        "min_rate_percentage": 0.5,
        "default_pppoe_profile": "default",
        "default_pppoe_rate": "10M/10M",
        "default_dhcp_per_client_mbps": 15,
        "default_hotspot_per_client_mbps": 10,
        "duplicate_ip_policy": "warn_and_skip",
        "static_comment_value": "static",
    },
    "rust_core": {
        "enabled": True,
        "binary_path": "",
        "timeout_seconds": 10,
        "enforce_validation": False,
        "enforce_sync_plan": False,
        "fail_closed_when_enforced": True,
        "authority_mode": "shadow",  # shadow | enforce_blockers
        "prefer_daemon": False,
        "unix_socket": "/run/lqosync-core.sock",
        "transaction_authority": "preview",
        "execute_apply_manifest": False,
        "allow_rust_file_writes": False,
        "allow_rust_libreqos_apply": False,
        "self_test_on_status": False,
        "execute_rollback": False,
        "allow_rust_rollback_file_writes": False,
        "rollback_authority": "preview",
        "require_authority_readiness": False,
        "routeros_transport_authority": "plan_only",
        "allow_rust_routeros_live_reads": False,
        "allow_rust_routeros_credentials": False,
        "routeros_live_read_pilot": False,
        "routeros_live_read_timeout_seconds": 5,
        "routeros_read_pilot_adapter": "fixture",
        "allow_rust_routeros_fixture_reads": True,
        "routeros_tcp_connect_pilot": False,
        "allow_rust_routeros_tcp_connect": False,
        "routeros_tcp_connect_timeout_seconds": 3,
        "routeros_auth_pilot": False,
        "routeros_auth_timeout_seconds": 5,
        "routeros_auth_handshake_pilot": False,
        "allow_rust_routeros_auth_fixture": True,
        "routeros_auth_session_pilot": False,
        "allow_rust_routeros_session_state": False,
        "routeros_session_authority": "contract_only",
        "routeros_authenticated_read_pilot": False,
        "allow_rust_routeros_authenticated_fixture_reads": True,
        "routeros_authenticated_read_authority": "fixture_only",
        "routeros_live_read_adapter_pilot": False,
        "allow_rust_routeros_live_read_adapter": False,
        "routeros_live_read_adapter_authority": "contract_only",
        "rust_collector_authority_pilot": False,
        "allow_rust_collector_authority": False,
        "rust_collector_authority_sources": [],
        "collector_authority_mode": "python_authoritative",
        "collector_authority_require_parity_score": 99.99,
        "collector_authority_manifest_pilot": False,
        "allow_collector_authority_manifest": False,
        "collector_authority_dry_run_selection_pilot": False,
        "allow_collector_authority_dry_run_selection": False,
        "collector_authority_dry_run_bundle_pilot": False,
        "allow_collector_authority_dry_run_bundle": False,
        "run_cycle_rust_shadow_report_enabled": False,
        "run_cycle_rust_shadow_report_pilot": False,
        "run_cycle_rust_shadow_include_rows": False,
        "collector_authority_activation_pilot": False,
        "allow_collector_authority_activation": False,
        "collector_authority_activation_mode": "shadow_only",
        "collector_authority_require_python_fallback": True,
        "collector_authority_require_run_cycle_shadow": True,
        "collector_authority_min_shadow_cycles": 3,
        "collector_authority_successful_shadow_cycles": 0,
        "collector_authority_runtime_pilot": False,
        "allow_collector_authority_runtime_contract": False,
        "collector_authority_runtime_mode": "contract_only",
        "collector_authority_runtime_require_activation_plan": True,
        "collector_authority_runtime_require_python_fallback": True,
        "collector_authority_runtime_max_shadow_age_seconds": 900,
        "collector_authority_shadow_age_seconds": 0,
        "collector_authority_switch_rehearsal_pilot": False,
        "allow_collector_authority_switch_rehearsal": False,
        "collector_authority_switch_mode": "rehearsal_only",
        "collector_authority_switch_require_runtime_contract": True,
        "collector_authority_switch_require_python_fallback": True,
        "collector_authority_switch_require_manual_confirmation": True,
        "collector_authority_pilot_execution_pilot": False,
        "allow_collector_authority_pilot_execution_contract": False,
        "collector_authority_pilot_execution_mode": "contract_only",
        "collector_authority_pilot_execution_require_switch_rehearsal": True,
        "collector_authority_pilot_execution_require_python_fallback": True,
        "collector_authority_pilot_execution_require_manual_confirmation": True,
        "collector_authority_pilot_execution_max_shadow_age_seconds": 900,
        "collector_authority_pilot_result_evaluator_pilot": False,
        "allow_collector_authority_pilot_result_evaluation": False,
        "collector_authority_pilot_result_mode": "evaluate_only",
        "collector_authority_pilot_result_require_execution_contract": True,
        "collector_authority_pilot_result_require_python_fallback": True,
        "collector_authority_pilot_result_require_no_cleanup_apply": True,
        "collector_authority_pilot_result_require_parity": True,
        "collector_authority_pilot_result_max_shadow_age_seconds": 900,
        "collector_authority_promotion_readiness_pilot": False,
        "allow_collector_authority_promotion_readiness": False,
        "collector_authority_promotion_readiness_mode": "readiness_only",
        "collector_authority_promotion_require_pilot_result": True,
        "collector_authority_promotion_require_python_fallback": True,
        "collector_authority_promotion_require_manual_confirmation": True,
        "collector_authority_promotion_require_no_cleanup_apply": True,
        "collector_authority_promotion_max_shadow_age_seconds": 900,
        "collector_authority_promotion_execution_rehearsal_pilot": False,
        "allow_collector_authority_promotion_execution_rehearsal": False,
        "collector_authority_promotion_execution_mode": "rehearsal_only",
        "collector_authority_promotion_execution_require_readiness": True,
        "collector_authority_promotion_execution_require_python_fallback": True,
        "collector_authority_promotion_execution_require_manual_confirmation": True,
        "collector_authority_promotion_execution_require_no_cleanup_apply": True,
        "collector_authority_promotion_execution_max_shadow_age_seconds": 900,
        "collector_authority_promotion_commit_plan_pilot": False,
        "allow_collector_authority_promotion_commit_plan": False,
        "collector_authority_promotion_commit_mode": "plan_only",
        "collector_authority_promotion_commit_require_execution_rehearsal": True,
        "collector_authority_promotion_commit_require_python_fallback": True,
        "collector_authority_promotion_commit_require_manual_confirmation": True,
        "collector_authority_promotion_commit_require_no_cleanup_apply": True,
        "collector_authority_promotion_commit_max_shadow_age_seconds": 900,
        "collector_authority_promotion_cutover_ledger_pilot": False,
        "allow_collector_authority_promotion_cutover_ledger": False,
        "collector_authority_promotion_cutover_mode": "ledger_only",
        "collector_authority_promotion_cutover_require_commit_plan": True,
        "collector_authority_promotion_cutover_require_python_fallback": True,
        "collector_authority_promotion_cutover_require_manual_confirmation": True,
        "collector_authority_promotion_cutover_require_no_cleanup_apply": True,
        "collector_authority_promotion_cutover_require_rollback_path": True,
        "collector_authority_promotion_cutover_max_shadow_age_seconds": 900,
        "collector_authority_production_freeze_gate_pilot": False,
        "allow_collector_authority_production_freeze_gate": False,
        "collector_authority_production_freeze_mode": "freeze_only",
        "collector_authority_production_freeze_require_cutover_ledger": True,
        "collector_authority_production_freeze_require_python_fallback": True,
        "collector_authority_production_freeze_require_manual_confirmation": True,
        "collector_authority_production_freeze_require_no_cleanup_apply": True,
        "collector_authority_production_freeze_require_rollback_path": True,
        "collector_authority_production_freeze_require_maintenance_window": True,
        "collector_authority_production_freeze_require_operator_ack": True,
        "collector_authority_production_freeze_max_shadow_age_seconds": 900,
        "collector_authority_production_switch_contract_pilot": False,
        "allow_collector_authority_production_switch_contract": False,
        "collector_authority_production_switch_mode": "contract_only",
        "collector_authority_production_switch_require_freeze_gate": True,
        "collector_authority_production_switch_require_python_fallback": True,
        "collector_authority_production_switch_require_manual_confirmation": True,
        "collector_authority_production_switch_require_no_cleanup_apply": True,
        "collector_authority_production_switch_require_rollback_path": True,
        "collector_authority_production_switch_require_maintenance_window": True,
        "collector_authority_production_switch_require_operator_ack": True,
        "collector_authority_production_switch_max_shadow_age_seconds": 900,
        "rust_backend_api_handoff_plan_pilot": False,
        "allow_rust_backend_api_handoff_plan": False,
        "rust_backend_api_handoff_mode": "plan_only",
        "rust_backend_api_handoff_require_production_switch_contract": True,
        "rust_backend_api_handoff_require_python_backend_fallback": True,
        "rust_backend_api_handoff_require_manual_confirmation": True,
        "rust_backend_api_handoff_require_webui_compatibility": True,
        "rust_backend_api_handoff_require_route_parity": True,
        "rust_backend_api_handoff_require_no_side_effects": True,
        "rust_backend_api_handoff_max_shadow_age_seconds": 900,
        "rust_backend_scheduler_handoff_plan_pilot": False,
        "allow_rust_backend_scheduler_handoff_plan": False,
        "rust_backend_scheduler_handoff_mode": "plan_only",
        "rust_backend_scheduler_handoff_require_api_handoff": True,
        "rust_backend_scheduler_handoff_require_python_fallback": True,
        "rust_backend_scheduler_handoff_require_manual_confirmation": True,
        "rust_backend_scheduler_handoff_require_run_cycle_shadow": True,
        "rust_backend_scheduler_handoff_require_scheduler_parity": True,
        "rust_backend_scheduler_handoff_require_no_side_effects": True,
        "rust_backend_scheduler_handoff_max_shadow_age_seconds": 900,
        "rust_run_cycle_orchestrator_handoff_contract_pilot": False,
        "allow_rust_run_cycle_orchestrator_handoff_contract": False,
        "rust_run_cycle_orchestrator_handoff_mode": "contract_only",
        "rust_run_cycle_orchestrator_handoff_require_scheduler_handoff": True,
        "rust_run_cycle_orchestrator_handoff_require_python_fallback": True,
        "rust_run_cycle_orchestrator_handoff_require_manual_confirmation": True,
        "rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow": True,
        "rust_run_cycle_orchestrator_handoff_require_config_state_shadow": True,
        "rust_run_cycle_orchestrator_handoff_require_no_side_effects": True,
        "rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds": 900,
        "rust_config_state_authority_handoff_contract_pilot": False,
        "allow_rust_config_state_authority_handoff_contract": False,
        "rust_config_state_authority_handoff_mode": "contract_only",
        "rust_config_state_authority_handoff_require_run_cycle_orchestrator": True,
        "rust_config_state_authority_handoff_require_python_fallback": True,
        "rust_config_state_authority_handoff_require_manual_confirmation": True,
        "rust_config_state_authority_handoff_require_config_state_shadow": True,
        "rust_config_state_authority_handoff_require_atomic_writer_shadow": True,
        "rust_config_state_authority_handoff_require_transaction_journal_shadow": True,
        "rust_config_state_authority_handoff_require_audit_shadow": True,
        "rust_config_state_authority_handoff_require_rollback_shadow": True,
        "rust_config_state_authority_handoff_require_no_side_effects": True,
        "rust_config_state_authority_handoff_max_shadow_age_seconds": 900,
        "rust_live_collector_authority_handoff_contract_pilot": False,
        "allow_rust_live_collector_authority_handoff_contract": False,
        "rust_live_collector_authority_handoff_mode": "contract_only",
        "rust_live_collector_authority_handoff_require_config_state_authority": True,
        "rust_live_collector_authority_handoff_require_python_fallback": True,
        "rust_live_collector_authority_handoff_require_manual_confirmation": True,
        "rust_live_collector_authority_handoff_require_live_collector_shadow": True,
        "rust_live_collector_authority_handoff_require_routeros_adapter_shadow": True,
        "rust_live_collector_authority_handoff_require_collector_parity": True,
        "rust_live_collector_authority_handoff_require_no_side_effects": True,
        "rust_live_collector_authority_handoff_max_shadow_age_seconds": 900,
        "rust_circuit_builder_authority_handoff_contract_pilot": False,
        "allow_rust_circuit_builder_authority_handoff_contract": False,
        "rust_circuit_builder_authority_handoff_mode": "contract_only",
        "rust_circuit_builder_authority_handoff_require_live_collector_authority": True,
        "rust_circuit_builder_authority_handoff_require_python_fallback": True,
        "rust_circuit_builder_authority_handoff_require_manual_confirmation": True,
        "rust_circuit_builder_authority_handoff_require_circuit_shadow": True,
        "rust_circuit_builder_authority_handoff_require_shaped_devices_parity": True,
        "rust_circuit_builder_authority_handoff_require_parent_integrity": True,
        "rust_circuit_builder_authority_handoff_require_no_side_effects": True,
        "rust_circuit_builder_authority_handoff_max_shadow_age_seconds": 900,
        "rust_sync_engine_authority_handoff_contract_pilot": False,
        "allow_rust_sync_engine_authority_handoff_contract": False,
        "rust_sync_engine_authority_handoff_mode": "contract_only",
        "rust_sync_engine_authority_handoff_require_circuit_builder_authority": True,
        "rust_sync_engine_authority_handoff_require_python_fallback": True,
        "rust_sync_engine_authority_handoff_require_manual_confirmation": True,
        "rust_sync_engine_authority_handoff_require_sync_plan_shadow": True,
        "rust_sync_engine_authority_handoff_require_diff_parity": True,
        "rust_sync_engine_authority_handoff_require_apply_manifest_preview": True,
        "rust_sync_engine_authority_handoff_require_cleanup_safety": True,
        "rust_sync_engine_authority_handoff_require_no_side_effects": True,
        "rust_sync_engine_authority_handoff_max_shadow_age_seconds": 900,
        "rust_apply_journal_rollback_authority_handoff_contract_pilot": False,
        "allow_rust_apply_journal_rollback_authority_handoff_contract": False,
        "rust_apply_journal_rollback_authority_handoff_mode": "contract_only",
        "rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority": True,
        "rust_apply_journal_rollback_authority_handoff_require_python_fallback": True,
        "rust_apply_journal_rollback_authority_handoff_require_manual_confirmation": True,
        "rust_apply_journal_rollback_authority_handoff_require_apply_shadow": True,
        "rust_apply_journal_rollback_authority_handoff_require_journal_shadow": True,
        "rust_apply_journal_rollback_authority_handoff_require_rollback_shadow": True,
        "rust_apply_journal_rollback_authority_handoff_require_audit_shadow": True,
        "rust_apply_journal_rollback_authority_handoff_require_no_side_effects": True,
        "rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds": 900,
        "rust_backend_service_runtime_handoff_contract_pilot": False,
        "allow_rust_backend_service_runtime_handoff_contract": False,
        "rust_backend_service_runtime_handoff_mode": "contract_only",
        "rust_backend_service_runtime_handoff_require_apply_journal_rollback_authority": True,
        "rust_backend_service_runtime_handoff_require_python_fallback": True,
        "rust_backend_service_runtime_handoff_require_manual_confirmation": True,
        "rust_backend_service_runtime_handoff_require_route_parity": True,
        "rust_backend_service_runtime_handoff_require_static_assets": True,
        "rust_backend_service_runtime_handoff_require_service_supervision": True,
        "rust_backend_service_runtime_handoff_require_api_shadow": True,
        "rust_backend_service_runtime_handoff_require_no_side_effects": True,
        "rust_backend_service_runtime_handoff_max_shadow_age_seconds": 900,
        "full_rust_backend_production_readiness_contract_pilot": False,
        "allow_full_rust_backend_production_readiness_contract": False,
        "full_rust_backend_production_readiness_mode": "contract_only",
        "full_rust_backend_production_readiness_require_service_runtime": True,
        "full_rust_backend_production_readiness_require_python_fallback": True,
        "full_rust_backend_production_readiness_require_manual_confirmation": True,
        "full_rust_backend_production_readiness_require_webui_unchanged": True,
        "full_rust_backend_production_readiness_require_operator_final_review": True,
        "full_rust_backend_production_readiness_require_no_side_effects": True,
        "full_rust_backend_production_readiness_max_shadow_age_seconds": 900,
        "full_rust_backend_cutover_plan_pilot": False,
        "allow_full_rust_backend_cutover_plan": False,
        "full_rust_backend_cutover_mode": "plan_only",
        "full_rust_backend_cutover_require_production_readiness": True,
        "full_rust_backend_cutover_require_python_fallback": True,
        "full_rust_backend_cutover_require_manual_confirmation": True,
        "full_rust_backend_cutover_require_webui_unchanged": True,
        "full_rust_backend_cutover_require_rollback_path": True,
        "full_rust_backend_cutover_require_operator_approval": True,
        "full_rust_backend_cutover_require_no_side_effects": True,
        "full_rust_backend_cutover_max_shadow_age_seconds": 900,
        "full_rust_backend_cutover_execution_contract_pilot": False,
        "allow_full_rust_backend_cutover_execution_contract": False,
        "full_rust_backend_cutover_execution_mode": "contract_only",
        "full_rust_backend_cutover_execution_require_cutover_plan": True,
        "full_rust_backend_cutover_execution_require_python_fallback": True,
        "full_rust_backend_cutover_execution_require_manual_confirmation": True,
        "full_rust_backend_cutover_execution_require_webui_unchanged": True,
        "full_rust_backend_cutover_execution_require_rollback_path": True,
        "full_rust_backend_cutover_execution_require_operator_ack": True,
        "full_rust_backend_cutover_execution_require_no_side_effects": True,
        "full_rust_backend_cutover_execution_max_shadow_age_seconds": 900,
        "python_backend_retirement_plan_pilot": False,
        "allow_python_backend_retirement_plan": False,
        "python_backend_retirement_mode": "plan_only",
        "python_backend_retirement_require_cutover_execution_contract": True,
        "python_backend_retirement_require_python_fallback": True,
        "python_backend_retirement_require_manual_confirmation": True,
        "python_backend_retirement_require_webui_unchanged": True,
        "python_backend_retirement_require_rollback_path": True,
        "python_backend_retirement_require_operator_ack": True,
        "python_backend_retirement_require_no_side_effects": True,
        "python_backend_retirement_max_shadow_age_seconds": 900,
        "rust_backend_production_enablement_contract_pilot": False,
        "allow_rust_backend_production_enablement_contract": False,
        "rust_backend_production_enablement_mode": "contract_only",
        "rust_backend_production_enablement_require_python_retirement_plan": True,
        "rust_backend_production_enablement_require_python_fallback": True,
        "rust_backend_production_enablement_require_manual_confirmation": True,
        "rust_backend_production_enablement_require_webui_unchanged": True,
        "rust_backend_production_enablement_require_rollback_path": True,
        "rust_backend_production_enablement_require_operator_ack": True,
        "rust_backend_production_enablement_require_no_side_effects": True,
        "rust_backend_production_enablement_max_shadow_age_seconds": 900,
        "python_backend_removal_execution_contract_pilot": False,
        "allow_python_backend_removal_execution_contract": False,
        "python_backend_removal_execution_mode": "contract_only",
        "python_backend_removal_execution_require_rust_enablement_contract": True,
        "python_backend_removal_execution_require_python_fallback": True,
        "python_backend_removal_execution_require_manual_confirmation": True,
        "python_backend_removal_execution_require_webui_unchanged": True,
        "python_backend_removal_execution_require_rollback_path": True,
        "python_backend_removal_execution_require_operator_ack": True,
        "python_backend_removal_execution_require_no_side_effects": True,
        "python_backend_removal_execution_max_shadow_age_seconds": 900,
        "full_rust_backend_removal_rehearsal_pilot": False,
        "allow_full_rust_backend_removal_rehearsal": False,
        "full_rust_backend_removal_rehearsal_mode": "rehearsal_only",
        "full_rust_backend_removal_rehearsal_require_removal_execution_contract": True,
        "full_rust_backend_removal_rehearsal_require_python_fallback": True,
        "full_rust_backend_removal_rehearsal_require_manual_confirmation": True,
        "full_rust_backend_removal_rehearsal_require_webui_unchanged": True,
        "full_rust_backend_removal_rehearsal_require_rollback_path": True,
        "full_rust_backend_removal_rehearsal_require_operator_ack": True,
        "full_rust_backend_removal_rehearsal_require_no_side_effects": True,
        "full_rust_backend_removal_rehearsal_max_shadow_age_seconds": 900,
        "full_rust_backend_production_cutover_pilot": False,
        "allow_full_rust_backend_production_cutover": False,
        "full_rust_backend_production_cutover_mode": "operator_supervised",
        "full_rust_backend_production_cutover_require_removal_rehearsal": True,
        "full_rust_backend_production_cutover_require_manual_confirmation": True,
        "full_rust_backend_production_cutover_require_webui_unchanged": True,
        "full_rust_backend_production_cutover_require_rollback_path": True,
        "full_rust_backend_production_cutover_require_operator_ack": True,
        "full_rust_backend_production_cutover_require_server_tests": True,
        "full_rust_backend_production_cutover_require_python_fallback_backup": True,
        "full_rust_backend_production_cutover_max_shadow_age_seconds": 900,
        "full_rust_backend_production_verifier_pilot": False,
        "allow_full_rust_backend_production_verifier": False,
        "full_rust_backend_production_verifier_mode": "verify_only",
        "full_rust_backend_production_verifier_require_cutover": True,
        "full_rust_backend_production_verifier_require_webui_unchanged": True,
        "full_rust_backend_production_verifier_require_runtime_health": True,
        "full_rust_backend_production_verifier_require_rollback_package": True,
        "full_rust_backend_production_verifier_require_manual_confirmation": True,
        "full_rust_backend_production_verifier_require_operator_ack": True,
        "full_rust_backend_production_verifier_require_server_tests": True,
        "full_rust_backend_production_verifier_max_shadow_age_seconds": 900,
        "full_rust_backend_post_retirement_verifier_pilot": False,
        "allow_full_rust_backend_post_retirement_verifier": False,
        "full_rust_backend_post_retirement_verifier_mode": "verify_only",
        "full_rust_backend_post_retirement_require_production_verifier": True,
        "full_rust_backend_post_retirement_require_runtime_health": True,
        "full_rust_backend_post_retirement_require_python_retired": True,
        "full_rust_backend_post_retirement_require_webui_unchanged": True,
        "full_rust_backend_post_retirement_require_rollback_package": True,
        "full_rust_backend_post_retirement_require_server_tests": True,
        "full_rust_backend_post_retirement_require_manual_confirmation": True,
        "full_rust_backend_post_retirement_require_operator_ack": True,
        "full_rust_backend_post_retirement_max_shadow_age_seconds": 900,
        "full_rust_backend_steady_state_guard_pilot": False,
        "allow_full_rust_backend_steady_state_guard": False,
        "full_rust_backend_steady_state_guard_mode": "guard_only",
        "full_rust_backend_steady_state_require_post_retirement_verifier": True,
        "full_rust_backend_steady_state_require_runtime_health": True,
        "full_rust_backend_steady_state_require_no_python_drift": True,
        "full_rust_backend_steady_state_require_webui_unchanged": True,
        "full_rust_backend_steady_state_require_rollback_package": True,
        "full_rust_backend_steady_state_require_server_tests": True,
        "full_rust_backend_steady_state_require_manual_confirmation": True,
        "full_rust_backend_steady_state_require_operator_ack": True,
        "full_rust_backend_steady_state_max_shadow_age_seconds": 900,
        "full_rust_backend_production_drift_monitor_pilot": False,
        "allow_full_rust_backend_production_drift_monitor": False,
        "full_rust_backend_production_drift_monitor_mode": "monitor_only",
        "full_rust_backend_drift_monitor_require_steady_state_guard": True,
        "full_rust_backend_drift_monitor_require_runtime_health": True,
        "full_rust_backend_drift_monitor_require_no_python_drift": True,
        "full_rust_backend_drift_monitor_require_webui_unchanged": True,
        "full_rust_backend_drift_monitor_require_rollback_package": True,
        "full_rust_backend_drift_monitor_require_server_tests": True,
        "full_rust_backend_drift_monitor_require_manual_confirmation": True,
        "full_rust_backend_drift_monitor_require_operator_ack": True,
        "full_rust_backend_drift_monitor_max_shadow_age_seconds": 900,
        "full_rust_backend_production_audit_sentinel_pilot": False,
        "allow_full_rust_backend_production_audit_sentinel": False,
        "full_rust_backend_production_audit_sentinel_mode": "sentinel_only",
        "full_rust_backend_audit_sentinel_require_drift_monitor": True,
        "full_rust_backend_audit_sentinel_require_audit_trail": True,
        "full_rust_backend_audit_sentinel_require_journal_visibility": True,
        "full_rust_backend_audit_sentinel_require_rollback_visibility": True,
        "full_rust_backend_audit_sentinel_require_webui_unchanged": True,
        "full_rust_backend_audit_sentinel_require_server_tests": True,
        "full_rust_backend_audit_sentinel_require_manual_confirmation": True,
        "full_rust_backend_audit_sentinel_require_operator_ack": True,
        "full_rust_backend_audit_sentinel_max_shadow_age_seconds": 900,
    },
    "collector": {
        "selective_fields": True,
        "pppoe": {
            "read_active": True,
            "read_secrets": True,
            "read_profiles": True,
        },
        "dhcp": {
            "lease_mode": "permissive",
            "read_server_metadata": True,
        },
        "hotspot": {
            "enhanced_metadata": True,
        },
    },
    "preflight": {
        "enabled": True,
        "duplicate_ip_policy": "warn_and_skip",
        "missing_parent_policy": "block",
        "invalid_bandwidth_policy": "block",
    },
    "ui": {
        "refresh_seconds": 5,
        "show_raw_json_editor": True,
        "default_theme": "light",
        "privacy_mode_available": True,
    },
    "topology": {
        "allow_deep_hierarchy": True,
        "allow_custom_edit": True,
        "show_virtual_nodes": True,
        "validate_before_save": True,
    },
    "insights": {
        "enabled": True,
        "show_recommendations": True,
        "show_data_quality": True,
        "show_backup_readiness": True,
        "show_anomaly_detection": True,
        "show_warning_explanations": True,
        "fallback_speed_review_limit": 100,
    },
    "monitoring": {
        "enabled": True,
        "source_health_enabled": True,
        "performance_trends_enabled": True,
        "slowdown_multiplier": 5,
        "trend_sample_limit": 100,
        "show_health_nav": True,
    },
    "notifications": {
        "enabled": True,
        "internal_center_enabled": True,
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "base_url": "",
            "parse_mode": "HTML",
            "timeout_seconds": 10,
            "notify_levels": ["critical", "warning"],
            "minimum_interval_seconds": 60,
            "dedupe_window_minutes": 60,
            "max_items_per_digest": 10,
            "send_digest": True,
            "send_individual": False,
            "notify_on_apply_failed": True,
            "notify_on_policy_block": True,
            "notify_on_confirmation_required": True,
            "notify_on_update_available": True,
            "notify_on_source_health_warning": True,
            "notify_on_performance_slow": True
        }
    },
    "setup_repair": {
        "enabled": True,
        "read_only_by_default": True,
        "show_guided_setup": True,
        "show_repair_commands": True,
        "allow_policy_preset_apply": True,
        "doctor_command": "sudo CONFIG_PATH=/opt/libreqos/src/config.json python3 /opt/lqosync/scripts/doctor.py",
    },
    "setup_wizard": {
        "enabled": True,
        "first_run_completed": False,
        "redirect_after_login_until_complete": True,
        "show_dashboard_banner_until_complete": True,
        "scheduler_enable_requires_dry_run": True,
        "scheduler_enable_requires_no_failed_checks": True,
        "scheduler_enable_requires_router_and_source": True,
        "allow_force_scheduler_enable": False,
        "recommended_start_page": "/setup-wizard",
    },
    "config_validation": {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "validate_before_save": True,
        "simulate_before_save": True,
        "show_config_health": True,
        "block_save_on_schema_errors": True,
    },
    "package_quality": {
        "enabled": True,
        "check_routes_templates": True,
        "check_config_defaults": True,
        "show_in_setup_repair": True,
        "doctor_script": "/opt/lqosync/scripts/lqosync-doctor.sh",
        "release_check_script": "/opt/lqosync/scripts/release_check.py",
        "regression_check_script": "/opt/lqosync/scripts/regression_check.py",
        "config_migration_check_script": "/opt/lqosync/scripts/config_migration_check.py",
        "policy_path_audit_script": "/opt/lqosync/scripts/policy_path_audit.py",
        "stable_release_check_script": "/opt/lqosync/scripts/stable_release_check.py",
        "ui_wiring_audit_script": "/opt/lqosync/scripts/ui_wiring_audit.py",
        "cleanup_stale_files_script": "/opt/lqosync/scripts/cleanup_stale_files.py"
    },
    "stable_release": {
        "target": "v2.70 Stable Release Candidate",
        "feature_freeze": True,
        "allow_new_sidebar_modules": False,
        "require_release_check": True,
        "require_regression_check": True,
        "require_config_migration_check": True,
        "require_policy_path_audit": True,
        "require_stable_release_check": True,
        "compatibility_routes": ["/health", "/services", "/logs", "/policy", "/notifications", "/routers"]
    },
    "access_control": {
        "enabled": True,
        "roles": {
            "owner": "Full control including users, updates, setup/repair, config, policies, backups, and live actions.",
            "admin": "Config, policies, scheduler, backups, operations, and live apply actions except owner-only user/update controls.",
            "operator": "Monitoring, dry-run/reports, lifecycle, operations inspection, and documentation access.",
            "viewer": "Read-only dashboards, devices, reports, docs, and status pages."
        },
        "owner_required_routes": ["/settings/users", "/updates", "/setup-repair/repair-defaults", "/api/release/integrity"],
        "admin_required_summary": "Config, policy, scheduler, backup restore/delete, service restart, force apply, and setup actions require admin or owner.",
        "operator_summary": "Operators can view operational pages and run dry-run style previews, but cannot change production configuration or perform destructive actions."
    },
    "policies": smart_policy_defaults(),
    "services": {
        # Required/current LibreQoS + LQoSync units. lqos_node_manager is not
        # required on newer LibreQoS installs and is tracked separately as a
        # legacy optional Web UI unit.
        "units": ["lqosd", "lqos_scheduler", "lqosync"],
        "legacy_optional_units": ["lqos_node_manager"],
        "show_legacy_optional_not_installed": False,
        "unit_metadata": {
            "lqosd": {
                "label": "LibreQoS daemon",
                "role": "required",
                "note": "Main LibreQoS daemon; on newer LibreQoS installs this also serves the Web UI on port 9123."
            },
            "lqos_scheduler": {
                "label": "LibreQoS scheduler",
                "role": "required",
                "note": "Runs LibreQoS scheduler/integration refresh jobs."
            },
            "lqos_node_manager": {
                "label": "Legacy Web UI service",
                "role": "legacy_optional",
                "note": "Older LibreQoS installs only. Newer LibreQoS usually exposes Web UI through lqosd, so this unit may be not installed."
            },
            "lqosync": {
                "label": "LQoSync service",
                "role": "required",
                "note": "LQoSync dashboard, scheduler, and MikroTik-to-LibreQoS sync engine."
            }
        },
        "restart_groups": {
            "libreqos_core": ["lqosd", "lqos_scheduler"]
        },
        "journal_lines_default": 100
    },
    "routers": [],
}


def deep_merge(base, override):
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path=None):
    path = path or os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
    p = Path(path)
    if not p.exists():
        cfg = deepcopy(DEFAULT_CONFIG)
        normalize_config(cfg)
        return cfg
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    cfg = deep_merge(DEFAULT_CONFIG, raw)
    normalize_config(cfg)
    return cfg


def _backup_config_file(path: str):
    p = Path(path)
    if not p.exists():
        return None
    backup_dir = p.parent / "config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"config.json.{stamp}.bak"
    shutil.copy2(p, dst)
    return str(dst)


def save_config(config, path=None, backup_existing=True):
    path = path or os.getenv("CONFIG_PATH") or "/opt/libreqos/src/config.json"
    cfg = deep_merge(DEFAULT_CONFIG, config)
    normalize_config(cfg)
    errors, _warnings = validate_config(cfg)
    if errors:
        raise ValueError("Invalid config: " + "; ".join(errors))
    if backup_existing:
        try:
            _backup_config_file(path)
        except Exception:
            # Config save should not fail just because a safety backup failed.
            pass
    text = json.dumps(cfg, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    atomic_write_text(path, text)
    try:
        Path(path).chmod(0o600)
    except Exception:
        pass


def _floatish(value, default):
    try:
        return float(value)
    except Exception:
        return default


def normalize_config(cfg):
    cfg.setdefault("app", {})
    cfg.setdefault("paths", {})
    cfg.setdefault("libreqos", {})
    cfg.setdefault("scheduler", {})
    cfg.setdefault("defaults", {})
    cfg.setdefault("collector", {})
    cfg.setdefault("rust_core", {})
    cfg.setdefault("topology", {})
    cfg.setdefault("preflight", {})
    cfg.setdefault("policies", {})
    cfg.setdefault("routers", [])
    cfg.setdefault("config_validation", {})

    # Merge nested defaults without dropping user values.
    merged = deep_merge(DEFAULT_CONFIG, cfg)
    cfg.clear(); cfg.update(merged)
    migrated, _migration_notes = migrate_config_schema(cfg)
    cfg.clear(); cfg.update(migrated)

    paths = cfg.setdefault("paths", {})
    paths.setdefault("transaction_journal", "/opt/lqosync/logs/transaction_journal.jsonl")

    # Network mode is the user-facing layout selector. Legacy flags are derived
    # automatically so old config.json files keep working.
    normalize_network_mode(cfg)

    # LibreQoS.py uses relative files internally, so working_dir must be set
    # explicitly. Preserve operator value if absolute; otherwise normalize.
    lib = cfg.setdefault("libreqos", {})
    wd = str(lib.get("working_dir") or "").strip()
    if not wd or not Path(wd).is_absolute():
        lib["working_dir"] = str(Path(os.getenv("LQOSYNC_LIBREQOS_SRC") or "/opt/libreqos/src"))
    lib.setdefault("retry_if_last_apply_failed", True)
    install_mode = (os.getenv("LQOSYNC_INSTALL_MODE") or "").strip().lower()
    force_direct = str(os.getenv("LQOSYNC_FORCE_DIRECT") or "").strip().lower() in {"1", "true", "yes", "on"}
    running_in_container = Path("/.dockerenv").exists() or bool(os.getenv("container"))
    # Bare-metal/systemd is the priority deployment. If LQoSync is not running
    # in a container, host_nsenter is invalid and must not survive through config
    # normalization. This protects live installs even when an old config.json or
    # config.json.example contained Docker-specific values.
    if install_mode in {"baremetal", "host", "systemd"} or force_direct or (install_mode not in {"docker", "container"} and not running_in_container):
        lib["run_mode"] = "direct"
        lib["sudo"] = True

    # Normalize LibreQoS service unit names. Older builds used lqos/lqosd_scheduler,
    # but the correct/common LibreQoS units for status/restart are lqosd and
    # lqos_scheduler, e.g. `sudo systemctl status lqosd lqos_scheduler`.
    svc = cfg.setdefault("services", {})
    aliases = {"lqos": "lqosd", "lqosd_scheduler": "lqos_scheduler"}
    units = svc.get("units") or DEFAULT_CONFIG["services"]["units"]
    normalized_units = []
    for unit in units:
        unit = aliases.get(str(unit).strip(), str(unit).strip())
        if unit and unit not in normalized_units:
            normalized_units.append(unit)
    # Add and normalize optional/legacy service metadata. Keep legacy units out
    # of the required list by default so fresh installs do not show
    # lqos_node_manager as a required/failed service.
    legacy_optional = svc.get("legacy_optional_units") or DEFAULT_CONFIG["services"].get("legacy_optional_units", [])
    svc["legacy_optional_units"] = []
    for unit in legacy_optional:
        unit = aliases.get(str(unit).strip(), str(unit).strip())
        if unit and unit not in svc["legacy_optional_units"]:
            svc["legacy_optional_units"].append(unit)
    svc.setdefault("show_legacy_optional_not_installed", DEFAULT_CONFIG["services"].get("show_legacy_optional_not_installed", False))
    svc.setdefault("unit_metadata", {})
    svc["unit_metadata"] = deep_merge(DEFAULT_CONFIG["services"].get("unit_metadata", {}), svc.get("unit_metadata", {}))
    # If an old config inherited lqos_node_manager from previous defaults, it is
    # still allowed/auto-detected, but treated as legacy optional in UI/status.
    svc["units"] = normalized_units
    groups = svc.get("restart_groups") or DEFAULT_CONFIG["services"]["restart_groups"]
    normalized_groups = {}
    for name, group_units in groups.items():
        clean = []
        for unit in group_units or []:
            unit = aliases.get(str(unit).strip(), str(unit).strip())
            if unit and unit not in clean:
                clean.append(unit)
        normalized_groups[name] = clean
    svc["restart_groups"] = normalized_groups

    for router in cfg.get("routers", []):
        router.setdefault("enabled", True)
        router.setdefault("name", "Router")
        router.setdefault("address", "")
        router.setdefault("port", 8728)
        router.setdefault("username", "")
        router.setdefault("password", "")
        router.setdefault("root_download_mbps", cfg.get("ROOT_DOWNLOAD_MBPS", 115))
        router.setdefault("root_upload_mbps", cfg.get("ROOT_UPLOAD_MBPS", 115))
        router.setdefault("root_type", "site")
        router.setdefault("root_virtual", False)
        router.setdefault("parent_node", "")  # used by deep_hierarchy/custom_hierarchy modes

        router.setdefault("pppoe", {})
        pppoe = router["pppoe"]
        pppoe.setdefault("enabled", False)
        pppoe.setdefault("per_plan_node", False)
        pppoe.setdefault("flat_aggregate_factor", 0.3)
        pppoe.setdefault("node_type", "plan")
        pppoe.setdefault("flat_node_name", "PPP-{router}")
        pppoe.setdefault("plan_node_name", "{profile}-{router}")
        pppoe.setdefault("factor_rules", [
            {"max_plan_mbps": 15, "download_factor": 0.31, "upload_factor": 0.31},
            {"max_plan_mbps": 9999, "download_factor": 1.0, "upload_factor": 1.0},
        ])

        router.setdefault("dhcp", {})
        dhcp = router["dhcp"]
        dhcp.setdefault("enabled", False)
        if not dhcp.get("servers") and dhcp.get("dhcp_server"):
            dhcp["servers"] = [{
                "name": name,
                "enabled": True,
                "mode": "per_site",
                "default_plan_down_mbps": dhcp.get("download_limit_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"]),
                "default_plan_up_mbps": dhcp.get("upload_limit_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"]),
                "download_factor": 0.5,
                "upload_factor": 0.5,
                "node_type": "site",
                "node_name": "DHCP-{server}-{router}",
            } for name in dhcp.get("dhcp_server", [])]
        dhcp.setdefault("servers", [])
        for server in dhcp.get("servers", []):
            server.setdefault("enabled", True)
            server.setdefault("name", "")
            server.setdefault("mode", "per_site")
            if "default_plan_down_mbps" not in server and "download_limit_mbps" in server:
                server["default_plan_down_mbps"] = server["download_limit_mbps"]
            if "default_plan_up_mbps" not in server and "upload_limit_mbps" in server:
                server["default_plan_up_mbps"] = server["upload_limit_mbps"]
            server.setdefault("default_plan_down_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"])
            server.setdefault("default_plan_up_mbps", cfg["defaults"]["default_dhcp_per_client_mbps"])
            server.setdefault("download_factor", 0.5)
            server.setdefault("upload_factor", 0.5)
            server.setdefault("node_type", "site")
            server.setdefault("node_name", "DHCP-{server}-{router}" if server.get("mode") == "per_site" else "PLAN-DHCP-{plan}-{router}")
            server.setdefault("speed_comment", "")

        router.setdefault("hotspot", {})
        hs = router["hotspot"]
        hs.setdefault("enabled", False)
        hs.setdefault("include_mac", True)
        hs.setdefault("download_limit_mbps", cfg["defaults"]["default_hotspot_per_client_mbps"])
        hs.setdefault("upload_limit_mbps", cfg["defaults"]["default_hotspot_per_client_mbps"])
        hs.setdefault("download_factor", 1.0)
        hs.setdefault("upload_factor", 1.0)
        hs.setdefault("node_type", "site")
        hs.setdefault("node_name", "HS-{router}")
        hs.setdefault("enhanced_metadata", cfg.get("collector", {}).get("hotspot", {}).get("enhanced_metadata", True))


def validate_config(cfg: dict):
    errors: list[str] = []
    warnings: list[str] = []
    paths = cfg.get("paths", {})
    mode = cfg.get("network_mode")
    if mode not in VALID_NETWORK_MODES:
        errors.append(f"network_mode invalid: {mode}")
    for opt in ("file_drift_policy",):
        val = cfg.get("app", {}).get(opt)
        if val not in ("overwrite_with_backup", "warn_only", "block"):
            errors.append(f"app.{opt} invalid: {val}")
    for key in ("shaped_devices_csv", "network_json"):
        if not paths.get(key):
            errors.append(f"paths.{key} is required")
    policies = cfg.setdefault("policies", {})
    policies.setdefault("mode", "balanced")
    if policies.get("mode") not in POLICY_PRESETS:
        errors.append(f"policies.mode invalid: {policies.get('mode')}")
    cleanup_sources = policies.get("cleanup_sources", {}) if isinstance(policies, dict) else {}
    for source_name, source_policy in cleanup_sources.items():
        if not isinstance(source_policy, dict):
            continue
        for key, val in source_policy.items():
            if key.endswith("_action") and val not in CLEANUP_ACTIONS:
                errors.append(f"policies.cleanup_sources.{source_name}.{key} invalid: {val}")
    for section in ("cleanup", "node_cleanup_guard", "small_node_guard", "source_cleanup_guard"):
        section_data = policies.get(section, {}) if isinstance(policies, dict) else {}
        if isinstance(section_data, dict):
            for key, val in section_data.items():
                if key.endswith("action") and val not in CLEANUP_ACTIONS:
                    errors.append(f"policies.{section}.{key} invalid: {val}")

    topology = cfg.setdefault("topology", {})
    topology.setdefault("allow_deep_hierarchy", True)
    topology.setdefault("allow_custom_edit", True)
    topology.setdefault("show_virtual_nodes", True)
    topology.setdefault("validate_before_save", True)

    rust_core = cfg.setdefault("rust_core", {})
    rust_core.setdefault("enabled", True)
    rust_core.setdefault("binary_path", "")
    rust_core.setdefault("timeout_seconds", 10)
    rust_core.setdefault("enforce_validation", False)
    rust_core.setdefault("enforce_sync_plan", False)
    rust_core.setdefault("fail_closed_when_enforced", True)
    rust_core.setdefault("authority_mode", "shadow")
    rust_core.setdefault("prefer_daemon", False)
    rust_core.setdefault("unix_socket", "/run/lqosync-core.sock")
    rust_core.setdefault("transaction_authority", "preview")
    rust_core.setdefault("execute_apply_manifest", False)
    rust_core.setdefault("allow_rust_file_writes", False)
    rust_core.setdefault("allow_rust_libreqos_apply", False)
    rust_core.setdefault("self_test_on_status", False)
    rust_core.setdefault("append_transaction_journal", False)
    rust_core.setdefault("allow_transaction_journal_writes", False)
    rust_core.setdefault("include_rehearsal_journal_entries", False)
    rust_core.setdefault("allow_dry_run_journal_entries", False)
    rust_core.setdefault("execute_rollback", False)
    rust_core.setdefault("allow_rust_rollback_file_writes", False)
    rust_core.setdefault("rollback_authority", "preview")
    rust_core.setdefault("require_authority_readiness", False)
    rust_core.setdefault("routeros_transport_authority", "plan_only")
    rust_core.setdefault("allow_rust_routeros_live_reads", False)
    rust_core.setdefault("allow_rust_routeros_credentials", False)
    rust_core.setdefault("routeros_live_read_pilot", False)
    rust_core.setdefault("routeros_live_read_timeout_seconds", 5)
    rust_core.setdefault("routeros_read_pilot_adapter", "fixture")
    rust_core.setdefault("allow_rust_routeros_fixture_reads", True)
    rust_core.setdefault("collector_authority_pilot_execution_pilot", False)
    rust_core.setdefault("allow_collector_authority_pilot_execution_contract", False)
    rust_core.setdefault("collector_authority_pilot_execution_mode", "contract_only")
    rust_core.setdefault("collector_authority_pilot_result_evaluator_pilot", False)
    rust_core.setdefault("allow_collector_authority_pilot_result_evaluation", False)
    rust_core.setdefault("collector_authority_pilot_result_mode", "evaluate_only")
    rust_core.setdefault("collector_authority_promotion_readiness_pilot", False)
    rust_core.setdefault("allow_collector_authority_promotion_readiness", False)
    rust_core.setdefault("collector_authority_promotion_readiness_mode", "readiness_only")
    rust_core.setdefault("collector_authority_promotion_require_pilot_result", True)
    rust_core.setdefault("collector_authority_promotion_require_python_fallback", True)
    rust_core.setdefault("collector_authority_promotion_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_promotion_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_promotion_max_shadow_age_seconds", 900)
    rust_core.setdefault("collector_authority_promotion_execution_rehearsal_pilot", False)
    rust_core.setdefault("allow_collector_authority_promotion_execution_rehearsal", False)
    rust_core.setdefault("collector_authority_promotion_execution_mode", "rehearsal_only")
    rust_core.setdefault("collector_authority_promotion_execution_require_readiness", True)
    rust_core.setdefault("collector_authority_promotion_execution_require_python_fallback", True)
    rust_core.setdefault("collector_authority_promotion_execution_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_promotion_execution_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_promotion_execution_max_shadow_age_seconds", 900)
    rust_core.setdefault("collector_authority_promotion_commit_plan_pilot", False)
    rust_core.setdefault("allow_collector_authority_promotion_commit_plan", False)
    rust_core.setdefault("collector_authority_promotion_commit_mode", "plan_only")
    rust_core.setdefault("collector_authority_promotion_commit_require_execution_rehearsal", True)
    rust_core.setdefault("collector_authority_promotion_commit_require_python_fallback", True)
    rust_core.setdefault("collector_authority_promotion_commit_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_promotion_commit_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_promotion_commit_max_shadow_age_seconds", 900)
    rust_core.setdefault("collector_authority_promotion_cutover_ledger_pilot", False)
    rust_core.setdefault("allow_collector_authority_promotion_cutover_ledger", False)
    rust_core.setdefault("collector_authority_promotion_cutover_mode", "ledger_only")
    rust_core.setdefault("collector_authority_promotion_cutover_require_commit_plan", True)
    rust_core.setdefault("collector_authority_promotion_cutover_require_python_fallback", True)
    rust_core.setdefault("collector_authority_promotion_cutover_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_promotion_cutover_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_promotion_cutover_require_rollback_path", True)
    rust_core.setdefault("collector_authority_promotion_cutover_max_shadow_age_seconds", 900)
    rust_core.setdefault("collector_authority_production_freeze_gate_pilot", False)
    rust_core.setdefault("allow_collector_authority_production_freeze_gate", False)
    rust_core.setdefault("collector_authority_production_freeze_mode", "freeze_only")
    rust_core.setdefault("collector_authority_production_freeze_require_cutover_ledger", True)
    rust_core.setdefault("collector_authority_production_freeze_require_python_fallback", True)
    rust_core.setdefault("collector_authority_production_freeze_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_production_freeze_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_production_freeze_require_rollback_path", True)
    rust_core.setdefault("collector_authority_production_freeze_require_maintenance_window", True)
    rust_core.setdefault("collector_authority_production_freeze_require_operator_ack", True)
    rust_core.setdefault("collector_authority_production_freeze_max_shadow_age_seconds", 900)
    rust_core.setdefault("collector_authority_production_switch_contract_pilot", False)
    rust_core.setdefault("allow_collector_authority_production_switch_contract", False)
    rust_core.setdefault("collector_authority_production_switch_mode", "contract_only")
    rust_core.setdefault("collector_authority_production_switch_require_freeze_gate", True)
    rust_core.setdefault("collector_authority_production_switch_require_python_fallback", True)
    rust_core.setdefault("collector_authority_production_switch_require_manual_confirmation", True)
    rust_core.setdefault("collector_authority_production_switch_require_no_cleanup_apply", True)
    rust_core.setdefault("collector_authority_production_switch_require_rollback_path", True)
    rust_core.setdefault("collector_authority_production_switch_require_maintenance_window", True)
    rust_core.setdefault("collector_authority_production_switch_require_operator_ack", True)
    rust_core.setdefault("collector_authority_production_switch_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_backend_api_handoff_plan_pilot", False)
    rust_core.setdefault("allow_rust_backend_api_handoff_plan", False)
    rust_core.setdefault("rust_backend_api_handoff_mode", "plan_only")
    rust_core.setdefault("rust_backend_api_handoff_require_production_switch_contract", True)
    rust_core.setdefault("rust_backend_api_handoff_require_python_backend_fallback", True)
    rust_core.setdefault("rust_backend_api_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_backend_api_handoff_require_webui_compatibility", True)
    rust_core.setdefault("rust_backend_api_handoff_require_route_parity", True)
    rust_core.setdefault("rust_backend_api_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_backend_api_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_backend_scheduler_handoff_plan_pilot", False)
    rust_core.setdefault("allow_rust_backend_scheduler_handoff_plan", False)
    rust_core.setdefault("rust_backend_scheduler_handoff_mode", "plan_only")
    rust_core.setdefault("rust_backend_scheduler_handoff_require_api_handoff", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_require_run_cycle_shadow", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_require_scheduler_parity", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_backend_scheduler_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_run_cycle_orchestrator_handoff_contract", False)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_mode", "contract_only")
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_scheduler_handoff", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_run_cycle_shadow", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_config_state_shadow", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_run_cycle_orchestrator_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_config_state_authority_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_config_state_authority_handoff_contract", False)
    rust_core.setdefault("rust_config_state_authority_handoff_mode", "contract_only")
    rust_core.setdefault("rust_config_state_authority_handoff_require_run_cycle_orchestrator", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_config_state_shadow", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_atomic_writer_shadow", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_transaction_journal_shadow", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_audit_shadow", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_rollback_shadow", True)
    rust_core.setdefault("rust_config_state_authority_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_config_state_authority_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_live_collector_authority_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_live_collector_authority_handoff_contract", False)
    rust_core.setdefault("rust_live_collector_authority_handoff_mode", "contract_only")
    rust_core.setdefault("rust_live_collector_authority_handoff_require_config_state_authority", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_live_collector_shadow", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_routeros_adapter_shadow", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_collector_parity", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_live_collector_authority_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_circuit_builder_authority_handoff_contract", False)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_mode", "contract_only")
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_live_collector_authority", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_circuit_shadow", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_shaped_devices_parity", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_parent_integrity", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_circuit_builder_authority_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_sync_engine_authority_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_sync_engine_authority_handoff_contract", False)
    rust_core.setdefault("rust_sync_engine_authority_handoff_mode", "contract_only")
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_circuit_builder_authority", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_sync_plan_shadow", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_diff_parity", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_apply_manifest_preview", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_cleanup_safety", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_sync_engine_authority_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_apply_journal_rollback_authority_handoff_contract", False)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_mode", "contract_only")
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_sync_engine_authority", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_apply_shadow", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_journal_shadow", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_rollback_shadow", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_audit_shadow", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_apply_journal_rollback_authority_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_backend_service_runtime_handoff_contract_pilot", False)
    rust_core.setdefault("allow_rust_backend_service_runtime_handoff_contract", False)
    rust_core.setdefault("rust_backend_service_runtime_handoff_mode", "contract_only")
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_apply_journal_rollback_authority", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_python_fallback", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_manual_confirmation", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_route_parity", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_static_assets", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_service_supervision", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_api_shadow", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_require_no_side_effects", True)
    rust_core.setdefault("rust_backend_service_runtime_handoff_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_production_readiness_contract_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_production_readiness_contract", False)
    rust_core.setdefault("full_rust_backend_production_readiness_mode", "contract_only")
    rust_core.setdefault("full_rust_backend_production_readiness_require_service_runtime", True)
    rust_core.setdefault("full_rust_backend_production_readiness_require_python_fallback", True)
    rust_core.setdefault("full_rust_backend_production_readiness_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_production_readiness_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_production_readiness_require_operator_final_review", True)
    rust_core.setdefault("full_rust_backend_production_readiness_require_no_side_effects", True)
    rust_core.setdefault("full_rust_backend_production_readiness_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_cutover_plan_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_cutover_plan", False)
    rust_core.setdefault("full_rust_backend_cutover_mode", "plan_only")
    rust_core.setdefault("full_rust_backend_cutover_require_production_readiness", True)
    rust_core.setdefault("full_rust_backend_cutover_require_python_fallback", True)
    rust_core.setdefault("full_rust_backend_cutover_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_cutover_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_cutover_require_rollback_path", True)
    rust_core.setdefault("full_rust_backend_cutover_require_operator_approval", True)
    rust_core.setdefault("full_rust_backend_cutover_require_no_side_effects", True)
    rust_core.setdefault("full_rust_backend_cutover_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_cutover_execution_contract_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_cutover_execution_contract", False)
    rust_core.setdefault("full_rust_backend_cutover_execution_mode", "contract_only")
    rust_core.setdefault("full_rust_backend_cutover_execution_require_cutover_plan", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_python_fallback", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_rollback_path", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_require_no_side_effects", True)
    rust_core.setdefault("full_rust_backend_cutover_execution_max_shadow_age_seconds", 900)
    rust_core.setdefault("python_backend_retirement_plan_pilot", False)
    rust_core.setdefault("allow_python_backend_retirement_plan", False)
    rust_core.setdefault("python_backend_retirement_mode", "plan_only")
    rust_core.setdefault("python_backend_retirement_require_cutover_execution_contract", True)
    rust_core.setdefault("python_backend_retirement_require_python_fallback", True)
    rust_core.setdefault("python_backend_retirement_require_manual_confirmation", True)
    rust_core.setdefault("python_backend_retirement_require_webui_unchanged", True)
    rust_core.setdefault("python_backend_retirement_require_rollback_path", True)
    rust_core.setdefault("python_backend_retirement_require_operator_ack", True)
    rust_core.setdefault("python_backend_retirement_require_no_side_effects", True)
    rust_core.setdefault("python_backend_retirement_max_shadow_age_seconds", 900)
    rust_core.setdefault("rust_backend_production_enablement_contract_pilot", False)
    rust_core.setdefault("allow_rust_backend_production_enablement_contract", False)
    rust_core.setdefault("rust_backend_production_enablement_mode", "contract_only")
    rust_core.setdefault("rust_backend_production_enablement_require_python_retirement_plan", True)
    rust_core.setdefault("rust_backend_production_enablement_require_python_fallback", True)
    rust_core.setdefault("rust_backend_production_enablement_require_manual_confirmation", True)
    rust_core.setdefault("rust_backend_production_enablement_require_webui_unchanged", True)
    rust_core.setdefault("rust_backend_production_enablement_require_rollback_path", True)
    rust_core.setdefault("rust_backend_production_enablement_require_operator_ack", True)
    rust_core.setdefault("rust_backend_production_enablement_require_no_side_effects", True)
    rust_core.setdefault("rust_backend_production_enablement_max_shadow_age_seconds", 900)
    rust_core.setdefault("python_backend_removal_execution_contract_pilot", False)
    rust_core.setdefault("allow_python_backend_removal_execution_contract", False)
    rust_core.setdefault("python_backend_removal_execution_mode", "contract_only")
    rust_core.setdefault("python_backend_removal_execution_require_rust_enablement_contract", True)
    rust_core.setdefault("python_backend_removal_execution_require_python_fallback", True)
    rust_core.setdefault("python_backend_removal_execution_require_manual_confirmation", True)
    rust_core.setdefault("python_backend_removal_execution_require_webui_unchanged", True)
    rust_core.setdefault("python_backend_removal_execution_require_rollback_path", True)
    rust_core.setdefault("python_backend_removal_execution_require_operator_ack", True)
    rust_core.setdefault("python_backend_removal_execution_require_no_side_effects", True)
    rust_core.setdefault("python_backend_removal_execution_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_removal_rehearsal", False)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_mode", "rehearsal_only")
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_removal_execution_contract", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_python_fallback", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_rollback_path", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_require_no_side_effects", True)
    rust_core.setdefault("full_rust_backend_removal_rehearsal_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_production_cutover_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_production_cutover", False)
    rust_core.setdefault("full_rust_backend_production_cutover_mode", "operator_supervised")
    rust_core.setdefault("full_rust_backend_production_cutover_require_removal_rehearsal", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_rollback_path", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_production_cutover_require_python_fallback_backup", True)
    rust_core.setdefault("full_rust_backend_production_cutover_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_production_verifier_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_production_verifier", False)
    rust_core.setdefault("full_rust_backend_production_verifier_mode", "verify_only")
    rust_core.setdefault("full_rust_backend_production_verifier_require_cutover", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_runtime_health", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_rollback_package", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_production_verifier_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_production_verifier_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_post_retirement_verifier_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_post_retirement_verifier", False)
    rust_core.setdefault("full_rust_backend_post_retirement_verifier_mode", "verify_only")
    rust_core.setdefault("full_rust_backend_post_retirement_require_production_verifier", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_runtime_health", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_python_retired", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_rollback_package", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_post_retirement_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_post_retirement_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_steady_state_guard_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_steady_state_guard", False)
    rust_core.setdefault("full_rust_backend_steady_state_guard_mode", "guard_only")
    rust_core.setdefault("full_rust_backend_steady_state_require_post_retirement_verifier", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_runtime_health", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_no_python_drift", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_rollback_package", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_steady_state_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_steady_state_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_production_drift_monitor_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_production_drift_monitor", False)
    rust_core.setdefault("full_rust_backend_production_drift_monitor_mode", "monitor_only")
    rust_core.setdefault("full_rust_backend_drift_monitor_require_steady_state_guard", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_runtime_health", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_no_python_drift", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_rollback_package", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_drift_monitor_max_shadow_age_seconds", 900)
    rust_core.setdefault("full_rust_backend_production_audit_sentinel_pilot", False)
    rust_core.setdefault("allow_full_rust_backend_production_audit_sentinel", False)
    rust_core.setdefault("full_rust_backend_production_audit_sentinel_mode", "sentinel_only")
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_drift_monitor", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_audit_trail", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_journal_visibility", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_rollback_visibility", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_webui_unchanged", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_server_tests", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_manual_confirmation", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_require_operator_ack", True)
    rust_core.setdefault("full_rust_backend_audit_sentinel_max_shadow_age_seconds", 900)
    if rust_core.get("authority_mode") not in ("shadow", "enforce_blockers"):
        errors.append(f"rust_core.authority_mode invalid: {rust_core.get('authority_mode')}")
    if rust_core.get("routeros_read_pilot_adapter") not in ("fixture", "disabled"):
        errors.append(f"rust_core.routeros_read_pilot_adapter invalid: {rust_core.get('routeros_read_pilot_adapter')}")
    if rust_core.get("routeros_transport_authority") not in ("plan_only", "live_read_pilot"):
        errors.append(f"rust_core.routeros_transport_authority invalid: {rust_core.get('routeros_transport_authority')}")
    try:
        rust_core["routeros_live_read_timeout_seconds"] = max(int(rust_core.get("routeros_live_read_timeout_seconds", 5) or 5), 1)
    except Exception:
        errors.append("rust_core.routeros_live_read_timeout_seconds must be numeric")
    # Compatibility: authority_mode=enforce_blockers implies sync-plan enforcement.
    if rust_core.get("authority_mode") == "enforce_blockers":
        rust_core["enforce_sync_plan"] = True
    if rust_core.get("rollback_authority") not in ("preview", "execute_file_restores"):
        errors.append(f"rust_core.rollback_authority invalid: {rust_core.get('rollback_authority')}")
    try:
        rust_core["timeout_seconds"] = max(int(rust_core.get("timeout_seconds", 10) or 10), 1)
    except Exception:
        errors.append("rust_core.timeout_seconds must be numeric")

    collector = cfg.get("collector", {})
    lease_mode = collector.get("dhcp", {}).get("lease_mode", "permissive")
    if lease_mode not in ("permissive", "strict"):
        errors.append(f"collector.dhcp.lease_mode invalid: {lease_mode}")
    sched = cfg.get("scheduler", {})
    for key in ("active_interval_seconds", "idle_interval_seconds", "error_retry_interval_seconds"):
        try:
            if int(sched.get(key, 0)) <= 0:
                errors.append(f"scheduler.{key} must be > 0")
        except Exception:
            errors.append(f"scheduler.{key} must be numeric")
    seen_router_names = set()
    for idx, router in enumerate(cfg.get("routers", [])):
        name = router.get("name") or f"router[{idx}]"
        if name in seen_router_names:
            errors.append(f"duplicate router name: {name}")
        seen_router_names.add(name)
        if router.get("enabled", True):
            if not router.get("address"):
                warnings.append(f"{name}: address is empty")
            if not router.get("username"):
                warnings.append(f"{name}: username is empty")
        try:
            float(router.get("root_download_mbps", 0)); float(router.get("root_upload_mbps", 0))
        except Exception:
            errors.append(f"{name}: root bandwidth must be numeric")
        for rule in router.get("pppoe", {}).get("factor_rules", []):
            for key in ("max_plan_mbps", "download_factor", "upload_factor"):
                try: float(rule.get(key))
                except Exception: errors.append(f"{name}: PPP factor rule {key} must be numeric")
        for server in router.get("dhcp", {}).get("servers", []):
            if not server.get("name"):
                errors.append(f"{name}: DHCP server entry has empty name")
            if str(server.get("mode", "per_site")).lower() not in ("per_site", "per_plan"):
                errors.append(f"{name}/{server.get('name')}: invalid DHCP mode")
            for key in ("default_plan_down_mbps", "default_plan_up_mbps", "download_factor", "upload_factor"):
                try: float(server.get(key))
                except Exception: errors.append(f"{name}/{server.get('name')}: {key} must be numeric")
    schema_report = validate_schema(cfg)
    for e in schema_report.get("errors", []):
        if e not in errors:
            errors.append(e)
    for w in schema_report.get("warnings", []):
        if w not in warnings:
            warnings.append(w)
    return errors, warnings
