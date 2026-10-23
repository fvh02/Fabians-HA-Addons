"""Connection to Fabians-HA-Master: keys, iMessages and Claude all come from there.

The master is found by the add-on's own host name (e.g. "1a2b3c4d-krypto" → "1a2b3c4d-master"), so
nothing has to be entered. It recognises the calling add-on by its address and only hands out the
keys that add-on needs.

Canonical copy: shared/fabians_master.py – the add-ons carry identical copies (tools/sync-shared.sh).
"""

import base64
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request

log = logging.getLogger("master")
PORT = 8090
# Add-ons talk to each other inside Home Assistant: never through a proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class MasterError(Exception):
    pass


def url() -> str:
    env = os.environ.get("FABIANS_MASTER_URL", "").strip()
    if env:
        return env.rstrip("/")
    host = socket.gethostname()
    prefix = host.split("-", 1)[0] if "-" in host else "local"
    return f"http://{prefix}-master:{PORT}"


def _call(method: str, path: str, body: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url() + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        text = err.read().decode(errors="replace")
        try:
            text = json.loads(text).get("error") or text
        except ValueError:
            pass
        raise MasterError(text[-400:] or f"Fehler {err.code}") from err
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise MasterError(f"Fabians-HA-Master nicht erreichbar ({url()}) – ist es installiert und gestartet?") from err


def keys(wait: float | None = None) -> dict:
    """The keys of this add-on. The master may still be starting, so this waits for it:
    wait=None waits as long as it takes, a number waits at most that many seconds and then returns {}."""
    started, warned = time.time(), 0.0
    while True:
        try:
            return _call("GET", "/api/keys")
        except MasterError as err:
            if wait is not None and time.time() - started >= wait:
                log.warning("%s – ohne Schlüssel weiter", err)
                return {}
            if time.time() - warned > 60:
                log.warning("%s – warte ...", err)
                warned = time.time()
            time.sleep(5)


def notify(text: str, image: bytes | None = None, filename: str = "bild.jpg") -> bool:
    """Send an iMessage to the owner through the master."""
    body: dict = {"text": text}
    if image:
        body.update(image_b64=base64.b64encode(image).decode(), filename=filename)
    try:
        return bool(_call("POST", "/api/notify", body, timeout=60).get("sent"))
    except MasterError as err:
        log.warning("iMessage nicht gesendet: %s", err)
        return False


def ask_claude(request: dict, timeout: float = 1000) -> dict:
    """Ask Claude through the master (it uses the assistant's login). Returns Claude Code's JSON result."""
    return _call("POST", "/api/claude", request, timeout=timeout)
