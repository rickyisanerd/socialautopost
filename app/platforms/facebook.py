import httpx
from app.platforms.base import PlatformClient

GRAPH_API = "https://graph.facebook.com/v21.0"


class FacebookClient(PlatformClient):
    platform_name = "facebook"

    def __init__(self, page_id: str, access_token: str):
        self.page_id = page_id
        self.access_token = access_token

    async def verify_credentials(self) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{GRAPH_API}/{self.page_id}",
                params={"access_token": self.access_token},
            )
            return r.status_code == 200

    async def post(self, text: str, image_path: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            if image_path:
                with open(image_path, "rb") as f:
                    r = await client.post(
                        f"{GRAPH_API}/{self.page_id}/photos",
                        data={"message": text, "access_token": self.access_token},
                        files={"source": ("image.png", f, "image/png")},
                    )
            else:
                r = await client.post(
                    f"{GRAPH_API}/{self.page_id}/feed",
                    data={"message": text, "access_token": self.access_token},
                )

            data = r.json()
            if "id" in data:
                return {"success": True, "post_id": data["id"], "error": ""}
            return {"success": False, "post_id": "", "error": data.get("error", {}).get("message", str(data))}
