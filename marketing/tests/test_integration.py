import os
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient
from bson.objectid import ObjectId


SECRET = "test-secret"


@patch.dict(os.environ, {"DJANGO_SERVICE_SECRET": SECRET})
class GenerateContentAsyncViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/marketing/generate/async/"

    @patch("marketing.views.threading.Thread")
    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_returns_202_and_content_id(self, mock_get_db, mock_thread):
        inserted_id = ObjectId()
        col = MagicMock()
        col.insert_one.return_value = MagicMock(inserted_id=inserted_id)
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db

        resp = self.client.post(
            self.url,
            {"sourceType": "package", "sourceId": str(ObjectId())},
            format="json",
            HTTP_X_INTERNAL_SECRET=SECRET,
        )

        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["contentId"], str(inserted_id))
        self.assertEqual(resp.json()["status"], "processing")
        # The processing doc must be written before the thread is dispatched.
        col.insert_one.assert_called_once()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_rejects_without_internal_secret(self):
        resp = self.client.post(
            self.url,
            {"sourceType": "package", "sourceId": str(ObjectId())},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_rejects_missing_source_id(self, mock_get_db):
        resp = self.client.post(
            self.url,
            {"sourceType": "package"},
            format="json",
            HTTP_X_INTERNAL_SECRET=SECRET,
        )
        self.assertEqual(resp.status_code, 400)

    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_rejects_bad_source_type(self, mock_get_db):
        resp = self.client.post(
            self.url,
            {"sourceType": "banner", "sourceId": str(ObjectId())},
            format="json",
            HTTP_X_INTERNAL_SECRET=SECRET,
        )
        self.assertEqual(resp.status_code, 400)


class OverlayTextTests(TestCase):
    @patch("marketing.crew.tools.marketing_source_tool.MarketingSourceTool.fetch_facts")
    def test_overlay_built_from_facts_not_llm(self, mock_fetch):
        from marketing.views import _build_overlay_text
        mock_fetch.return_value = {
            "destination": "Barbacoas", "duration_days": 2, "price_per_person": 40.0,
        }
        # Price must render as $40 (no ".0"), with the real destination.
        self.assertEqual(
            _build_overlay_text("package", "507f1f77bcf86cd799439011"),
            "Barbacoas · 2 días · $40/persona",
        )

    @patch("marketing.crew.tools.marketing_source_tool.MarketingSourceTool.fetch_facts")
    def test_overlay_empty_when_facts_unavailable(self, mock_fetch):
        from marketing.views import _build_overlay_text
        mock_fetch.return_value = None
        self.assertEqual(_build_overlay_text("package", "507f1f77bcf86cd799439011"), "")


class JunkDescriptionGuardTests(TestCase):
    def test_detects_junk_and_empty_descriptions(self):
        from marketing.views import _looks_like_junk_description
        junk = [
            "",
            None,
            "   ",
            "short",
            "wjdjwjdj dwqd 9 wd 0 uwq d. dwu.  d q dwqdw8",  # the real Barbacoas junk
            "xkcd zxcv bcdfg hjklm",  # vowel-less soup
        ]
        for d in junk:
            self.assertTrue(_looks_like_junk_description(d), f"should be junk: {d!r}")

    def test_accepts_real_descriptions(self):
        from marketing.views import _looks_like_junk_description
        good = [
            "Disfruta de dos días inolvidables en Barbacoas con desayuno y alojamiento incluidos.",
            "Un acogedor apartamento en el centro de la ciudad, ideal para parejas.",
        ]
        for d in good:
            self.assertFalse(_looks_like_junk_description(d), f"should be valid: {d!r}")

    def test_assess_quality_flags_junk_description_and_missing_fields(self):
        from marketing.views import _assess_source_quality
        warnings = _assess_source_quality({
            "description": "wjdjwjdj dwqd 9 wd",
            "price_per_person": None,
            "destination": "",
        })
        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("descripción" in w.lower() for w in warnings))

    def test_assess_quality_clean_source_has_no_warnings(self):
        from marketing.views import _assess_source_quality
        warnings = _assess_source_quality({
            "description": "Dos días maravillosos en Barbacoas con todo incluido y guía local.",
            "price_per_person": 40.0,
            "destination": "Barbacoas",
        })
        self.assertEqual(warnings, [])


