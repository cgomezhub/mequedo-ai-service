from django.test import TestCase
from unittest.mock import patch, MagicMock

from pydantic import ValidationError
from bson.objectid import ObjectId

from marketing.crew.tools.marketing_source_tool import (
    MarketingSourceTool,
    MarketingSourceArgs,
)


class MarketingSourceToolTests(TestCase):
    def test_tool_initialization(self):
        tool = MarketingSourceTool()
        self.assertIn("Marketing Source", tool.name)
        self.assertEqual(tool.args_schema, MarketingSourceArgs)

    def test_args_validation(self):
        args = MarketingSourceArgs(source_type="package", source_id="507f1f77bcf86cd799439011")
        self.assertEqual(args.source_type, "package")
        with self.assertRaises(ValidationError):
            MarketingSourceArgs(source_type="package")  # missing source_id

    def test_invalid_source_type(self):
        tool = MarketingSourceTool()
        out = tool._run(source_type="banner", source_id="507f1f77bcf86cd799439011")
        self.assertIn("Error", out)

    def test_invalid_objectid(self):
        tool = MarketingSourceTool()
        out = tool._run(source_type="package", source_id="not-an-id")
        self.assertIn("Error", out)

    @patch("marketing.crew.tools.marketing_source_tool.get_db")
    def test_package_fetch_returns_factual_dict(self, mock_get_db):
        oid = ObjectId()
        package_doc = {
            "_id": oid,
            "title": "Aventura en Mérida",
            "description": "Tour de montaña inolvidable.",
            "destination": "Mérida",
            "pricePerPerson": 45,
            "durationDays": 3,
            "inclusions": ["Transporte", "Desayuno"],
            "exclusions": ["Almuerzo"],
            "imageSrc": ["https://res.cloudinary.com/demo/image/upload/v1/merida.jpg"],
            "operatorId": ObjectId(),
        }

        packages_col = MagicMock()
        packages_col.find_one.return_value = package_doc
        operators_col = MagicMock()
        operators_col.find_one.return_value = {"businessName": "Andes Tours", "phoneNumber": "+58000"}

        mock_db = MagicMock()
        mock_db.get_collection.side_effect = lambda name: {
            "TourismPackage": packages_col,
            "TourismOperatorProfile": operators_col,
        }[name]
        mock_get_db.return_value = mock_db

        out = MarketingSourceTool()._run(source_type="package", source_id=str(oid))

        self.assertIn("Aventura en Mérida", out)
        self.assertIn("Mérida", out)
        self.assertIn("45", out)
        self.assertIn("Andes Tours", out)
        self.assertIn("merida.jpg", out)

    @patch("marketing.crew.tools.marketing_source_tool.get_db")
    def test_missing_source_returns_sentinel(self, mock_get_db):
        col = MagicMock()
        col.find_one.return_value = None
        mock_db = MagicMock()
        mock_db.get_collection.return_value = col
        mock_get_db.return_value = mock_db

        out = MarketingSourceTool()._run(source_type="package", source_id=str(ObjectId()))
        self.assertEqual(out, "NO_SOURCE_FOUND")
