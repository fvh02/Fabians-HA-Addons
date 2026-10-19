#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Karte ..."
cd /app
exec python3 /app/server.py
