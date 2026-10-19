"""Ask Claude for structured JSON: through Fabians-HA-Master (the assistant's login), or with an own token (tests)."""

import json
import logging
import os
import re
import subprocess

import fabians_master

log = logging.getLogger("claude")

CLAUDE = os.environ.get("BRAIN_CLAUDE", "claude")
TIMEOUT = 900
LOGIN_HINT = ("Claude ist nicht erreichbar. Das Gedächtnis fragt Claude über Fabians-HA-Master und den "
              "Fabians-HA-Assistenten – sind beide installiert und gestartet, und ist der Assistent angemeldet?")


class ClaudeError(Exception):
    def __init__(self, message: str, temporary: bool = False):
        super().__init__(message)
        self.temporary = temporary  # Claude unreachable: not the info's fault, it waits without counting a try


def source(bridge_url: str = "") -> str:
    """Where Claude is asked: an own token (tests) or the master."""
    return "token" if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") else "master"


def _login_error(text: str) -> bool:
    low = text.lower()
    return "not logged in" in low or "/login" in low or "invalid api key" in low or "oauth" in low and "expired" in low


def _run_local(prompt: str, schema: dict, model: str) -> str:
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema), "--max-turns", "6"]
    if model:
        cmd += ["--model", model]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd="/tmp", stdin=subprocess.DEVNULL)
    except FileNotFoundError as err:
        raise ClaudeError("Claude Code ist nicht installiert") from err
    except subprocess.TimeoutExpired as err:
        raise ClaudeError("Claude hat zu lange gebraucht") from err
    if proc.returncode != 0 and not proc.stdout.strip():
        err = (proc.stderr or "").strip()
        raise ClaudeError(LOGIN_HINT if _login_error(err) else f"Claude-Fehler: {err[-300:]}")
    return proc.stdout


def _run_master(prompt: str, schema: dict, model: str) -> dict:
    try:
        return fabians_master.ask_claude({"prompt": prompt, "schema": schema, "max_turns": 6, "model": model},
                                         timeout=TIMEOUT + 60)
    except fabians_master.MasterError as err:
        text = str(err)
        if _login_error(text):
            raise ClaudeError(LOGIN_HINT) from err
        # Master or assistant not running (yet): not the info's fault, it waits without counting a try.
        raise ClaudeError(f"Claude über Fabians-HA-Master nicht erreichbar: {text[:300]}", temporary=True) from err


def ask(prompt: str, schema: dict, model: str = "", bridge_url: str = "") -> dict:
    """Ask Claude without any tools and return the JSON object that matches the schema."""
    if source() == "master":
        envelope = _run_master(prompt, schema, model)
    else:
        try:
            envelope = json.loads(_run_local(prompt, schema, model))
        except ValueError as err:
            raise ClaudeError("Antwort von Claude nicht lesbar") from err
    if envelope.get("is_error"):
        text = str(envelope.get("result"))
        raise ClaudeError(LOGIN_HINT if _login_error(text) else f"Claude-Fehler: {text[:300]}")
    result = envelope.get("structured_output")
    if not isinstance(result, dict):
        match = re.search(r"\{.*\}", str(envelope.get("result") or ""), re.S)
        if not match:
            raise ClaudeError("Claude hat kein Ergebnis geliefert")
        try:
            result = json.loads(match.group(0))
        except ValueError as err:
            raise ClaudeError("Antwort von Claude nicht lesbar") from err
    if envelope.get("total_cost_usd"):
        log.info("Claude: %.4f $", envelope["total_cost_usd"])
    return result
