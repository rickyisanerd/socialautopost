import hashlib
import hmac
import base64
import time
import uuid
import urllib.parse
import httpx
from app.platforms.base import PlatformClient

API_BASE = "https://api.twitter.com"


class XTwitterClient(PlatformClient):
    platform_name = "x"

    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret

    def _oauth_signature(self, method: str, url: str, params: dict) -> str:
        sorted_params = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(params.items()))
        base_string = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
        signing_key = f"{urllib.parse.quote(self.api_secret, safe='')}&{urllib.parse.quote(self.access_token_secret, safe='')}"
        signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
        return base64.b64encode(signature.digest()).decode()

    def _oauth_header(self, method: str, url: str) -> str:
        oauth_params = {
            "oauth_consumer_key": self.api_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token,
            "oauth_version": "1.0",
        }
        oauth_params["oauth_signature"] = self._oauth_signature(method, url, oauth_params)
        header = ", ".join(f'{k}="{urllib.parse.quote(str(v), safe="")}"' for k, v in sorted(oauth_params.items()))
        return f"OAuth {header}"

    async def verify_credentials(self) -> bool:
        url = f"{API_BASE}/2/users/me"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"Authorization": self._oauth_header("GET", url)})
            return r.status_code == 200

    async def _upload_media(self, image_path: str) -> str | None:
        url = "https://upload.twitter.com/1.1/media/upload.json"
        async with httpx.AsyncClient(timeout=60) as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    url,
                    headers={"Authorization": self._oauth_header("POST", url)},
                    files={"media": f},
                )
            if r.status_code == 200:
                return r.json().get("media_id_string")
        return None

    async def post(self, text: str, image_path: str | None = None) -> dict:
        url = f"{API_BASE}/2/tweets"
        payload = {"text": text}

        if image_path:
            media_id = await self._upload_media(image_path)
            if media_id:
                payload["media"] = {"media_ids": [media_id]}

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": self._oauth_header("POST", url),
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = r.json()
            if "data" in data and "id" in data["data"]:
                return {"success": True, "post_id": data["data"]["id"], "error": ""}
            return {"success": False, "post_id": "", "error": str(data)}
