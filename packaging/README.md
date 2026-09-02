# Agent package build and publish

Endpoint users never receive this repository. Build packages on trusted build machines, verify them, and then copy only the finished package to the Ubuntu server.

## Linux DEB package

Build on an Ubuntu amd64 machine:

```bash
cd /opt/mini-edr
chmod +x packaging/linux/build.sh
./packaging/linux/build.sh
```

The output is `dist/mini-edr-agent-linux-amd64.deb`. Publish it to the central server:

```bash
sudo install -o mini-edr -g mini-edr -m 640 dist/mini-edr-agent-linux-amd64.deb /opt/mini-edr/server/payloads/mini-edr-agent-linux-amd64.deb
sudo systemctl restart mini-edr-server
```

## Windows MSI package

Build on a trusted 64-bit Windows build computer, not on a monitored endpoint. Install Python 3.12, Git, and WiX Toolset first.

```powershell
git clone https://github.com/Pratik-943/mini-EDR.git C:\mini-edr-build
cd C:\mini-edr-build
.\packaging\windows\build.ps1
```

The output is `dist\mini-edr-agent-windows.msi`. Copy it to the Ubuntu server, then publish it:

```bash
sudo install -o mini-edr -g mini-edr -m 640 /path/to/mini-edr-agent-windows.msi /opt/mini-edr/server/payloads/mini-edr-agent-windows.msi
sudo systemctl restart mini-edr-server
```

For real production use, code-sign the MSI before publishing it. In a private VM lab, use the package only after verifying its SHA-256 hash against the build output.
