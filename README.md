# Mini-EDR (Endpoint Detection and Response)

Mini-EDR is a lightweight, cross-platform security architecture designed to monitor Windows endpoints and stream live threat telemetry to a centralized Ubuntu command server. 

It features an invisible, fileless agent deployment, real-time YARA scanning, active threat quarantine, and a live web dashboard.

---

## 🏗️ Architecture
1. **Central Command Server (Ubuntu):** A FastAPI backend that receives telemetry, logs alerts, and hosts the live web dashboard.
2. **Endpoint Agent (Windows):** A compiled, hidden executable that monitors processes, network connections, file modifications, and registry persistence.

---

## 🚀 1. Server Setup (Ubuntu)
All configuration and monitoring is done exclusively on the Ubuntu Server.

### Installation
Clone this repository to your Ubuntu server and navigate into the directory:
```bash
git clone https://github.com/Pratik-943/mini-EDR.git
cd mini-EDR
```

### Setup Environment
Install Python and the required dependencies:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start the Server
Run the combined API and Web Dashboard server:
```bash
cd server
uvicorn app:app --host 0.0.0.0 --port 8000
```
*You can now open `http://<UBUNTU_IP>:8000/` in any web browser to view the Live Dashboard.*

---

## ⚡ 2. Endpoint Deployment (Windows)
You do **not** need Python installed on your Windows endpoints. The client only needs to run a single fileless execution command.

1. Open **Windows PowerShell as Administrator** on the target machine.
2. Run the following "Dropper" command (replace the IP address with your Ubuntu server's IP):
```powershell
Invoke-WebRequest -Uri "http://192.168.X.X:8000/download/agent" -OutFile "$env:TEMP\agent.exe"; Start-Process "$env:TEMP\agent.exe" -WindowStyle Hidden
```

The agent will silently download into the hidden temporary directory and launch as a background process. Your Ubuntu Dashboard will immediately show **1 Active Endpoint** and begin streaming telemetry.

---

## 🛠️ Advanced: Recompiling the Agent
*(Note: A pre-compiled `agent.exe` is already included in the `dist/` folder of this repository. You only need to follow these steps if you change the backend IP address or modify the agent code.)*

If you need to change the Hardcoded IP Address for the agent, you must recompile the payload.

1. Open `agent/config/settings.py` and modify `BACKEND_URL` to match your Ubuntu Server IP.
2. Run the build script:
   
   **On Linux/Ubuntu:**
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
   
   **On Windows:**
   ```powershell
   .\build.ps1
   ```
3. PyInstaller will generate a new executable inside the `dist/` folder.
4. Copy this new executable into the `server/payloads/` directory. The deployment command will now serve your updated payload!

---

## 🛡️ Features & Testing
Once deployed, the agent actively monitors for threats. You can test the detection engines by triggering the following events on your Windows endpoint:

* **File Monitor:** Create a text file named `test_edr.txt` on your desktop.
* **YARA Alert Engine:** Create a dummy script named `malware.bat`. The agent will detect the suspicious extension, flag it, and automatically quarantine (delete) the file.
* **Registry Monitor:** Add a persistence key to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

All alerts will instantly stream to the Ubuntu Web Dashboard!
