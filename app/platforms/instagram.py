import httpx
from app.platforms.base import PlatformClient

GRAPH_API = "https://graph.facebook.com/v21.0"


class InstagramClient(PlatformClient):
    """Instagram Graph API requires a public image URL — we upload to Facebook first
    and use that URL, or the business must provide an image hosting solution."""

    platform_name = "instagram"

    def __init__(self, ig_account_id: str, access_token: str):
        self.ig_account_id = ig_account_id
        self.access_token = access_token

    async def verify_credentials(self) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{GRAPH_API}/{self.ig_account_id}",
                params={"access_token": self.access_token, "fields": "id,username"},
            )
            return r.status_code == 200

    async def post(self, text: str, image_url: str | None = None) -> dict:
        if not image_url:
            return {"success": False, "post_id": "", "error": "Instagram requires an image URL"}

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create media container
            r = await client.post(
                f"{GRAPH_API}/{self.ig_account_id}/media",
                data={
                    "image_url": image_url,
                    "caption": text,
                    "access_token": self.access_token,
                },
            )
            data = r.json()
            if "id" not in data:
                return {"success": False, "post_id": "", "error": data.get("error", {}).get("message", str(data))}

            container_id = data["id"]

            # Step 2: Publish the container
            r = await client.post(
                f"{GRAPH_API}/{self.ig_account_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            data = r.json()
            if "id" in data:
                return {"success": True, "post_id": data["id"], "error": ""}
            return {"success": False, "post_id": "", "error": data.get("error", {}).get("message", str(data))}
