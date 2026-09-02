#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="$ROOT/.build/linux-agent"
VENV_DIR="$BUILD_DIR/venv"
STAGE_DIR="$BUILD_DIR/stage"
DIST_DIR="$ROOT/dist"
VERSION="0.2.0"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip pyinstaller
"$VENV_DIR/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$VENV_DIR/bin/pyinstaller" --noconfirm --clean --onefile --name mini-edr-agent --paths "$ROOT" --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/work" --specpath "$BUILD_DIR/spec" "$ROOT/agent/main.py"

install -d "$STAGE_DIR/DEBIAN" "$STAGE_DIR/opt/mini-edr-agent" "$STAGE_DIR/usr/local/bin" "$STAGE_DIR/lib/systemd/system"
install -m 755 "$BUILD_DIR/dist/mini-edr-agent" "$STAGE_DIR/opt/mini-edr-agent/mini-edr-agent"
ln -s /opt/mini-edr-agent/mini-edr-agent "$STAGE_DIR/usr/local/bin/mini-edr-agent"

cat > "$STAGE_DIR/DEBIAN/control" <<EOF
Package: mini-edr-agent
Version: $VERSION
Section: admin
Priority: optional
Architecture: amd64
Maintainer: mini-EDR
Description: mini-EDR endpoint monitoring agent
EOF

cat > "$STAGE_DIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
systemctl daemon-reload
exit 0
EOF
chmod 755 "$STAGE_DIR/DEBIAN/postinst"

cat > "$STAGE_DIR/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
systemctl stop mini-edr-agent.service || true
systemctl disable mini-edr-agent.service || true
exit 0
EOF
chmod 755 "$STAGE_DIR/DEBIAN/prerm"

cat > "$STAGE_DIR/lib/systemd/system/mini-edr-agent.service" <<'EOF'
[Unit]
Description=mini-EDR endpoint agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/mini-edr-agent/mini-edr-agent run
Restart=always
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

dpkg-deb --build --root-owner-group "$STAGE_DIR" "$DIST_DIR/mini-edr-agent-linux-amd64.deb"
echo "Built $DIST_DIR/mini-edr-agent-linux-amd64.deb"
