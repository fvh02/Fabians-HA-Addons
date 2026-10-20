#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Serien-Kalender ..."
cd /app
exec python3 /app/server.py
