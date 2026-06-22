import os
import logging
import urllib.parse
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class CloudinaryImageComposer:
    """Builds branded Cloudinary delivery URLs from existing property photos.

    Pure string building over Cloudinary's URL-based transformation API:
    a text overlay (price/destination) plus an optional brand-logo overlay are
    layered on top of a source image already hosted on Cloudinary. No upload,
    no AI image generation, no network call — just a transformed delivery URL.
    """

    def __init__(self) -> None:
        self.cloud_name: Optional[str] = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.logo_public_id: Optional[str] = os.getenv(
            "CLOUDINARY_LOGO_PUBLIC_ID")
        if not self.cloud_name:
            logger.warning(
                "CLOUDINARY_CLOUD_NAME not configured; image composition disabled.")

    @staticmethod
    def _extract_public_id(source_url: str) -> Optional[str]:
        """Recover the Cloudinary ``public_id`` (incl. version) from a delivery URL.

        Returns ``None`` when the URL is not a Cloudinary ``/upload/`` URL, so the
        caller can gracefully skip composition for foreign image hosts.
        """
        if not source_url or "/upload/" not in source_url:
            return None
        tail = source_url.split("/upload/", 1)[1]
        # Drop the file extension; keep the version prefix (vNNN) if present.
        if "." in tail.rsplit("/", 1)[-1]:
            tail = tail.rsplit(".", 1)[0]
        return tail

    @staticmethod
    def _encode_overlay_text(text: str) -> str:
        """Cloudinary text overlays need commas/slashes URL-escaped twice."""
        cleaned = text.replace(",", " ").replace("/", " ").strip()
        return urllib.parse.quote(cleaned, safe="")

    def compose(
        self,
        source_url: str,
        overlay_text: str,
        font: str = "Arial",
        font_size: int = 60,
    ) -> Optional[str]:
        """Return a transformed Cloudinary URL, or ``None`` if composition is unavailable.

        Args:
            source_url: A Cloudinary-hosted source photo URL from the listing.
            overlay_text: Short factual text to burn in (e.g. ``"Mérida $45/persona"``).
            font: Cloudinary-supported font family for the text overlay.
            font_size: Pixel size of the overlay text.
        """
        if not self.cloud_name:
            return None

        public_id = self._extract_public_id(source_url)
        if not public_id:
            logger.warning(
                "Source URL is not a Cloudinary upload URL; skipping composition.")
            return None

        transformations: List[str] = ["c_fill,w_1080,h_1080"]

        encoded_text = self._encode_overlay_text(overlay_text)
        transformations.append(
            f"l_text:{font}_{font_size}_bold:{encoded_text},co_white,g_south,y_80"
        )

        if self.logo_public_id:
            # Cloudinary requires ':' in a public_id to be written as '/' inside l_.
            logo_ref = self.logo_public_id.replace("/", ":")
            transformations.append(
                f"l_{logo_ref},w_180,g_north_east,x_40,y_40,o_85")

        transformation_str = "/".join(transformations)
        return (
            f"https://res.cloudinary.com/{self.cloud_name}/image/upload/"
            f"{transformation_str}/{public_id}.jpg"
        )


class InstagramService:
    """Instagram Graph API client (Phase 2-ready; NOT called in Phase 1).

    Mirrors ``WhatsAppService``: same base/version, Bearer auth, and
    try/except/logging shape. Publishing is gated behind Meta App Review, so
    these methods are built now but only wired into the scheduler in Phase 2.
    """

    def __init__(self) -> None:
        self.ig_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        # Reuse the WhatsApp/Meta app token unless a dedicated Graph token is set.
        self.access_token = os.getenv("META_GRAPH_ACCESS_TOKEN") or os.getenv(
            "WHATSAPP_ACCESS_TOKEN")
        self.api_version = "v24.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.ig_account_id}"

        if not self.ig_account_id or not self.access_token:
            logger.error("❌ Instagram credentials not configured")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def create_media_container(self, image_url: str, caption: str) -> Optional[str]:
        """POST /media — upload an image + caption, returning a ``creation_id``."""
        if not self.ig_account_id or not self.access_token:
            logger.error("❌ Instagram not configured")
            return None

        url = f"{self.base_url}/media"
        payload = {"image_url": image_url, "caption": caption}

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=15)
            response.raise_for_status()
            creation_id = response.json().get("id")
            logger.info(f"✅ IG media container created: {creation_id}")
            return creation_id
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error creating IG media container: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def publish_media(self, creation_id: str) -> bool:
        """POST /media_publish — publish a previously created media container."""
        if not self.ig_account_id or not self.access_token:
            logger.error("❌ Instagram not configured")
            return False

        url = f"{self.base_url}/media_publish"
        payload = {"creation_id": creation_id}

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=15)
            response.raise_for_status()
            logger.info(f"✅ IG media published from container {creation_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error publishing IG media: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False
