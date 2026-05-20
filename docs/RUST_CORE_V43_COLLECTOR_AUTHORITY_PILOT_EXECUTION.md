# Rust Core v4.3 Collector Authority Pilot Execution Contract

Adds `build-collector-authority-pilot-execution-contract`, a non-mutating bridge after the v4.2 switch rehearsal.

## Purpose

This phase proves that LQoSync can describe a future Rust collector authority pilot execution without actually switching production collector authority away from Python.

## Safety

The operation does not open RouterOS sockets, does not perform live reads, does not transfer cleanup authority, does not write generated files, and does not apply LibreQoS. Python collector fallback remains mandatory.

## Confirmation

The readiness contract requires the manual token:

```text
CONFIRM_COLLECTOR_AUTHORITY_PILOT_EXECUTION
```

Even with the token, this release only returns `collector_authority_pilot_execution_contract_ready`; it does not execute production authority transfer.

## Operation

```text
build-collector-authority-pilot-execution-contract
```

## API

```text
GET  /api/rust-core/collector-authority-pilot-execution-contract
POST /api/rust-core/collector-authority-pilot-execution-contract
```
