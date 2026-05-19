//! LQoSync Rust safety core.
//!
//! v0.1 intentionally acts as an optional sidecar validator. Python remains the
//! WebUI/orchestrator, while this crate provides deterministic parsing and
//! validation behind a stable JSON protocol that can be used by both a CLI and a
//! future Unix socket daemon.

pub mod bandwidth;
pub mod network;
pub mod protocol;
pub mod shaped_devices;
pub mod validators;
pub mod diff;
