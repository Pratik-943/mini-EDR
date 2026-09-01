# mini-EDR

<p align="center"><strong>Private-network endpoint detection with Wazuh-style agent deployment.</strong></p>

mini-EDR runs its complete server on one Ubuntu Server. Administrators use the dashboard to create a unique deployment for each Windows or Linux endpoint, then paste the generated command into that endpoint as an administrator. Endpoints do **not** clone this repository.

## V1 architecture

```text
┌──────────────────┐              ┌─────────────────────────────────────┐
│ Windows endpoint │              │ Ubuntu Server                        │
│ Agent service    │── HTTPS ───▶ │ mini-EDR server + dashboard + rules  │
└──────────────────┘              │ deployment-token database            │
                                  └─────────────────────────────────────┘
┌──────────────────┐                         ▲
│ Linux endpoint   │──────── HTTPS ───────────┘
│ Agent service    │
└──────────────────┘
```

The lab uses exactly three systems on one VMware Host-only or isolated NAT network:

| System | Purpose |
|---|---|
| Ubuntu Server VM | Central server, dashboard, deployment service, database, detection rules |
| Windows desktop VM | Monitored endpoint; receives only the Windows agent package |
| Linux desktop VM | Monitored endpoint; receives only the Linux agent package |

The Ubuntu Server must have a static local IP address because agents use that address to reconnect after reboot.

## Ubuntu Server minimum requirements

| Resource | Minimum | Recommended |
|---|---:|---:|
| Operating system | Ubuntu Server 22.04 LTS | Ubuntu Server 24.04 LTS |
| CPU | 2 vCPU | 2–4 vCPU |
| Memory | 4 GB RAM | 4–8 GB RAM |
| Storage | 40 GB free | 40–80 GB free |
| Network | Static local IPv4 address | Static local IPv4 address |
| Open port | TCP `443` from endpoints | TCP `443` from endpoints |

## Deployment security model

Each deployment is separate:

```text
Windows-01 → deployment token A → agent credential A
Linux-01   → deployment token B → agent credential B
```

1. The admin selects an operating system and unique agent name in the dashboard.
2. The server generates a cryptographically random deployment token and stores only its SHA-256 hash.
3. The dashboard displays one installation command. This is the only time the token is shown.
4. The endpoint runs the command as Administrator or `root`, downloads only its OS package, and enrolls.
5. The server marks the token `active`; it cannot enroll another endpoint.
6. The installed service uses its own agent credential for future telemetry and starts automatically after reboot.

Pending tokens can be revoked from the dashboard. Expired, revoked, or used tokens cannot be reused.

## Current implementation status

| Feature | Status |
|---|---|
| Admin-protected deployment API and dashboard | Implemented |
| Per-endpoint token generation, expiry, revocation, and one-time enrollment | Implemented |
| Endpoint repository cloning | Removed from the deployment design |
| Package download endpoint | Implemented; serves published agent artifacts only |
| Windows MSI agent service | Packaging work still required |
| Linux DEB agent service | Packaging work still required |
| Native Windows/Linux log collectors | Next implementation phase |

Do not generate a production deployment command until signed agent packages have been built and published under `server/payloads/`. Until then, the dashboard correctly reports that no package is published.

---

## 1. Prepare the VMware local network

Use a Host-only or isolated NAT network. Example addresses:

| VM | Example address |
|---|---:|
| Ubuntu Server | `192.168.56.10` |
| Windows desktop | `192.168.56.20` |
| Linux desktop | `192.168.56.30` |

On the Ubuntu server, confirm its address:

```bash
ip -br address
```

On each endpoint, verify it can reach the Ubuntu server:

```bash
ping 192.168.56.10
```

---

## 2. Install the central server on Ubuntu

Run every command in this section on the Ubuntu Server VM.

