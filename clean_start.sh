#!/bin/bash
echo "================================"
echo "CLEAN START - Web SSH Client"
echo "================================"

# Hentikan semua proses Python
pkill -f "python.*app.py" 2>/dev/null
echo "✓ Server dihentikan"

# Hapus database lama
rm -rf instance/
echo "✓ Database lama dihapus"

# Hapus cache
rm -rf __pycache__/
rm -f *.pyc
echo "✓ Cache dibersihkan"

# Buat struktur folder
mkdir -p instance
echo "✓ Struktur folder dibuat"

echo ""
echo "✅ SEMUA SIAP!"
echo "Jalankan server dengan:"
echo "python3 app.py"
echo "================================"


# Application : Web SSH Client
# This application build with Python3 for access server via web SSH
# Build by : herdiana3389 (https://sys-ops.id)
# License : MIT (Open Source)
# Repository : https://hub.docker.com/r/sysopsid/web-ssh-client