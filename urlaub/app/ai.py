"""Claude for the three jobs that need judgement: reading receipts, ranking accommodations and
picking spots. Every call asks for JSON that matches a schema, so the answers can be used directly.

The model can be changed in the add-on options; a declined request is re-run on Anthropic's
recommended fallback model (server-side), so a single refusal doesn't break a feature.
"""

import base64
import json
import logging

import anthropic

log = logging.getLogger("urlaub.ai")

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIError(Exception):
    """Shown to the user as is."""


class AI:
    def __init__(self, api_key: str, model: str):
        self.model = model or "claude-opus-5-5"
        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=3, timeout=180) if api_key else None

    @property
    def ready(self) -> bool:
        return self.client is not None

    async def _json(self, system: str, content: list, schema: dict, effort: str = "medium", max_tokens: int = 16000) -> dict:
        if not self.client:
            raise AIError("Für diese Funktion fehlt der Anthropic-API-Key (Fabians-HA-Master → Claude)")
        params = dict(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
        try:
            try:
                response = await self.client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
            except anthropic.BadRequestError as err:
                # e.g. a model chosen in the options that has no fallback – plain request instead
                log.info("Anfrage ohne Fallback wiederholt: %s", err.message)
                response = await self.client.messages.create(**params)
        except anthropic.AuthenticationError:
            raise AIError("Der Anthropic-API-Key ist ungültig – bitte im Fabians-HA-Master prüfen")
        except anthropic.PermissionDeniedError:
            raise AIError("Der API-Key darf dieses Modell nicht nutzen (Add-on-Einstellungen → Modell)")
        except anthropic.NotFoundError:
            raise AIError(f"Das Modell „{self.model}“ gibt es nicht – bitte in den Add-on-Einstellungen ändern")
        except anthropic.RateLimitError:
            raise AIError("Zu viele Anfragen an Claude – bitte gleich noch einmal versuchen")
        except anthropic.BadRequestError as err:
            raise AIError(f"Claude hat die Anfrage abgelehnt: {err.message}")
        except anthropic.APIStatusError as err:
            raise AIError(f"Claude ist gerade nicht erreichbar ({err.status_code}) – bitte später noch einmal")
        except anthropic.APIConnectionError:
            raise AIError("Keine Verbindung zu Claude – ist der Server online?")
        if response.stop_reason == "refusal":
            raise AIError("Claude hat diese Anfrage nicht bearbeitet")
        if response.stop_reason == "max_tokens":
            raise AIError("Die Antwort war zu lang – bitte mit weniger Daten noch einmal versuchen")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except ValueError:
            log.warning("Keine gültige JSON-Antwort: %s", text[:300])
            raise AIError("Claude hat keine verwertbare Antwort geliefert – bitte noch einmal versuchen")

    # -- receipts -------------------------------------------------------------------------------
    async def read_receipt(self, image: bytes, media_type: str, tags: list[dict]) -> dict:
        tag_lines = "\n".join(f"- {t['id']}: {t['name']}" + (f" (gehört zu {t['parent']})" if t.get("parent") else "") for t in tags)
        system = (
            "Du liest Kassenzettel für eine Urlaubsgruppe, die ihre Einkäufe fair aufteilt. Gib jeden gekauften Artikel "
            "als eigene Zeile zurück, genau wie auf dem Bon (Menge und Zeilenpreis inklusive Mehrwertsteuer). Rabatte, "
            "Pfand-Rückgaben und Gutscheine sind Zeilen mit negativem Preis; ordne einen Rabatt den Merkmalen des Artikels "
            "zu, auf den er sich bezieht. Pfand für Flaschen bekommt dieselben Merkmale wie das Getränk.\n\n"
            "Merkmale steuern, wer einen Artikel mitbezahlt: Bier bezahlen nur Biertrinker usw. Vergib nur Merkmale aus "
            "dieser Liste und nur, wenn sie eindeutig passen; Alltägliches (Brot, Wasser, Spülmittel …) bekommt keine "
            f"Merkmale.\n{tag_lines}\n\nKürze Artikelnamen nicht ab, sondern schreibe sie verständlich aus "
            "(z. B. „Becks Pils 0,5 l“ statt „BECKS P 0,5“). Unlesbares markierst du mit unsicher=true."
        )
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["laden", "datum", "waehrung", "summe", "artikel", "ist_kassenzettel"],
            "properties": {
                "ist_kassenzettel": {"type": "boolean"},
                "laden": {"type": "string"},
                "datum": {"type": "string", "description": "YYYY-MM-DD oder leer"},
                "waehrung": {"type": "string", "description": "ISO-Code, z. B. EUR"},
                "summe": {"type": "number", "description": "Gesamtsumme laut Bon"},
                "artikel": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["name", "menge", "preis", "merkmale", "unsicher"],
                    "properties": {
                        "name": {"type": "string"},
                        "menge": {"type": "number"},
                        "preis": {"type": "number", "description": "Zeilenpreis (Menge × Einzelpreis), negativ bei Rabatt"},
                        "merkmale": {"type": "array", "items": {"type": "string", "enum": [t["id"] for t in tags] or ["-"]}},
                        "unsicher": {"type": "boolean"},
                    }}},
            },
        }
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(image).decode()}},
            {"type": "text", "text": "Lies diesen Kassenzettel."},
        ]
        return await self._json(system, content, schema, effort="medium")

    # -- accommodations -----------------------------------------------------------------------------
    async def rank_stays(self, trip: dict, stays: list[dict]) -> dict:
        system = (
            "Du hilfst einer Gruppe, die beste Unterkunft für ihren Urlaub zu finden. Bewerte jede Unterkunft auf einer "
            "Skala von 0 bis 10 in drei Bereichen: Lage (Nähe zu Zentrum, Strand/Natur, Restaurants, Supermarkt, "
            "Nahverkehr – nutze die mitgelieferten Entfernungen und Orte in der Nähe), Komfort (Schlafplätze für die "
            "Gruppe, Ausstattung, Bewertungen, Zustand) und Preis (Preis pro Person und Nacht im Vergleich zu den "
            "anderen und zum Gebotenen). Fehlen Angaben, bewerte vorsichtig und sag, was fehlt. Wähle danach die drei "
            "besten aus und begründe kurz und konkret auf Deutsch, für wen sie am besten passen."
        )
        schema = {
            "type": "object", "additionalProperties": False, "required": ["bewertungen", "top3", "fazit"],
            "properties": {
                "bewertungen": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["id", "lage", "komfort", "preis", "gesamt", "plus", "minus", "fehlt"],
                    "properties": {
                        "id": {"type": "integer"},
                        "lage": {"type": "number"}, "komfort": {"type": "number"}, "preis": {"type": "number"},
                        "gesamt": {"type": "number"},
                        "plus": {"type": "array", "items": {"type": "string"}},
                        "minus": {"type": "array", "items": {"type": "string"}},
                        "fehlt": {"type": "array", "items": {"type": "string"}},
                    }}},
                "top3": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["id", "warum"],
                    "properties": {"id": {"type": "integer"}, "warum": {"type": "string"}}}},
                "fazit": {"type": "string"},
            },
        }
        text = json.dumps({"urlaub": trip, "unterkuenfte": stays}, ensure_ascii=False)
        return await self._json(system, [{"type": "text", "text": text}], schema, effort="high")

    # -- spots --------------------------------------------------------------------------------------
    async def pick_spots(self, trip: dict, candidates: list[dict], wishes: str) -> dict:
        system = (
            "Du bist ein Reisekenner, der für eine Gruppe die coolsten Orte rund um ihr Urlaubsziel auswählt – gerade "
            "auch weniger bekannte: versteckte Buchten, Aussichtspunkte, Wasserfälle, Ruinen, kleine Bars und "
            "Biergärten, besondere Orte der Einheimischen. Wähle 12 bis 18 Orte NUR aus der Kandidatenliste (über ihre "
            "id) – erfinde keine Orte. Mische Kategorien, meide reine Massenattraktionen wenn es bessere Alternativen "
            "gibt, und markiere echte Geheimtipps. Beschreibe jeden Ort in 1–2 lebendigen Sätzen auf Deutsch und gib "
            "einen praktischen Tipp (beste Zeit, was mitnehmen, worauf achten). Sag nichts, was du nicht sicher weißt; "
            "nutze ansonsten die Angaben der Kandidaten."
        )
        schema = {
            "type": "object", "additionalProperties": False, "required": ["spots"],
            "properties": {"spots": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "titel", "kategorie", "geheimtipp", "beschreibung", "tipp"],
                "properties": {
                    "id": {"type": "string"},
                    "titel": {"type": "string"},
                    "kategorie": {"type": "string", "enum": ["Natur", "Aussicht", "Baden", "Kultur", "Essen & Trinken", "Nachtleben", "Aktiv"]},
                    "geheimtipp": {"type": "boolean"},
                    "beschreibung": {"type": "string"},
                    "tipp": {"type": "string"},
                }}}},
        }
        text = json.dumps({"urlaub": trip, "wuensche_der_gruppe": wishes, "kandidaten": candidates}, ensure_ascii=False)
        return await self._json(system, [{"type": "text", "text": text}], schema, effort="medium")