### 2.1 Install dependencies

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip caddy openssl ufw
```

### 2.2 Clone this repository — server only

```bash
sudo mkdir -p /opt/mini-edr
sudo chown "$USER":"$USER" /opt/mini-edr
git clone https://github.com/Pratik-943/mini-EDR.git /opt/mini-edr
cd /opt/mini-edr
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
```

`pytest` must pass before continuing.

### 2.3 Create the service account and admin token

Create a strong administrator token. It grants access to the dashboard data and deployment commands.

```bash
openssl rand -hex 32
```

Create the service account and environment file:

```bash
sudo useradd --system --home /opt/mini-edr --shell /usr/sbin/nologin mini-edr
sudo install -d -o mini-edr -g mini-edr /var/lib/mini-edr
sudo install -d -o root -g mini-edr -m 750 /etc/mini-edr
sudo nano /etc/mini-edr/server.env
```

Paste this content, replacing the value once with the random output. Never commit or share it.

```ini
EDR_ADMIN_TOKEN=PASTE_YOUR_RANDOM_ADMIN_TOKEN_HERE
EDR_DATABASE_PATH=/var/lib/mini-edr/mini_edr.db
EDR_SERVER_NAME=mini-EDR-LAB
```

Protect it:

```bash
sudo chown root:mini-edr /etc/mini-edr/server.env
sudo chmod 640 /etc/mini-edr/server.env
sudo chown -R mini-edr:mini-edr /var/lib/mini-edr
```

### 2.4 Start the server and HTTPS proxy

```bash
cd /opt/mini-edr
sudo cp deploy/systemd/mini-edr-server.service /etc/systemd/system/mini-edr-server.service
sudo systemctl daemon-reload
sudo systemctl enable --now mini-edr-server
sudo cp deploy/caddy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Replace `192.168.56.10` in the Caddyfile with the static IP of your Ubuntu server. Then validate and start Caddy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl restart caddy
```

Restrict access to your endpoints:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.56.20 to any port 443 proto tcp
sudo ufw allow from 192.168.56.30 to any port 443 proto tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 2.5 Verify the server

```bash
sudo systemctl status mini-edr-server --no-pager
sudo systemctl status caddy --no-pager
sudo journalctl -u mini-edr-server -f
```

Open `https://YOUR_SERVER_IP` from an administrator browser. Enter the `EDR_ADMIN_TOKEN` from `/etc/mini-edr/server.env` to unlock the dashboard.

---

## 3. Deploy an endpoint from the dashboard

This is the only intended endpoint deployment path. Do **not** clone GitHub or install Python on endpoint computers.

1. Open `https://YOUR_SERVER_IP` in an administrator browser.
2. Enter the server administrator token.
3. Under **DEPLOY NEW AGENT**, select `Windows` or `Linux`.
4. Enter a unique agent name, for example `windows-lab-01` or `linux-lab-01`.
5. Select how long the deployment token remains valid.
6. Select **Generate install command**.
7. Copy the generated command once.
8. Run it as Administrator on Windows or with `sudo` on Linux.

The endpoint downloads only its signed package from your Ubuntu Server. After installation, the package creates the OS service and the agent connects automatically. The deployment record changes from `pending` to `active` after enrollment.

## 4. Publish agent packages before deployment

The Ubuntu server delivers packages from `server/payloads/`. The expected names are:

```text
server/payloads/mini-edr-agent-windows.msi
server/payloads/mini-edr-agent-linux-amd64.deb
```

Package requirements are documented in [server/payloads/README.md](server/payloads/README.md). Build artifacts must be signed, verified, and copied to the Ubuntu server during release; they must not be committed to GitHub.

## Server operations

| Task | Command |
|---|---|
| Server status | `sudo systemctl status mini-edr-server --no-pager` |
| Follow server logs | `sudo journalctl -u mini-edr-server -f` |
| Restart server | `sudo systemctl restart mini-edr-server` |
| Proxy status | `sudo systemctl status caddy --no-pager` |
| Database backup | `sudo cp /var/lib/mini-edr/mini_edr.db /var/backups/mini_edr_$(date +%F).db` |

## Safety rules

- Never expose this lab server directly to the public internet.
- Never commit admin tokens, certificates, database files, or installer packages.
- Never disable certificate verification with `curl -k` or `verify=False`.
- Use only safe test data. Do not download or execute malware.
- Revoke unused deployments and rotate the admin token if it is exposed.

