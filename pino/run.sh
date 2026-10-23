#!/usr/bin/with-contenv bashio
bashio::log.info "Pino wacht auf ..."
cd /app
exec python3 /app/server.py
