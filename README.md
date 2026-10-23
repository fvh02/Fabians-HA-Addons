# Fabians-HA-Addons

Alle Home-Assistant-Add-ons in einem Repository. **Fabians-HA-Master** verwaltet alle Schlüssel
und verbindet die Add-ons – in den anderen Add-ons trägst du keine Keys oder Tokens mehr ein.

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ffvh02%2FFabians-HA-Addons)

Oder manuell: *Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories* →
`https://github.com/fvh02/Fabians-HA-Addons`.

| Add-on | Was es macht |
|---|---|
| [Fabians-HA-Master](master/DOCS.md) | Alle Schlüssel an einem Ort, Brücke für iMessage, Claude und den Assistenten. **Zuerst installieren.** |
| [Fabians-HA-Assistent](assistent/DOCS.md) | Claude per iMessage und E-Mail (Inkbox): Gedächtnis, Restaurant-Karte, Kalender, Downloads, eBay, Pakete, Stundenplan, Erinnerungen, Übersetzer, 3D-Druck, Krypto, Add-ons |
| [Fabians-HA-Krypto-Trader](krypto/DOCS.md) | Claude handelt Krypto mit festem Budget und Verlustgrenzen, zuerst auf Papier |
| [Fabians-HA-3D-Druck](druck3d/DOCS.md) | Modelle auf Printables finden, slicen und auf dem Bambu Lab P1S drucken |
| [Fabians-HA-Downloader](downloader/DOCS.md) | Warteschlange für Datei-Downloads |
| [Fabians-HA-Video-Downloader](videodownloader/DOCS.md) | YouTube und Videos von beliebigen Webseiten herunterladen, mit Mediathek, optional über Proton VPN |
| [Fabians-HA-Spieleabend](spieleabend/README.md) | 27 Spiele im Browser – Karten-, Zeichen-, Wort-, Quiz-, Party- und Trinkspiele, mit Konten |
| [Fabians-HA-Bestenliste](bestenliste/DOCS.md) | Monatsrangliste, Achievements und Ruhmeshalle für den Spieleabend |
| [Fabians-HA-Urlaub](urlaub/DOCS.md) | Urlaub gemeinsam planen: Unterkünfte vergleichen, Geheimtipps, Kassenzettel aufteilen |
| [Fabians-HA-Gedächtnis](gedaechtnis/DOCS.md) | Langzeitgedächtnis für den Assistenten – ein Obsidian-Vault, den Claude pflegt |
| [Fabians-HA-Karte](karte/DOCS.md) | Deine Restaurant-Karte: der Assistent trägt Besuche mit Speisekarte, Bestellung und Fotos ein und gleicht sie online ab |
| [Fabians-HA-Serien](serien/DOCS.md) | Serien-Kalender: neue Folgen und Staffeln deiner Serien, mit Meldung am Erscheinungstag |
| [Fabians-HA-Werkbank](werkbank/DOCS.md) | Claude konstruiert Teile (build123d) – Maße aus Fotos, Vorschau aufs Handy, Druck nach deinem „Ja“ |
| [Fabians-HA-Pino](pino/DOCS.md) | Pino, ein Kiwi mit eigenem Leben in einer Sandbox-Welt – Gebäude beschreibst du, Claude baut sie |
| [Fabians-HA-Himmel](himmel/DOCS.md) | Himmels-Kalender: ISS-Überflüge, Mondphasen, Sternschnuppen, Finsternisse und klare Nächte |
| [Fabians-HA-Browser](browser/DOCS.md) | Google Chrome in Home Assistant, am PC und Handy bedienbar (nur amd64) |

## So geht's

1. Repository hinzufügen, **Fabians-HA-Master** installieren und starten.
2. In der Seitenleiste **Master** öffnen und die Schlüssel eintragen – oder mit einem Klick aus den
   alten Add-ons übernehmen.
3. Die gewünschten Add-ons installieren und starten. Sie holen sich ihre Schlüssel selbst.

**Umzug von den alten Repositories** (fabiaiagent, HA-downloader-Addon, HA-Games-Addon, HA-Urlaub-Addon, HA-Assistant-Brain): Die neuen
Add-ons laufen neben den alten. Erst Schlüssel übernehmen, dann das alte Add-on stoppen und das
neue starten – beim Assistenten unbedingt in dieser Reihenfolge, zwei Gateways mit derselben
Inkbox-Identität stören sich. Daten in den alten Add-ons (Krypto-Verlauf, Download-Liste,
eBay-Preisalarme, claude.ai-Anmeldung, Spieleabend-Konten und Bestenliste, Urlaube) ziehen nicht
automatisch mit.

Alle Ideen für weitere Add-ons stehen in einer Liste: [ideen/](ideen/README.md).

Schlüssel gehören ausschließlich in den Master, nie in dieses Repository.
Das Internet-Setup (Cloudflare Tunnel) steht in [TUNNEL.md](TUNNEL.md).

![Spieleabend](bilder/spieleabend/start.jpg)
