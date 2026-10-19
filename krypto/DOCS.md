# Fabians-HA-Krypto-Trader

Claude handelt für dich Kryptowährungen: **alle 3 Stunden** (einstellbar) schaut er sich Kurse,
Trends und Nachrichten an und entscheidet, was gekauft, verkauft oder gehalten wird – jeweils mit
Begründung. Standardmäßig wählt er aus den **meistgehandelten Coins der Börse**, auch kleinen. Feste Regeln im Add-on begrenzen das Risiko, egal was Claude entscheidet.

> **Ehrlich gesagt:** Niemand – auch keine KI – kann Gewinne garantieren. Die meisten
> Trading-Bots schneiden auf Dauer schlechter ab als einfaches Halten. Deshalb startet der
> Trader im **Papertrading** (echte Kurse, simuliertes Geld) und vergleicht sich ständig mit
> „nur Bitcoin halten“ und „alle Coins gleich halten“. Erst wenn das über Wochen überzeugt,
> lohnt sich echtes Geld – und dann nur Geld, dessen Verlust du verkraften kannst.

## So läuft es

- **Alle 3 Stunden** entscheidet Claude (über Fabians-HA-Master mit der Anmeldung deines Assistenten). Wird gehandelt, kommt
  sofort eine iMessage mit Begründung; abends (einstellbar) ein Tagesbericht mit Vergleich.
- **Coins:** `auto` = die 40 meistgehandelten Coins mit mindestens 250.000 € Tagesumsatz
  (Stablecoins wie USDT ausgenommen). Oder eine feste Liste, z. B. `BTC,ETH,SOL`.
- **Alle 15 Minuten** prüft das Add-on ohne Claude:
  - **Stop-Loss:** Ein Coin, der z. B. 12 % unter seinem Einkaufspreis liegt, wird verkauft.
  - **Verlustgrenze gesamt:** Liegt das Handelskapital z. B. 20 % unter dem Start, wird alles verkauft und
    gestoppt. Weiter geht es nur, wenn du es freigibst.
- **Weitere feste Regeln:** nie mehr als das Budget (Vorgabe 500 €), höchstens 25 % pro Kauf,
  40 % pro großem Coin (BTC, ETH, SOL, XRP, ADA, DOGE, LINK …) und **10 % pro kleinem Coin**,
  mindestens 10 % Bargeld, höchstens 12 Orders am Tag.
- **Nachrichten:** Claude stützt seine Entscheidungen auf die Nachrichten deiner Quellen
  (Option **Nachrichtenquellen**, vorgegeben CoinDesk, Cointelegraph, Decrypt und BTC-ECHO; jede
  Webseite mit RSS-Feed geht). Eine allgemeine Websuche macht er dann nicht, er darf nur Artikel
  dieser Quellen öffnen. Bei jedem Trade steht, auf welcher Nachricht er beruht. Nachrichten sind
  für Claude nur Information, keine Anweisung, und die festen Regeln gelten trotzdem.
- **Getaggter Gewinn:** Claude kauft und verkauft nach eigenem Ermessen und verkauft immer
  ganz. Vom Gewinn eines Verkaufs bleiben nur volle 10-%-Stufen im Handelsgeld, der Rest wird
  als Euro **getaggt** und nie wieder verwendet:

  | Gewinn beim Verkauf | weiter im Einsatz | getaggt (nicht mehr verwendet) |
  |---|---|---|
  | +4 % (500 → 520 €) | 500 € | 20 € |
  | +12 % | Einkaufspreis + 10 % | 2 % |
  | +27 % | Einkaufspreis + 20 % | 7 % |
  | +39 % | Einkaufspreis + 30 % | 9 % |
  | 50 € → 70 € (+40 %) | 70 € | – |

  Der getaggte Betrag zählt zum Gesamtwert, und beim endgültigen Stopp rechnest du ihn zum
  Gewinn. Im Dashboard steht er unter **Getaggter Gewinn**. Einstellbar unter **Gewinnstufe**
  (0 = aus). Verluste verkleinern einfach das Handelsgeld.
