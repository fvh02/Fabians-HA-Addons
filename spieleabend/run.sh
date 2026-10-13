#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Spieleabend ..."
cd /app
exec python3 /app/server.py
