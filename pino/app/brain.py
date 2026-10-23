"""Pino's brain: a small language model in Ollama (on another computer in the home network).

Every question asks for JSON that matches a schema (Ollama's "format"), so even a 3B model answers in a
form the add-on can check. If Ollama cannot be reached, BrainAsleep is raised and Pino dozes until it is back.
"""

import json
import logging

import aiohttp

log = logging.getLogger("brain")
TIMEOUT = 240


class BrainAsleep(Exception):
    """Ollama is not reachable (laptop off, wrong address, model missing)."""


class Brain:
    def __init__(self, url: str, model: str):
        self.url = url.rstrip("/")
        self.model = model or "qwen2.5:3b"
        self.http: aiohttp.ClientSession | None = None
        self.last_error = ""
        self.calls = 0

    @property
    def configured(self) -> bool:
        return bool(self.url)

    async def ask(self, system: str, prompt: str, schema: dict, temperature: float = 0.8, tokens: int = 400) -> dict:
        if not self.url:
            raise BrainAsleep("Keine Ollama-Adresse eingetragen (Option ollama_url)")
        body = {"model": self.model, "stream": False, "format": schema, "keep_alive": "30m",
                "options": {"temperature": temperature, "num_ctx": 4096, "num_predict": tokens},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        try:
            async with self.http.post(self.url + "/api/chat", json=body,
                                      timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
                text = await resp.text()
                if resp.status == 404 and "model" in text.lower():
                    raise BrainAsleep(f"Modell {self.model} fehlt auf dem Laptop – dort „ollama pull {self.model}“ ausführen")
                if resp.status >= 300:
                    raise BrainAsleep(f"Ollama meldet Fehler {resp.status}: {text[:200]}")
                data = json.loads(text)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            self.last_error = (f"Gehirn nicht erreichbar ({self.url}) – ist der Laptop an und läuft Ollama?"
                               if not isinstance(err, ValueError) else "Ollama hat unlesbar geantwortet")
            raise BrainAsleep(self.last_error) from err
        except BrainAsleep as err:
            self.last_error = str(err)
            raise
        self.last_error = ""
        self.calls += 1
        content = (data.get("message") or {}).get("content") or ""
        try:
            result = json.loads(content)
        except ValueError:
            start, end = content.find("{"), content.rfind("}")
            try:
                result = json.loads(content[start:end + 1]) if start >= 0 else {}
            except ValueError:
                result = {}
        return result if isinstance(result, dict) else {}

    async def ping(self) -> bool:
        if not self.url:
            return False
        try:
            async with self.http.get(self.url + "/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False
