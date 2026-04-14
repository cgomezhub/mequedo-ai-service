import os
import re
import logging
from pydantic import BaseModel, Field
from typing import Type, Optional
from crewai.tools import BaseTool

from pymongo import MongoClient
import certifi

logger = logging.getLogger(__name__)

# Global MongoClient to maintain the connection pool and avoid instantiating on every tool run
_mongo_client = None


def get_db():
    global _mongo_client
    try:
        if _mongo_client is None:
            _mongo_client = MongoClient(
                os.getenv("DATABASE_URL"),
                tlsCAFile=certifi.where(),
                # 2 seconds timeout to prevent hanging threads if DB is unreachable
                serverSelectionTimeoutMS=2000
            )
        return _mongo_client.get_database(os.getenv("MONGODB_DB_NAME", "test"))
    except Exception as e:
        logger.error(
            f"Failed to connect to MongoDB in SearchAccommodationTool: {e}")
        return None


class SearchAccommodationArgs(BaseModel):
    city: str = Field(..., description="The city name to search accommodations in, e.g. 'Valencia', 'Margarita'")
    max_price: Optional[int] = Field(
        None, description="The strictly maximum price the user is willing to pay.")
    guests: Optional[int] = Field(
        None, description="Number of guests requested.")
    bedrooms: Optional[int] = Field(
        None, description="Minimum number of bedrooms required.")
    bathrooms: Optional[int] = Field(
        None, description="Minimum number of bathrooms required.")


class SearchAccommodationTool(BaseTool):
    name: str = "Search Accommodation Database"
    description: str = (
        "Search the exact Mequedo MongoDB database for accommodations based on city, "
        "maximum price, and guest capacity. ALWAYS use this tool to verify options before suggesting them.\n"
        "CRITICAL INVOCATION RULE: Pass exactly flat primitive values in JSON like {\"city\": \"Barquisimeto\"}. "
        "DO NOT use JSON Schema objects or nested dictionaries."
    )
    args_schema: Type[BaseModel] = SearchAccommodationArgs

    def _run(self, city: str, max_price: Optional[int] = None, guests: Optional[int] = None, bedrooms: Optional[int] = None, bathrooms: Optional[int] = None) -> str:
        db = get_db()
        if db is None:
            return "Error: Database connection unavailable."

        locations_col = db.get_collection("Location")
        listings_col = db.get_collection("Listing")

        # Sanitize city input to natively prevent ReDoS (Regular Expression Denial of Service) risks
        sanitized_city = re.escape(city.strip())

        try:
            # Relaxed regex to allow partial matches (e.g. 'Margarita' matches 'Isla Margarita')
            regex_query = {"$regex": sanitized_city, "$options": "i"}
            matching_locations = list(locations_col.find(
                {"city": regex_query}, {"_id": 1}))

            # Since loc["_id"] is already returned as a native ObjectId, we cleanly assemble our array
            matching_loc_ids = [loc["_id"] for loc in matching_locations]

            if not matching_loc_ids:
                return f"No locations found matching the city '{city}'."

            # Formulate the highly optimized direct query
            filters = {"isApproved": True,
                       "locationId": {"$in": matching_loc_ids}}
            if max_price:
                filters["price"] = {"$lte": max_price}
            if guests:
                filters["guests"] = {"$gte": guests}
            if bedrooms:
                filters["bedrooms"] = {"$gte": bedrooms}
            if bathrooms:
                filters["bathrooms"] = {"$gte": bathrooms}

            # Fetch enriched data including slug, guests, bedrooms, bathrooms and description
            listings = list(listings_col.find(
                filters, 
                {
                    "title": 1, 
                    "price": 1, 
                    "category": 1, 
                    "slug": 1, 
                    "guests": 1, 
                    "bedrooms": 1, 
                    "bathrooms": 1, 
                    "description": 1
                }
            ).limit(6))

            if not listings:
                return f"No accommodations found in '{city}' matching criteria: max_price={max_price}."

            result = f"Found {len(listings)} options in {city}. CRITICAL: Use these exact details only:\n"
            for l in listings:
                l_city = city.capitalize()
                l_title = l.get('title', 'Unknown')
                l_price = l.get('price', 0)
                l_category = l.get('category', 'N/A')
                l_slug = l.get('slug', 'n-a')
                l_guests = l.get('guests', 1)
                l_beds = l.get('bedrooms', 1)
                l_baths = l.get('bathrooms', 1)
                l_desc = l.get('description', '')[:100] # Short excerpt
                
                result += (
                    f"- {l_title} | Price: ${l_price} | Category: {l_category} | "
                    f"City: {l_city} | Slug: {l_slug} | Max Guests: {l_guests} | "
                    f"Beds: {l_beds} | Baths: {l_baths} | Desc: {l_desc}...\n"
                )
            return result
        except Exception as e:
            logger.error(
                f"Database operation failed in SearchAccommodationTool: {e}")
            return "Error: A database execution failure interrupted the search."
