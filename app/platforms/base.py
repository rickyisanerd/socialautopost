from abc import ABC, abstractmethod


class PlatformClient(ABC):
    platform_name: str = ""

    @abstractmethod
    async def post(self, text: str, image_path: str | None = None) -> dict:
        """Post content. Returns {"success": bool, "post_id": str, "error": str}."""
        pass

    @abstractmethod
    async def verify_credentials(self) -> bool:
        pass

    async def get_metrics(self, post_id: str) -> dict | None:
        """Fetch engagement metrics for a post. Returns dict of metric values or None on failure.

        Expected keys: impressions, reach, likes, comments, shares, saves, clicks, engagement
        """
        return None
