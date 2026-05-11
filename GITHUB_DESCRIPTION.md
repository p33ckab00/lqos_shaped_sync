# GitHub Repository Metadata

Repository name:

```text
lqos_shaped_sync
```

Description:

```text
Database-free MikroTik-to-LibreQoS subscriber sync dashboard that generates ShapedDevices.csv/network.json with dry-run, scheduler, Docker, and service monitoring.
```

Topics:

```text
libreqos mikrotik routeros qos shaping isp pppoe dhcp hotspot scheduler docker python flask
```

## In-app About module

The application includes an operator-readable About page at `/about` with project description, workflow, installation guide, requirements, paths, commands, and notes.


This release includes pending LibreQoS apply recovery: when files were written successfully but LibreQoS.py fails, LQoSync keeps a pending apply marker and retries until LibreQoS applies successfully.
