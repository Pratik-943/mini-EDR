# 🛡️ Mini-EDR (Endpoint Detection and Response)

Mini-EDR is a production-ready, AI-powered Endpoint Detection and Response system. It monitors Windows endpoints in real-time and streams live threat telemetry to a centralized Ubuntu command server with a live web dashboard.

**Key Features:**
- 🤖 **AI Behavioral Analysis** — Local LLM (Ollama) analyzes event sequences for ransomware and malicious behavior
- 🔍 **YARA Signature Detection** — Real-time file scanning with auto-quarantine
- 👁️ **Process, Network & Registry Monitoring** — Full endpoint visibility
- 🌐 **Live Web Dashboard** — Real-time alerts, endpoint registry, and AI model selector
- 💉 **Fileless Deployment** — One PowerShell command installs the agent silently
- 🔄 **Universal Agent** — One compiled `agent.exe` works for all deployments, no recompile needed

---

## 🏗️ Architecture

```
[ Windows Endpoint ]  ──POST /api/logs──►  [ Ubuntu Server (AWS EC2) ]
    agent.exe                                  FastAPI + Ollama AI
    (silent, hidden)                           Live Web Dashboard
                                               port 8000
```

1. **Central Command Server (Ubuntu/Cloud):** Hosts the FastAPI backend, AI engine, and live dashboard.
2. **Endpoint Agent (Windows):** A silent, compiled `.exe` that monitors processes, files, network, and registry. Deployed via a single PowerShell command.

---

## 🚀 Server Setup Guide (Ubuntu / AWS EC2)

### Step 1 — Install AI Engine (Ollama)
```bash
curl -fsSL https://ollama.com/install.sh | sh

# For 4GB RAM / 2 CPU (recommended for low-resource servers)
ollama pull qwen2.5:0.5b
ollama pull llama3.2:1b

# For 8GB+ RAM
ollama pull llama3.2:3b
```

### Step 2 — Clone the Repository
```bash
git clone https://github.com/Pratik-943/mini-EDR.git
cd mini-EDR
```

### Step 3 — Install Python Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4 — Start the Server
```bash
cd server
uvicorn app:app --host 0.0.0.0 --port 8000
```

> Open `http://<YOUR_SERVER_IP>:8000` in any browser to view the Live Dashboard.

> **AWS EC2 Users:** Ensure Port `8000` is open in your Security Group Inbound Rules (Custom TCP, `0.0.0.0/0`).

---

## ⚙️ Agent Build (GitHub Actions — Automatic)

The Windows agent is **automatically compiled** by GitHub Actions on every push. No manual compilation or IP configuration is needed.

1. Go to your GitHub repo → **Actions** tab → **Build Universal Agent**
2. Click **Run workflow** → **Run workflow**
3. GitHub will compile `agent.exe` on a real Windows machine and commit it to `server/payloads/agent.exe`
4. Run `git pull` on your Ubuntu server to get the latest agent

> The agent reads the server URL **at runtime** from the command it is launched with, so the same `agent.exe` works for any server IP without recompiling.

---

## 💉 Deploying to Windows Endpoints

No Python, no repo, no setup needed on the endpoint machine.

### Method 1: Dashboard Deploy Page (Recommended)
1. Open your dashboard in the browser
2. Click the **"DEPLOY ENDPOINT"** button in the top-right header
3. Copy the auto-generated PowerShell command (pre-filled with your server IP)
4. Paste it in **PowerShell as Administrator** on the target Windows machine

### Method 2: Direct URL
Navigate to `http://<YOUR_SERVER_IP>:8000/deploy/dropper` to get the one-liner.

The agent will silently download, register itself with the server, and begin streaming live telemetry. Your dashboard will immediately show the new endpoint with its hostname, OS, CPU, and RAM details.

---

## 🛡️ Features & Testing

Once deployed, trigger detection events on the Windows endpoint to test:

| Test | Action | Expected Result |
|---|---|---|
| **File Monitor** | Create any file in `C:\Users` | Gray INFO log on dashboard |
| **YARA Detection** | Create a file named `malware.bat` | 🔴 CRITICAL alert, file auto-deleted |
| **AI Detection** | Run rapid file creation loop (5+ files) | 🟣 AI DETECTED alert |
| **Registry Monitor** | Add key to `HKCU\...\CurrentVersion\Run` | Alert on dashboard |

**AI Sequence Test (Ransomware Simulation):**
```powershell
1..5 | ForEach-Object { New-Item -Path "$env:USERPROFILE\Desktop\locked_$_.encrypted" -ItemType File }
```

---

## 🔄 Auto-Start on Reboot (Persistence)

### Ubuntu Server — systemd Service
```bash
sudo nano /etc/systemd/system/miniedr.service
```
Paste:
```ini
[Unit]
Description=Mini-EDR Dashboard Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/mini-EDR/server
ExecStart=/home/ubuntu/mini-EDR/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable miniedr
sudo systemctl start miniedr
```

### Windows Agent — Registry Persistence
Run in PowerShell on the endpoint after the agent is installed:
```powershell
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MiniEDR_Agent" -Value "$env:TEMP\agent.exe" -PropertyType String -Force
```

---

## 🧠 AI Model Selection

The dashboard includes a live AI Model Selector in the header. Switch models without restarting the server.

| Model | RAM Required | Speed | Best For |
|---|---|---|---|
| `qwen2.5:0.5b` | ~1 GB | ⚡ Fastest | Low-resource servers |
| `llama3.2:1b` | ~2 GB | Fast | Balanced performance |
| `llama3.2:3b` | ~4 GB | Moderate | High accuracy |
