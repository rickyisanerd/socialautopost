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
