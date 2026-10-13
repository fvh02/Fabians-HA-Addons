#!/bin/sh
echo "[master] Starte Fabians-HA-Master ..."
cd /app
exec python3 /app/server.py
