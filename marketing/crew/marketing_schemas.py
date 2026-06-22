from pydantic import BaseModel, Field
from typing import List


class MarketingContentSchema(BaseModel):
    """Structured, channel-ready marketing draft for a single Mequedo source.

    Used as ``output_json`` on the final QA task (mirrors ``IntentSchema``'s role
    in the chatbot crew). Every field must be grounded in the MarketingSourceTool
    output — no invented prices, dates, amenities, or inclusions.
    """
    instagram_caption: str = Field(
        ..., description="AIDA Instagram caption in Venezuelan Spanish, <= 2200 chars.")
    hashtags: List[str] = Field(
        default_factory=list, description="Relevant hashtags, <= 30 items, each starting with '#'.")
    youtube_title: str = Field(
        ..., description="Catchy YouTube title in Spanish (<= 100 chars).")
    youtube_description: str = Field(
        ..., description="YouTube description in Spanish with factual package details.")
    announcement_html: str = Field(
        ..., description="Short in-app announcement as PLAIN TEXT in Spanish (no HTML tags; the frontend wraps it).")
    image_overlay_text: str = Field(
        ..., description="Short text to burn into the composed image (real price/destination).")
    chosen_image_url: str = Field(
        ..., description="The single best source image URL picked from the package photos.")
