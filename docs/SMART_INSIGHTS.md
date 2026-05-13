# LQoSync v2.46 Smart Insights

Smart Insights is the operator guidance layer above the Smart Policy Center. It does not replace policy enforcement. It explains the result of each sync/dry-run in human terms.

## Included insights

- Data Quality score
- Backup readiness
- Fallback speed review
- Anomaly detection basics
- Recommendations panel
- Why / Fix / Next Action explanations

## Data Quality

The score starts at 100 and subtracts points for validation errors, collector errors, warnings, fallback/default speed usage, policy blocks, confirmation requirements, and suspicious empty output.

## Fallback speed review

Rows are flagged when the speed source contains `default`, `fallback`, or an unknown default-style source. These rows should be reviewed because the speed resolver did not find a stronger source such as PPP secret comment, profile comment/name, DHCP server speed_comment/name, or Hotspot user/profile metadata.

## Anomaly detection

The first implementation compares the current run with the previous run stored in runtime_state.json. It warns when generated client count drops sharply, total sync duration increases by a configured multiplier, or LibreQoS apply duration increases sharply.

## Operator guidance

Every recommendation should include:

```text
Title
Reason
Next action
Severity
```

This keeps the UI focused on actionable operations rather than raw internal flags.