class BackgroundWorkerTests(TestCase):
    @patch("marketing.crew.tools.marketing_source_tool.MarketingSourceTool.fetch_facts")
    @patch("marketing.views.CloudinaryImageComposer")
    @patch("marketing.views._kickoff_marketing_with_retry")
    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_background_writes_draft_doc(self, mock_get_db, mock_kickoff, mock_composer, mock_facts):
        import json
        from marketing.views import _run_marketing_in_background

        col = MagicMock()
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db

        real_image = "https://res.cloudinary.com/demo/image/upload/v1/x.jpg"
        # Clean source facts: deterministic overlay + no data-quality warnings.
        mock_facts.return_value = {
            "destination": "Mérida", "duration_days": 3, "price_per_person": 45.0,
            "description": "Tres días maravillosos en Mérida con todo incluido y guía.",
            "images": [real_image],
        }
        mock_kickoff.return_value = json.dumps({
            "instagram_caption": "¡Vive Mérida!",
            "hashtags": ["#Merida"],
            "youtube_title": "Aventura",
            "youtube_description": "Tour",
            "announcement_html": "<p>Nuevo</p>",
            "image_overlay_text": "Mérida $45",
            "chosen_image_url": real_image,
        })
        mock_composer.return_value.compose.return_value = "https://composed.url/x.jpg"

        content_id = ObjectId()
        _run_marketing_in_background(content_id, "package", str(ObjectId()))

        col.update_one.assert_called_once()
        _filter, update = col.update_one.call_args[0]
        set_fields = update["$set"]
        self.assertEqual(set_fields["status"], "draft")
        self.assertEqual(set_fields["instagramCaption"], "¡Vive Mérida!")
        # announcementHtml is stored as plain text (frontend manages the tags).
        self.assertEqual(set_fields["announcementHtml"], "Nuevo")
        self.assertEqual(set_fields["composedImageUrl"], "https://composed.url/x.jpg")
        # Composition runs over the DB image, never the raw LLM string.
        self.assertEqual(
            mock_composer.return_value.compose.call_args[0][0], real_image)
        # Overlay is built from facts (no ".0"), not from the LLM's "Mérida $45".
        self.assertEqual(set_fields["imageOverlayText"], "Mérida · 3 días · $45/persona")
        self.assertEqual(set_fields["dataQualityWarnings"], [])

    @patch("marketing.crew.tools.marketing_source_tool.MarketingSourceTool.fetch_facts")
    @patch("marketing.views.CloudinaryImageComposer")
    @patch("marketing.views._kickoff_marketing_with_retry")
    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_hallucinated_image_url_falls_back_to_db_image(
            self, mock_get_db, mock_kickoff, mock_composer, mock_facts):
        import json
        from marketing.views import _run_marketing_in_background

        col = MagicMock()
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db

        real_image = "https://res.cloudinary.com/carlosgomez/image/upload/v1773242952/jm9zmpz79bcf9sj5gqb9.png"
        mock_facts.return_value = {
            "destination": "Barbacoas", "duration_days": 2, "price_per_person": 10,
            "description": "Dos días en Barbacoas con todo incluido y transporte.",
            "images": [real_image],
        }
        mock_kickoff.return_value = json.dumps({
            "instagram_caption": "¡Vive Barbacoas!",
            "hashtags": ["#Barbacoas"],
            "youtube_title": "Aventura",
            "youtube_description": "Tour",
            "announcement_html": "Nuevo",
            "image_overlay_text": "Barbacoas $10",
            # LLM hallucinated a non-existent public_id (the real bug observed).
            "chosen_image_url": "https://res.cloudinary.com/carlosgomez/image/upload/v1781037712/is6bg9aynt0kz5asxbtb.jpg",
        })
        mock_composer.return_value.compose.return_value = "https://composed.url/real.jpg"

        _run_marketing_in_background(ObjectId(), "package", str(ObjectId()))

        # The hallucinated URL is discarded; composition runs over the DB image.
        self.assertEqual(
            mock_composer.return_value.compose.call_args[0][0], real_image)
        set_fields = col.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_fields["composedImageUrl"], "https://composed.url/real.jpg")

    @patch("marketing.views._kickoff_marketing_with_retry")
    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_background_writes_error_on_failure(self, mock_get_db, mock_kickoff):
        from marketing.views import _run_marketing_in_background

        col = MagicMock()
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db
        mock_kickoff.side_effect = RuntimeError("crew exploded")

        _run_marketing_in_background(ObjectId(), "package", str(ObjectId()))

        col.update_one.assert_called_once()
        _filter, update = col.update_one.call_args[0]
        self.assertEqual(update["$set"]["status"], "error")


@patch.dict(os.environ, {"DJANGO_SERVICE_SECRET": SECRET})
class GenerateContentStatusViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/marketing/generate/status/"

    @patch("chatbot.crew.tools.search_accommodation.get_db")
    def test_returns_draft_fields(self, mock_get_db):
        col = MagicMock()
        col.find_one.return_value = {
            "status": "draft",
            "instagramCaption": "¡Hola!",
            "hashtags": ["#Merida"],
            "composedImageUrl": "https://composed.url/x.jpg",
        }
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db

        resp = self.client.get(self.url, {"contentId": str(ObjectId())})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "draft")
        self.assertEqual(resp.json()["instagramCaption"], "¡Hola!")

    def test_missing_content_id_returns_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    def test_invalid_content_id_returns_400(self):
        resp = self.client.get(self.url, {"contentId": "not-an-id"})
        self.assertEqual(resp.status_code, 400)
