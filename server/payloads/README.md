# Server agent packages

This folder is read only by the mini-EDR server. Endpoints never clone the repository; they download a package only after an administrator creates a unique deployment record.

The deployment API expects these signed release artifacts:

- `mini-edr-agent-windows.msi`
- `mini-edr-agent-linux-amd64.deb`

The Windows MSI must install the `mini-edr-agent` Windows service, configure it with the `SERVER_URL`, `DEPLOYMENT_TOKEN`, and `AGENT_NAME` properties, and start it automatically.

The Linux DEB must install the `mini-edr-agent` command and `mini-edr-agent.service`. Its `configure` command must store the server URL, deployment token, and agent name with root-only permissions. The service must then enroll once, delete the deployment token after successful enrollment, and start automatically on reboot.

Do not commit built installers to Git. Publish verified signed artifacts to this server directory during the release process. The server returns `503 Package not published` until an expected package is available.

