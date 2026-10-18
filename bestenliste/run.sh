#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Spieleabend-Bestenliste ..."
cd /app
exec python3 /app/server.py
