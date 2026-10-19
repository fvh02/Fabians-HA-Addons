#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Urlaubsplaner ..."
cd /app
exec python3 /app/server.py
