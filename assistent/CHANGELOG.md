# Changelog

## 0.13.0

- Umgezogen nach **Fabians-HA-Addons** und umbenannt in **Fabians-HA-Assistent**.
- Alle Schlüssel (Inkbox, Claude, Apple, eBay) kommen aus **Fabians-HA-Master**; die Felder in der
  Konfiguration sind weg. Downloader, 3D-Druck und Krypto-Trader werden über den Master gefunden,
  Adressen einzutragen entfällt. Preisalarme gehen an die Handynummer aus dem Master.
- Die Claude-Brücke nimmt nur noch Anfragen des Masters an; kein Schlüssel mehr in `/share`.
