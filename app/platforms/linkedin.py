import httpx
from app.platforms.base import PlatformClient

API_BASE = "https://api.linkedin.com/v2"


class LinkedInClient(PlatformClient):
    platform_name = "linkedin"

    def __init__(self, access_token: str, org_id: str):
        self.access_token = access_token
        self.org_id = org_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def verify_credentials(self) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}/me", headers=self._headers())
            return r.status_code == 200

    async def _upload_image(self, image_path: str) -> str | None:
        author = f"urn:li:organization:{self.org_id}"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ],
            }
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{API_BASE}/assets?action=registerUpload",
                headers=self._headers(),
                json=register_payload,
            )
            if r.status_code != 200:
                return None

            data = r.json()
            upload_url = data["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset = data["value"]["asset"]

            with open(image_path, "rb") as f:
                r = await client.put(
                    upload_url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    content=f.read(),
                )
            if r.status_code in (200, 201):
                return asset
        return None

    async def post(self, text: str, image_path: str | None = None) -> dict:
        author = f"urn:li:organization:{self.org_id}"
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if image_path:
            asset = await self._upload_image(image_path)
            if asset:
                share = payload["specificContent"]["com.linkedin.ugc.ShareContent"]
                share["shareMediaCategory"] = "IMAGE"
                share["media"] = [
                    {
                        "status": "READY",
                        "media": asset,
                    }
                ]

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{API_BASE}/ugcPosts",
                headers=self._headers(),
                json=payload,
            )
            data = r.json()
            if r.status_code in (200, 201):
                return {"success": True, "post_id": data.get("id", ""), "error": ""}
            return {"success": False, "post_id": "", "error": str(data)}