- **Risikobereitschaft** im Dashboard umschaltbar:

  | Stufe | pro Kauf | großer Coin | kleiner Coin | Bargeld mind. | Stop-Loss |
  |---|---|---|---|---|---|
  | 🛡️ Vorsichtig | 15 % | 30 % | 5 % | 30 % | −8 % |
  | ⚖️ Ausgewogen | deine Optionen (Vorgabe 25 / 40 / 10 / 10 / −12 %) |||||
  | 🚀 Mutig | 35 % | 50 % | 20 % | 5 % | −18 % |

  Claude bekommt die Stufe mitgeteilt und richtet seine Entscheidungen danach. Die
  Verlustgrenze gesamt gilt immer. Umstellen kannst nur du – Claude kann die Stufe nicht ändern.
- **Dashboard** in der Seitenleiste (**Krypto**): Wert, Verlauf mit Vergleichslinien, Bestand,
  alle Entscheidungen mit Begründung, Stopp/Not-Aus, CSV-Export.
- **Per iMessage** (über Fabians-HA-Assistent): „Wie läuft der Krypto-Trader?“,
  „Warum hat er gestern verkauft?“, „Trading stopp“, „Not-Aus, alles verkaufen“.

## Einrichtung (Papertrading)

1. **Claude und iMessage:** hier nichts eintragen. Der Trader fragt Claude über den
   **Fabians-HA-Master**, der die Frage an den **Fabians-HA-Assistent** weitergibt (dessen
   Anmeldung). Berichte gehen über den Master an deine Handynummer. Master und Assistent müssen
   laufen.
2. Budget, Coins, Uhrzeit und Grenzen nach Wunsch, Börse für die Kurse (Vorgabe Kraken).
3. Starten. Die erste Entscheidung kommt gleich nach dem Start, dann alle 3 Stunden; im
   Dashboard geht auch „Jetzt entscheiden lassen“.

Jede Entscheidung verbraucht etwas von deinem Claude-Kontingent – alle 3 Stunden sind 8 am Tag.
Kleine Coins schwanken extrem (−30 % an einem Tag kommt vor); Stop-Loss und die 10-%-Grenze
pro kleinem Coin begrenzen das, verhindern Verluste aber nicht.

## „Not logged in · /login“

Diese Meldung heißt: Der Assistent ist bei Claude nicht angemeldet. Lösung: im Master einen
Claude-Token eintragen (oder im Assistenten die claude.ai-Anmeldung importieren) – der Master
startet den Assistenten dann neu. Mit „Claude testen“ auf der Master-Seite prüfst du das.

## Umstellen auf echtes Geld (erst nach einer Testphase!)

1. Bei der Börse ein **eigenes Unterkonto bzw. Portfolio** anlegen und nur das Geld
   hineinlegen, mit dem gehandelt werden darf (z. B. Coinbase Advanced → Portfolios,
   Kraken → Subaccount).
2. Dafür einen **API-Key nur mit Handelsrecht** erstellen – **ohne Auszahlungsrecht**. So kann
   niemand Geld abziehen, selbst wenn der Schlüssel in falsche Hände gerät.
3. Im **Fabians-HA-Master** unter **Krypto-Börse** API-Key und Secret eintragen.
4. Hier im Trader: `mode` = `live`, Börse wählen und bei **Echtgeld-Bestätigung** genau
   `ICH TRAGE DAS RISIKO` schreiben. Neu starten. Ohne diese beiden Einstellungen hier im
   Trader bleibt es beim Papertrading, auch wenn im Master Börsen-Keys stehen.
5. Es beginnt ein neues Konto mit dem Budget. Gehandelt wird höchstens das Budget und nie mehr,
   als wirklich auf dem Konto liegt. Das Papier-Konto wird archiviert.

Claude selbst kann nie auf echtes Geld umschalten, Grenzen ändern oder nach einem Stopp
weitermachen – das geht nur über dich.

## Steuern

In Deutschland sind Gewinne aus Coins, die weniger als ein Jahr gehalten wurden, als privates
Veräußerungsgeschäft steuerpflichtig (Freigrenze 1.000 € pro Jahr). Die Datei
**Trades als CSV** im Dashboard enthält alle Käufe und Verkäufe mit Kurs und Gebühr.
