# Mini-EDR (Endpoint Detection and Response)

Mini-EDR is a lightweight, cross-platform security architecture designed to monitor Windows endpoints and stream live threat telemetry to a centralized Ubuntu command server. 

It features an invisible, fileless agent deployment, real-time YARA scanning, active threat quarantine, and a live web dashboard.

---

## 🏗️ Architecture
1. **Central Command Server (Ubuntu):** A FastAPI backend that receives telemetry, logs alerts, and hosts the live web dashboard.
2. **Endpoint Agent (Windows):** A compiled, hidden executable that monitors processes, network connections, file modifications, and registry persistence.

---

## 🚀 1. Setup AI Engine (Ollama)
Mini-EDR uses **Ollama** on the Ubuntu server to perform advanced Behavioral Sequence Analysis without overloading the Windows endpoints.

1. **Install Ollama on Ubuntu:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. **Download AI Models:**
   Depending on your server hardware, pull the models you want to use. We recommend lightweight models for systems with lower RAM:
   
   *(For 4GB RAM / 2 Cores - Extremely Fast)*
   ```bash
   ollama pull qwen2.5:0.5b
   ollama pull llama3.2:1b
   ```
   *(For 8GB+ RAM)*
   ```bash
   ollama pull llama3.2:3b
   ```

---

## 📥 2. Download the Codebase
Clone this repository to your Ubuntu server and navigate into the directory:
```bash
git clone https://github.com/Pratik-943/mini-EDR.git
cd mini-EDR
```

---

## ⚙️ 3. Configuring the Agent IP & Compiling (Crucial Step)
Before starting the server or deploying the Windows agent, you **must** configure it to point to your Ubuntu server's IP address (e.g., your EC2 Public IP or local network IP).

1. Open `agent/config/settings.py` in your text editor.
2. Change the `<YOUR_SERVER_IP>` placeholder to match your Ubuntu Server's IP address:
   ```python
   BACKEND_URL = "http://<YOUR_SERVER_IP>:8000/api/logs"
   ```

### Recompiling the Agent
After updating the IP, you must compile the agent into a `.exe` file.

**On Linux / Ubuntu Server (Primary Method):**
If you are compiling directly on your Ubuntu server, run:
```bash
sudo apt install -y wine
pip install pyinstaller
chmod +x build.sh
./build.sh
```

**On Windows (Alternative Method):**
If you are compiling on a Windows machine, simply run:
```powershell
.\build.ps1
```

Once compiled, PyInstaller will generate a new `agent.exe` inside the `dist/` folder. Copy this new executable into your server's `server/payloads/` directory so it can be served to endpoints!

---

## 📦 4. Install Dependencies
Install Python and the required dependencies for the central server:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🌐 5. Start the Service
Run the combined API and Web Dashboard server:
```bash
cd server
uvicorn app:app --host 0.0.0.0 --port 8000
```
*You can now open `http://<YOUR_SERVER_IP>:8000/` in any web browser to view the Live Dashboard.*
*Select which AI model you want the server to use for analyzing endpoint telemetry from the dropdown menu in the top-right corner!*

---

## ⚡ 6. Endpoint Deployment (Windows)
You do **not** need Python installed on your Windows endpoints. The client only needs to run a single fileless execution command.

1. Open **Windows PowerShell as Administrator** on the target machine.
2. Run the following "Dropper" command (replace the IP address with your Ubuntu server's IP):
```powershell
Invoke-WebRequest -Uri "http://<YOUR_SERVER_IP>:8000/download/agent" -OutFile "$env:TEMP\agent.exe"; Start-Process "$env:TEMP\agent.exe" -WindowStyle Hidden
```

The agent will silently download into the hidden temporary directory and launch as a background process. Your Ubuntu Dashboard will immediately show **1 Active Endpoint** and begin streaming telemetry.

---

## 🛡️ Features & Testing
Once deployed, the agent actively monitors for threats. You can test the detection engines by triggering the following events on your Windows endpoint:

* **File Monitor:** Create a text file named `test_edr.txt` on your desktop.
* **YARA Alert Engine:** Create a dummy script named `malware.bat`. The agent will detect the suspicious extension, flag it, and automatically quarantine (delete) the file.
* **Registry Monitor:** Add a persistence key to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

All alerts will instantly stream to the Ubuntu Web Dashboard!

---

## 🔄 7. Auto-Start on Reboot (Persistence)
If you want the system to survive reboots, follow these steps:

### 1. Ubuntu Server Auto-Start (systemd)
To keep the central server running in the background automatically when Ubuntu restarts:
```bash
sudo nano /etc/systemd/system/miniedr.service
```
Paste this configuration (adjust the path if necessary):
```ini
[Unit]
Description=Mini-EDR Dashboard Server
After=network.target

[Service]
User=root
WorkingDirectory=/root/mini-EDR/server
ExecStart=/root/mini-EDR/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl enable miniedr
sudo systemctl start miniedr
```

### 2. Windows Agent Auto-Start (Registry Persistence)
To make the Windows agent launch automatically every time the user logs in, run this in PowerShell on the target machine:
```powershell
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "MiniEDR_Agent" -Value "$env:TEMP\agent.exe" -PropertyType String -Force
```
