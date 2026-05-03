#!/bin/bash
# Script untuk refresh VMS setelah edit.
# Source aktif ada di visitor_management/visitor_management/.
# Folder duplicate visitor_management/doctype sudah dihapus agar tidak saling menimpa.

BASE="/home/frappe/frappe-bench-v16/apps/visitor_management"

echo "=== Refreshing VMS ==="

echo "Menghapus cache..."
find $BASE -name "*.pyc" -delete
find $BASE -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

cd /home/frappe/frappe-bench-v16
bench --site wp.local clear-cache
bench restart
echo "=== Selesai! ==="
