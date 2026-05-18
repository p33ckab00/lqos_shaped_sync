# Operator Overview

LQoSync is designed to make the MikroTik-to-LibreQoS sync process visible.

## What happens behind the system

```text
MikroTik API collection
  → source normalization
  → identity/speed resolution
  → policy evaluation
  → generated ShapedDevices.csv rows
  → generated network.json nodes
  → validation and Dry Run impact
  → backup and write
  → LibreQoS apply/update
  → logs, audit, and health summaries
```

## Operator mental model

- Collectors answer: what does MikroTik currently show?
- Builders answer: what files would LibreQoS receive?
- Policies answer: is it safe to add, update, remove, or hold rows?
- Dry Run answers: what would change before live write?
- Operations Center answers: what actually happened?
- Update Center answers: what version/code is installed and what update is available?

## Inspired by LibreQoS

LQoSync does not replace LibreQoS. It is a companion tool inspired by LibreQoS workflows, built to reduce manual file editing and expose the logic behind generated shaping inputs.
