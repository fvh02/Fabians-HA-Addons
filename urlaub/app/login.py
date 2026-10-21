"""Sign in with Google and Apple (OpenID Connect, authorization code flow with PKCE).

The keys come from Fabians-HA-Master. The ID token is fetched by the server itself straight from the
provider's token endpoint over TLS, so its signature does not have to be checked (OpenID Connect Core
3.1.3.7); issuer, audience, expiry and nonce are.
"""

import base64
import hashlib
import json
import re
import secrets
import time
from urllib.parse import urlencode

import aiohttp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

STATE_TTL = 600
PROVIDERS = {
    "google": {"title": "Google", "auth": "https://accounts.google.com/o/oauth2/v2/auth",
               "token": "https://oauth2.googleapis.com/token", "iss": ("https://accounts.google.com", "accounts.google.com"),
               "scope": "openid email profile"},
    "apple": {"title": "Apple", "auth": "https://appleid.apple.com/auth/authorize",
              "token": "https://appleid.apple.com/auth/token", "iss": ("https://appleid.apple.com",),
              "scope": "name email"},
}


class LoginError(Exception):
    pass


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64u(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def apple_key(text: str):
    """The .p8 key from the master. Its single-line input loses the line breaks, so the PEM is rebuilt."""
    body = re.sub(r"-----[A-Z ]+-----", "", re.sub(r"-----(BEGIN|END)PRIVATEKEY-----", "", text))
    body = re.sub(r"\s+", "", body)
    pem = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(body[i:i + 64] for i in range(0, len(body), 64)) + "\n-----END PRIVATE KEY-----\n"
    try:
        return serialization.load_pem_private_key(pem.encode(), password=None)
    except ValueError as err:
        raise LoginError("Der Apple-Schlüssel (.p8) im Fabians-HA-Master ist ungültig") from err


class Login:
    def __init__(self, keys: dict):
        k = {key: str(value or "").strip() for key, value in keys.items()}
        self.google = (k.get("google_client_id"), k.get("google_client_secret"))
        self.apple = (k.get("apple_client_id"), k.get("apple_team_id"), k.get("apple_key_id"), k.get("apple_private_key"))
        self.pending: dict[str, dict] = {}

    def available(self) -> list[str]:
        out = []
        if all(self.google):
            out.append("google")
        if all(self.apple):
            out.append("apple")
        return out

    def client_id(self, provider: str) -> str:
        return self.google[0] if provider == "google" else self.apple[0]

    def client_secret(self, provider: str) -> str:
        if provider == "google":
            return self.google[1]
        client_id, team_id, key_id, p8 = self.apple
        now = int(time.time())
        head = b64u(json.dumps({"alg": "ES256", "kid": key_id}).encode())
        body = b64u(json.dumps({"iss": team_id, "iat": now, "exp": now + 300, "aud": "https://appleid.apple.com", "sub": client_id}).encode())
        r, s = decode_dss_signature(apple_key(p8).sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
        return f"{head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"

    def start(self, provider: str, redirect_uri: str) -> tuple[str, str]:
        """Authorization URL and the state, which the page also keeps in a cookie."""
        if provider not in self.available():
            raise LoginError(f"Die Anmeldung mit {PROVIDERS.get(provider, {}).get('title', provider)} ist nicht eingerichtet")
        now = time.time()
        for key in [k for k, v in self.pending.items() if now - v["at"] > STATE_TTL]:
            del self.pending[key]
        state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        self.pending[state] = {"provider": provider, "nonce": nonce, "verifier": verifier, "redirect": redirect_uri, "at": now}
        params = {"client_id": self.client_id(provider), "redirect_uri": redirect_uri, "response_type": "code",
                  "scope": PROVIDERS[provider]["scope"], "state": state, "nonce": nonce,
                  "code_challenge": b64u(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
        if provider == "apple":
            params["response_mode"] = "form_post"      # Apple only sends name and e-mail this way
        else:
            params["prompt"] = "select_account"
        return PROVIDERS[provider]["auth"] + "?" + urlencode(params), state

    async def finish(self, provider: str, state: str, cookie: str, code: str, user_json: str = "") -> dict:
        """Exchanges the code; returns {provider, sub, email, name}."""
        pending = self.pending.pop(state, None)
        if not pending or pending["provider"] != provider or not secrets.compare_digest(state, cookie or ""):
            raise LoginError("Die Anmeldung ist abgelaufen oder wurde in einem anderen Browser gestartet – bitte noch einmal")
        if time.time() - pending["at"] > STATE_TTL:
            raise LoginError("Die Anmeldung hat zu lange gedauert – bitte noch einmal")
        if not code:
            raise LoginError("Die Anmeldung wurde abgebrochen")
        form = {"grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect"],
                "client_id": self.client_id(provider), "client_secret": self.client_secret(provider),
                "code_verifier": pending["verifier"]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(PROVIDERS[provider]["token"], data=form, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise LoginError(f"{PROVIDERS[provider]['title']} ist gerade nicht erreichbar") from err
        if not isinstance(data, dict) or "id_token" not in data:
            detail = data.get("error_description") or data.get("error") if isinstance(data, dict) else ""
            raise LoginError(f"{PROVIDERS[provider]['title']} hat die Anmeldung abgelehnt{': ' + str(detail) if detail else ''}")
        try:
            claims = json.loads(unb64u(data["id_token"].split(".")[1]))
        except (ValueError, IndexError) as err:
            raise LoginError("Unerwartete Antwort bei der Anmeldung") from err
        aud = claims.get("aud")
        if (claims.get("iss") not in PROVIDERS[provider]["iss"] or self.client_id(provider) not in (aud if isinstance(aud, list) else [aud])
                or float(claims.get("exp", 0)) < time.time() - 60 or claims.get("nonce") != pending["nonce"] or not claims.get("sub")):
            raise LoginError("Die Anmeldung konnte nicht bestätigt werden – bitte noch einmal")
        name = str(claims.get("given_name") or claims.get("name") or "")
        if provider == "apple" and user_json:      # Apple sends the name only at the very first sign-in
            try:
                n = json.loads(user_json).get("name") or {}
                name = n.get("firstName") or name
            except (ValueError, AttributeError):
                pass
        email = str(claims.get("email") or "") if str(claims.get("email_verified", "true")).lower() == "true" else ""
        return {"provider": provider, "sub": str(claims["sub"]), "email": email[:120], "name": re.sub(r"\s+", " ", name).strip()[:30]}
