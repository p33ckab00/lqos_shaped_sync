//! LQoSync Rust safety core.
//!
//! v0.1 intentionally acts as an optional sidecar validator. Python remains the
//! WebUI/orchestrator, while this crate provides deterministic parsing and
//! validation behind a stable JSON protocol that can be used by both a CLI and a
//! future Unix socket daemon.

pub mod atomic_state;
pub mod apply_manifest;
pub mod apply_transaction;
pub mod bandwidth;
pub mod circuits;
pub mod collector_bundle;
pub mod collector_parity;
pub mod network;
pub mod protocol;
pub mod shaped_devices;
pub mod validators;
pub mod diff;
pub mod policy;

pub mod sync_plan;

pub mod self_test;
pub mod transaction_journal;
pub mod transaction_history;
pub mod rollback_executor;
pub mod authority_readiness;
pub mod authority_pilot;
pub mod routeros_plan;
pub mod routeros_results;
pub mod routeros_transport;
pub mod routeros_live_pilot;
pub mod routeros_read_pilot;
pub mod routeros_api_codec;
pub mod routeros_api_reply;
pub mod routeros_api_frame;
pub mod routeros_offline_session;
pub mod routeros_tcp_probe;
pub mod routeros_auth_plan;
pub mod routeros_auth_handshake;
