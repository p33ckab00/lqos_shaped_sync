# Policy Overview Custom Wiring Hotfix

LQoSync v2.70.10 fixes Custom policy mode behavior for Policy Overview controls inside Config Center → Policies.

Changing Operation Mode, Auto Apply, Optional Auto Backup, or Backup Retention now marks the policy state as Custom in the browser and is also protected server-side during Config Center save.

This is needed because those settings live under `app.*` for runtime compatibility, but they are presented inside the Policy Hierarchy as operator policy semantics.

Named presets still replace only `config.json → policies`; manual operator changes inside the Policy page remain Custom until a named preset is applied again.
