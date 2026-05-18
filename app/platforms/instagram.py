import asyncio
import logging
import httpx
from app.platforms.base import PlatformClient

GRAPH_API = "https://graph.facebook.com/v21.0"
log = logging.getLogger("socialautopost")


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

    async def _wait_for_container(self, client: httpx.AsyncClient, container_id: str, max_wait: int = 30) -> bool:
        """Poll until Instagram finishes processing the media container."""
        for attempt in range(max_wait // 3):
            r = await client.get(
                f"{GRAPH_API}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
            )
            data = r.json()
            status = data.get("status_code", "")
            log.info(f"Instagram container {container_id} status: {status}")
            if status == "FINISHED":
                return True
            if status == "ERROR":
                return False
            await asyncio.sleep(3)
        return False

    async def get_metrics(self, post_id: str) -> dict | None:
        """Fetch Instagram media insights: impressions, reach, likes, comments, saves."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get basic fields — these are reliable
                r = await client.get(
                    f"{GRAPH_API}/{post_id}",
                    params={
                        "fields": "like_count,comments_count",
                        "access_token": self.access_token,
                    },
                )
                data = r.json()
                likes = data.get("like_count", 0)
                comments = data.get("comments_count", 0)

                # Get insights — try IG media metrics
                impressions = 0
                reach = 0
                saves = 0
                shares = 0
                r2 = await client.get(
                    f"{GRAPH_API}/{post_id}/insights",
                    params={
                        "metric": "impressions,reach,saved,shares",
                        "access_token": self.access_token,
                    },
                )
                insights = r2.json()
                if "data" in insights:
                    for item in insights["data"]:
                        val = item.get("values", [{}])[0].get("value", 0)
                        if item["name"] == "impressions":
                            impressions = val
                        elif item["name"] == "reach":
                            reach = val
                        elif item["name"] == "saved":
                            saves = val
                        elif item["name"] == "shares":
                            shares = val
                else:
                    # Fallback: try total_interactions if specific metrics fail
                    log.debug(f"IG insights unavailable for {post_id}, using basic counts only")

                engagement = likes + comments + saves + shares
                return {
                    "impressions": impressions,
                    "reach": reach,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "saves": saves,
                    "clicks": 0,
                    "engagement": engagement,
                }
        except Exception as e:
            log.warning(f"Failed to fetch Instagram metrics for {post_id}: {e}")
            return None

    async def post(self, text: str, image_url: str | None = None) -> dict:
        if not image_url:
            return {"success": False, "post_id": "", "error": "Instagram requires an image URL"}

        async with httpx.AsyncClient(timeout=90) as client:
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

            # Step 2: Wait for container to finish processing
            ready = await self._wait_for_container(client, container_id)
            if not ready:
                return {"success": False, "post_id": "", "error": "Instagram media container never became ready"}

            # Step 3: Publish the container
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

    async def post_reel(self, text: str, video_url: str) -> dict:
        """Post a video as an Instagram Reel. Requires a public video URL."""
        if not video_url:
            return {"success": False, "post_id": "", "error": "Instagram Reels require a public video URL"}

        async with httpx.AsyncClient(timeout=120) as client:
            # Step 1: Create reel container
            r = await client.post(
                f"{GRAPH_API}/{self.ig_account_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": text,
                    "access_token": self.access_token,
                },
            )
            data = r.json()
            if "id" not in data:
                return {"success": False, "post_id": "", "error": data.get("error", {}).get("message", str(data))}

            container_id = data["id"]

            # Step 2: Wait for processing (videos take longer)
            ready = await self._wait_for_container(client, container_id, max_wait=120)
            if not ready:
                return {"success": False, "post_id": "", "error": "Instagram reel container never became ready"}

            # Step 3: Publish
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
