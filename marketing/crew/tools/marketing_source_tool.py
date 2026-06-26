import logging
from typing import Type, Optional, List

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from bson.objectid import ObjectId

from chatbot.crew.tools.search_accommodation import get_db

logger = logging.getLogger(__name__)


def _is_valid_objectid(oid: str) -> bool:
    try:
        ObjectId(oid)
        return True
    except Exception:
        return False


class MarketingSourceArgs(BaseModel):
    source_type: str = Field(
        ..., description="Either 'package' (TourismPackage) or 'listing' (Listing).")
    source_id: str = Field(
        ..., description="The MongoDB ObjectId of the source document, as a string.")


class MarketingSourceTool(BaseTool):
    name: str = "Mequedo Marketing Source Fetcher"
    description: str = (
        "Fetch the factual, structured record for a single Mequedo TourismPackage or "
        "Listing from MongoDB. This is the crew's ONLY source of truth: every price, "
        "date, inclusion, and amenity in the marketing copy MUST come from this output. "
        "Pass flat primitive values, e.g. {\"source_type\": \"package\", \"source_id\": \"...\"}."
    )
    args_schema: Type[BaseModel] = MarketingSourceArgs

    def fetch_facts(self, source_type: str, source_id: str) -> Optional[dict]:
        """Return the raw factual dict for a source, or ``None`` if unavailable.

        Public so the background worker can read authoritative values (price,
        destination) directly instead of trusting the LLM for the image overlay.
        """
        source_type = (source_type or "").strip().lower()
        if source_type not in ("package", "listing"):
            return None
        if not _is_valid_objectid(source_id):
            return None

        db = get_db()
        if db is None:
            return None

        try:
            if source_type == "package":
                return self._fetch_package(db, source_id)
            return self._fetch_listing(db, source_id)
        except Exception as e:
            logger.error(f"MarketingSourceTool DB failure: {e}")
            return None

    def _run(self, source_type: str, source_id: str) -> str:
        source_type = (source_type or "").strip().lower()
        if source_type not in ("package", "listing"):
            return "Error: source_type must be 'package' or 'listing'."
        if not _is_valid_objectid(source_id):
            return "Error: source_id is not a valid ObjectId."

        db = get_db()
        if db is None:
            return "Error: Database connection unavailable."

        try:
            if source_type == "package":
                facts = self._fetch_package(db, source_id)
            else:
                facts = self._fetch_listing(db, source_id)
        except Exception as e:
            logger.error(f"MarketingSourceTool DB failure: {e}")
            return "Error: A database execution failure interrupted the source fetch."

        if facts is None:
            return "NO_SOURCE_FOUND"

        return self._format_facts(facts)

    def _fetch_package(self, db, source_id: str) -> Optional[dict]:
        package = db.get_collection("TourismPackage").find_one(
            {"_id": ObjectId(source_id)},
            {
                "title": 1, "description": 1, "destination": 1,
                "pricePerPerson": 1, "durationDays": 1, "inclusions": 1,
                "exclusions": 1, "imageSrc": 1, "operatorId": 1,
            },
        )
        if not package:
            return None

        operator_name = None
        operator_phone = None
        operator_id = package.get("operatorId")
        if operator_id is not None:
            operator = db.get_collection("TourismOperatorProfile").find_one(
                {"_id": operator_id if isinstance(operator_id, ObjectId) else ObjectId(str(operator_id))},
                {"businessName": 1, "phoneNumber": 1},
            )
            if operator:
                operator_name = operator.get("businessName")
                operator_phone = operator.get("phoneNumber")

        return {
            "source_type": "package",
            "title": package.get("title"),
            "description": package.get("description"),
            "destination": package.get("destination"),
            "price_per_person": package.get("pricePerPerson"),
            "duration_days": package.get("durationDays"),
            "inclusions": package.get("inclusions") or [],
            "exclusions": package.get("exclusions") or [],
            "images": package.get("imageSrc") or [],
            "operator_name": operator_name,
            "operator_phone": operator_phone,
        }

    def _fetch_listing(self, db, source_id: str) -> Optional[dict]:
        listing = db.get_collection("Listing").find_one(
            {"_id": ObjectId(source_id)},
            {
                "title": 1, "description": 1, "price": 1, "category": 1,
                "guests": 1, "bedrooms": 1, "bathrooms": 1,
                "imageSrc": 1, "locationId": 1,
            },
        )
        if not listing:
            return None

        destination = None
        location_id = listing.get("locationId")
        if location_id is not None:
            # ``locationId`` may be stored as a string while ``Location._id`` is an
            # ObjectId; query with the raw value coerced, mirroring the operator
            # lookup. A malformed id yields no destination rather than aborting the
            # whole fetch (and losing every other fact).
            try:
                loc_oid = (location_id if isinstance(location_id, ObjectId)
                           else ObjectId(str(location_id)))
            except Exception:
                loc_oid = None
            if loc_oid is not None:
                location = db.get_collection("Location").find_one(
                    {"_id": loc_oid}, {"city": 1})
                if location:
                    destination = location.get("city")

        return {
            "source_type": "listing",
            "title": listing.get("title"),
            "description": listing.get("description"),
            "destination": destination,
            "price_per_person": listing.get("price"),
            "category": listing.get("category"),
            "guests": listing.get("guests"),
            "bedrooms": listing.get("bedrooms"),
            "bathrooms": listing.get("bathrooms"),
            "images": listing.get("imageSrc") or [],
            "operator_name": None,
            "operator_phone": None,
        }

    def _format_facts(self, facts: dict) -> str:
        """Render the dict as a compact, unambiguous fact sheet for the LLM.

        Missing fields are omitted rather than emitted as empty — the copywriter
        is instructed to never fabricate anything absent here.
        """
        lines: List[str] = ["FACTUAL SOURCE RECORD (use ONLY these facts):"]

        def add(label: str, value) -> None:
            if value is None or value == "" or value == []:
                return
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            lines.append(f"- {label}: {value}")

        price = facts.get("price_per_person")
        if price is not None:
            try:
                # Render 40.0 as "40" so the copy reads "$40", not "$40.0".
                price = int(price) if float(price) == int(price) else price
            except (TypeError, ValueError):
                pass

        add("Tipo", facts.get("source_type"))
        add("Título", facts.get("title"))
        add("Destino", facts.get("destination"))
        add("Precio por persona (USD)", price)
        add("Duración (días)", facts.get("duration_days"))
        add("Categoría", facts.get("category"))
        add("Capacidad (huéspedes)", facts.get("guests"))
        add("Habitaciones", facts.get("bedrooms"))
        add("Baños", facts.get("bathrooms"))
        add("Incluye", facts.get("inclusions"))
        add("No incluye", facts.get("exclusions"))
        add("Descripción", facts.get("description"))
        add("Operador", facts.get("operator_name"))

        images = facts.get("images") or []
        if images:
            lines.append("- Imágenes disponibles (elige UNA como chosen_image_url):")
            for url in images:
                lines.append(f"    {url}")
        else:
            lines.append("- Imágenes disponibles: NINGUNA (omite la composición de imagen).")

        return "\n".join(lines)
