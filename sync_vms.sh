#!/bin/bash
# Script untuk sync file VMS setelah edit
# Jalankan dari: /home/frappe/frappe-bench-v16/apps/visitor_management/

BASE="/home/frappe/frappe-bench-v16/apps/visitor_management"
SRC="$BASE/visitor_management"
DST="$BASE/visitor_management/visitor_management"

echo "=== Syncing VMS files ==="
cp $SRC/doctype/visitor/visitor.py        $DST/doctype/visitor/visitor.py
cp $SRC/doctype/visitor_log/visitor_log.py $DST/doctype/visitor_log/visitor_log.py
cp $SRC/api.py                             $DST/api.py

echo "Menghapus cache..."
find $BASE -name "*.pyc" -delete
find $BASE -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

cd /home/frappe/frappe-bench-v16
bench --site wp.local clear-cache
bench restart
echo "=== Selesai! ==="
