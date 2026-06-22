import os
from unittest.mock import patch

from django.test import TestCase

from marketing.services import CloudinaryImageComposer
from marketing.crew.marketing_schemas import MarketingContentSchema


class CloudinaryImageComposerTests(TestCase):
    @patch.dict(os.environ, {"CLOUDINARY_CLOUD_NAME": "mequedo", "CLOUDINARY_LOGO_PUBLIC_ID": "mequedo_logo"})
    def test_compose_builds_transformation_url(self):
        composer = CloudinaryImageComposer()
        source = "https://res.cloudinary.com/mequedo/image/upload/v1700000000/listings/casa.jpg"
        url = composer.compose(source, "Mérida $45 por persona")

        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("https://res.cloudinary.com/mequedo/image/upload/"))
        self.assertIn("l_text:", url)
        self.assertIn("l_mequedo_logo", url)
        # Source public_id (with version) preserved, no double extension.
        self.assertIn("v1700000000/listings/casa.jpg", url)
        # Commas in overlay text must be stripped/encoded, never raw.
        self.assertNotIn("$45,", url)

    @patch.dict(os.environ, {"CLOUDINARY_CLOUD_NAME": ""}, clear=False)
    def test_compose_disabled_without_cloud_name(self):
        with patch.object(CloudinaryImageComposer, "__init__", lambda s: None):
            composer = CloudinaryImageComposer()
            composer.cloud_name = None
            composer.logo_public_id = None
            self.assertIsNone(composer.compose("https://x/y/upload/a.jpg", "txt"))

    @patch.dict(os.environ, {"CLOUDINARY_CLOUD_NAME": "mequedo"})
    def test_compose_skips_non_cloudinary_url(self):
        composer = CloudinaryImageComposer()
        self.assertIsNone(composer.compose("https://example.com/photo.jpg", "txt"))


class MarketingContentSchemaTests(TestCase):
    def test_schema_validates_and_enforces_types(self):
        content = MarketingContentSchema(
            instagram_caption="¡Vive Mérida! " + "a" * 100,
            hashtags=["#Merida", "#Venezuela"],
            youtube_title="Aventura en Mérida",
            youtube_description="Tour de 3 días.",
            announcement_html="<p>Nuevo paquete</p>",
            image_overlay_text="Mérida $45",
            chosen_image_url="https://res.cloudinary.com/demo/image/upload/v1/x.jpg",
        )
        self.assertLessEqual(len(content.instagram_caption), 2200)
        self.assertLessEqual(len(content.hashtags), 30)
        self.assertEqual(content.hashtags[0], "#Merida")
