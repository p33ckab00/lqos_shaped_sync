# First Run Setup Wizard

LQoSync v2.54 adds a guided First Run Setup Wizard. The wizard is designed for new installs and major reconfiguration work. It does not replace Setup & Repair; instead, it gives operators a clean step-by-step path to production readiness.

## Purpose

The wizard answers:

- Are LibreQoS paths available?
- Are MikroTik routers configured?
- Are PPPoE / DHCP / Hotspot sources selected?
- Which Network Layout mode is active?
- Which Smart Policy preset is active?
- Has a Dry Run been completed?
- Is the scheduler ready to be enabled?

## Safety model

The wizard is read-only while loading. It does not contact routers or write generated LibreQoS files on page load. Write actions are deliberate form submissions such as applying a policy preset or saving a network layout mode.

Operators should follow this order:

1. Confirm LibreQoS paths.
2. Configure MikroTik router access.
3. Choose enabled PPPoE / DHCP / Hotspot sources.
4. Choose Network Layout mode.
5. Choose Smart Policy preset.
6. Run Dry Run.
7. Review Smart Reports / Lifecycle if needed.
8. Enable scheduler only after Dry Run is clean and expected.

## Relationship to Setup & Repair

Setup Wizard is for first-run onboarding and go-live flow.

Setup & Repair is for diagnostics, failed checks, repair commands, permission/path checks, and recovery guidance.

About / Documentation remains the long-form manual source of truth.
