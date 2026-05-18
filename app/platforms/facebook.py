import asyncio
import logging
import httpx
from app.platforms.base import PlatformClient

GRAPH_API = "https://graph.facebook.com/v21.0"
log = logging.getLogger("socialautopost")


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
                result = {"success": True, "post_id": data["id"], "error": ""}
                # If we uploaded an image, fetch the public CDN URL
                # so Instagram (and others) can reuse it
                if image_path:
                    try:
                        photo_id = data["id"].split("_")[-1] if "_" in data["id"] else data["id"]
                        img_r = await client.get(
                            f"{GRAPH_API}/{photo_id}",
                            params={"fields": "images", "access_token": self.access_token},
                        )
                        img_data = img_r.json()
                        if "images" in img_data and img_data["images"]:
                            result["image_url"] = img_data["images"][0]["source"]
                    except Exception:
                        pass  # Non-fatal — Instagram just won't get the URL
                return result
            return {"success": False, "post_id": "", "error": data.get("error", {}).get("message", str(data))}

    async def get_metrics(self, post_id: str) -> dict | None:
        """Fetch Facebook post/photo/reel metrics."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                likes = 0
                comments = 0
                shares = 0

                # Try multiple field sets — different post types support different fields
                for fields in [
                    "reactions.summary(true),comments.summary(true),shares",
                    "likes.summary(true),comments.summary(true),shares",
                    "comments.summary(true),shares",
                ]:
                    r = await client.get(
                        f"{GRAPH_API}/{post_id}",
                        params={"fields": fields, "access_token": self.access_token},
                    )
                    if r.status_code == 200:
                        data = r.json()
                        likes = (
                            data.get("reactions", {}).get("summary", {}).get("total_count", 0)
                            or data.get("likes", {}).get("summary", {}).get("total_count", 0)
                        )
                        comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                        shares = data.get("shares", {}).get("count", 0)
                        break
                    else:
                        err = r.json().get("error", {}).get("message", r.text[:200])
                        log.debug(f"FB metrics fields '{fields}' failed for {post_id}: {err}")

                # Try insights — different metrics for posts vs reels vs photos
                impressions = 0
                reach = 0
                clicks = 0
                for metrics in [
                    "post_impressions,post_impressions_unique,post_clicks",
                    "post_impressions,post_impressions_unique",
                ]:
                    r2 = await client.get(
                        f"{GRAPH_API}/{post_id}/insights",
                        params={"metric": metrics, "access_token": self.access_token},
                    )
                    if r2.status_code != 200:
                        log.debug(f"FB insights '{metrics}' failed for {post_id}: {r2.status_code}")
                        continue
                    insights = r2.json()
                    if "data" in insights and insights["data"]:
                        for item in insights["data"]:
                            val = item.get("values", [{}])[0].get("value", 0)
                            if "unique" in item["name"]:
                                reach = val
                            elif "impressions" in item["name"]:
                                impressions = val
                            elif "clicks" in item["name"]:
                                clicks = val
                        break  # Got data, stop trying

                engagement = likes + comments + shares + clicks
                # Only return metrics if we got at least something
                if engagement == 0 and impressions == 0 and reach == 0:
                    log.info(f"FB metrics all zero for {post_id} — may lack pages_read_engagement permission")
                    return None

                return {
                    "impressions": impressions,
                    "reach": reach,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "saves": 0,
                    "clicks": clicks,
                    "engagement": engagement,
                }
        except Exception as e:
            log.warning(f"Failed to fetch Facebook metrics for {post_id}: {e}")
            return None

    async def post_reel(self, text: str, video_path: str) -> dict:
        """Upload a video as a Facebook Reel via resumable upload."""
        async with httpx.AsyncClient(timeout=300) as client:
            file_size = __import__("os").path.getsize(video_path)

            # Step 1: Initialize upload session
            r = await client.post(
                f"{GRAPH_API}/{self.page_id}/video_reels",
                data={
                    "upload_phase": "start",
                    "access_token": self.access_token,
                },
            )
            data = r.json()
            if "video_id" not in data:
                return {"success": False, "post_id": "", "error": f"Reel init failed: {data.get('error', {}).get('message', str(data))}"}

            video_id = data["video_id"]

            # Step 2: Upload the video binary
            with open(video_path, "rb") as f:
                r = await client.post(
                    f"https://rupload.facebook.com/video-upload/v21.0/{video_id}",
                    headers={
                        "Authorization": f"OAuth {self.access_token}",
                        "offset": "0",
                        "file_size": str(file_size),
                        "Content-Type": "application/octet-stream",
                    },
                    content=f.read(),
                )
            upload_data = r.json()
            if not upload_data.get("success"):
                return {"success": False, "post_id": "", "error": f"Reel upload failed: {upload_data}"}

            # Step 3: Publish the reel
            r = await client.post(
                f"{GRAPH_API}/{self.page_id}/video_reels",
                data={
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "title": text[:100],
                    "description": text,
                    "access_token": self.access_token,
                },
            )
            pub_data = r.json()
            if pub_data.get("success") or "video_id" in pub_data:
                reel_id = pub_data.get("video_id", video_id)
                result = {"success": True, "post_id": str(reel_id), "error": ""}

                # Try to get the direct video source URL for Instagram reuse
                try:
                    vid_r = await client.get(
                        f"{GRAPH_API}/{reel_id}",
                        params={"fields": "source", "access_token": self.access_token},
                    )
                    vid_data = vid_r.json()
                    if "source" in vid_data:
                        result["video_url"] = vid_data["source"]
                        log.info(f"Got FB video source URL for Instagram reuse")
                except Exception:
                    pass
                return result
            return {"success": False, "post_id": "", "error": f"Reel publish failed: {pub_data.get('error', {}).get('message', str(pub_data))}"}
