pip install pyinstaller
pyinstaller --name agent --onefile --hidden-import loguru --hidden-import yara --hidden-import watchdog --hidden-import psutil --hidden-import win32timezone --hidden-import win32serviceutil --hidden-import agent.utils.forwarder agent/main.py
echo "Build complete! Look inside the 'dist' folder for agent.exe"
