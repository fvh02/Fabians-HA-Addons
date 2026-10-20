#!/usr/bin/with-contenv bashio
# with-contenv: the base image's init resets the environment; this brings back SUPERVISOR_TOKEN,
# without which the master can neither see the add-ons nor hand out their keys.
bashio::log.info "Starte Fabians-HA-Master ..."
cd /app
exec python3 /app/server.py
