# mini-EDR SDLC plan

## Product goal

Provide clear alerts when suspicious activity occurs on enrolled Windows or Linux endpoints. The system must preserve the evidence that led to each alert and be simple enough to deploy and troubleshoot.

## Design decisions

| Decision | Choice | Reason |
|---|---|---|
| Detection location | Server-side rules | One auditable source of truth |
| Agent role | Collect, buffer, authenticate, transmit | Keeps endpoints lightweight |
| Database | SQLite for development, PostgreSQL before multi-user production | Low setup cost, clear growth path |
| UI | Server-rendered terminal-style UI | No unnecessary frontend framework |
| Response | Manual only in v1 | Avoids unsafe automatic changes |
| AI | Excluded | Deterministic alerts are testable and explainable |
| YARA | Agent scanning, server-managed rule packs | Files remain on endpoint; server owns rule version |

## Phases and acceptance criteria

### 0. Scope and threat model — complete with Phase 1

- Define data flow, event schema, alert schema, and out-of-scope functions.
- Identify sensitive assets: enrollment tokens, agent tokens, telemetry, alert evidence, and database backups.
- Acceptance: team agrees this is alerting-first with no automatic remediation.

### 1. Server foundation — in progress

- Agent enrollment, heartbeats, authenticated ingestion, storage, rules, alerts, and dashboard.
- Acceptance: a simulated agent event generates a visible alert with evidence.

### 2. Agent core and Wazuh-style deployment

- Keep the complete repository on the Ubuntu server only. Endpoint users receive a generated install command, never a Git clone URL.
- Add server-created, per-endpoint, expiring deployment tokens; store only their hashes and mark them active after one successful enrollment.
- Add durable local queue, exponential retry, configuration file, health diagnostics, and agent update version reporting.
- Package a signed Windows service installer and Linux systemd package/install script. Both must start automatically after reboot.
- Acceptance: a disconnected endpoint retains events and safely uploads them after reconnecting.

### 3. Native log collection

- Windows: Security event IDs 4688, 4624, 4625; PowerShell 4103/4104; optional Sysmon integration.
- Linux: journald, SSH/authentication, sudo; auditd as an optional source.
- Acceptance: fixtures from both platforms normalize to the common event schema.

### 4. Detection engineering

- Add reviewed rule categories: PowerShell, suspicious parent/child process chains, authentication anomalies, persistence indicators, and YARA matches.
- Add bounded time-window correlation.
- Acceptance: every rule has positive, negative, and false-positive test fixtures.

### 5. YARA rule-pack support

- Version, review, and hash rule packs on the server.
- Agents retrieve only approved packs and report metadata/matches; they do not upload scanned files by default.
- Acceptance: a harmless known test file yields an attributable YARA alert.

### 6. Security hardening and release

- TLS via reverse proxy, one-time enrollment tokens, token rotation/revocation, least-privilege services, audit logs, backups, retention policy, and release signing.
- Acceptance: security test checklist passes in isolated test VMs.

## Non-functional requirements

- Server must reject unauthenticated, malformed, oversized, and replayed enrollment requests.
- Event ingestion must not silently discard failures; agents must retain a bounded local queue.
- Every alert must identify the endpoint, source event, detection rule, time, severity, and evidence.
- The dashboard must never render raw event values as executable HTML.
- Rules must be version-controlled and tested before release.

## Test strategy

1. Unit tests: event validation, token hashing, rule matching, severity handling.
2. API tests: enrollment, authentication, event batches, alert lifecycle.
3. Fixture tests: Windows Event Log XML/JSON and Linux journal JSON.
4. Integration tests: one Windows and one Linux VM, including network interruption.
5. Security tests: invalid tokens, duplicate enrollment, bad timestamps, oversized payloads, input injection, and access-control checks.

## Explicitly deferred

- Automatic process killing, host isolation, quarantine, or arbitrary remote commands.
- Full packet capture, direct ETW tracing, kernel drivers, and large-scale SIEM pipelines.
- AI/LLM incident conclusions.
- Elasticsearch, queues, Kubernetes, and multi-tenant design.
