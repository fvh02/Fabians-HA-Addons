#!/usr/bin/with-contenv bashio
bashio::log.info "Starte Himmels-Kalender ..."
cd /app
exec python3 /app/server.py
