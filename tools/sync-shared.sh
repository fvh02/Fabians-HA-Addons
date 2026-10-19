#!/bin/sh
# Copies the master client into every add-on that uses it (each add-on is built on its own).
cd "$(dirname "$0")/.."
for app in krypto/app druck3d/app downloader/app videodownloader/app spieleabend/app bestenliste/app urlaub/app gedaechtnis/app; do
  cp shared/fabians_master.py "$app/fabians_master.py"
done
echo "fabians_master.py verteilt"
