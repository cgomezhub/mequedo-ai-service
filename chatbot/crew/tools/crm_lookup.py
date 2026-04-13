import logging
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)


class UserContextArgs(BaseModel):
    user_id: str = Field(..., description="The user's unique ID from the Mequedo platform to look up their profile and reservations.")


class UserContextTool(BaseTool):
    """
    CRM Lookup Tool for Laura.
    Fetches the authenticated user's profile and active reservations from MongoDB
    so Laura can personalize her responses naturally.
    """
    name: str = "User Context Lookup"
    description: str = (
        "Look up a logged-in Mequedo user's profile and active reservations by their userId. "
        "Use this tool when the user seems to be asking about their bookings, trips, payments, or account. "
        "Do NOT use this tool if the userId is 'WEB_ANONYMOUS' or 'WEB_FRONTEND'."
    )
    args_schema: Type[BaseModel] = UserContextArgs

    def _run(self, user_id: str) -> str:
        # Reject anonymous / placeholder user IDs to avoid wasted DB calls
        if not user_id or user_id in ("WEB_ANONYMOUS", "WEB_FRONTEND", ""):
            return "No authenticated user context available. The user is browsing anonymously."

        try:
            from chatbot.crew.tools.search_accommodation import get_db
            db = get_db()
            if db is None:
                return "Error: Database connection unavailable."

            users_col = db.get_collection("User")
            reservations_col = db.get_collection("Reservation")
            listings_col = db.get_collection("Listing")

            # Safely prepare the ID query array to support both Native ObjectId and String ID storage
            query_ids = [user_id]
            if len(user_id) == 24:
                try:
                    query_ids.append(ObjectId(user_id))
                except Exception:
                    pass

            # Fetch user profile using both formats
            user = users_col.find_one(
                {"_id": {"$in": query_ids}},
                {"name": 1, "email": 1, "image": 1, "cardIdVerified": 1}
            )

            if not user:
                # Fallback to string "id" field in case DB differs
                user = users_col.find_one(
                    {"id": {"$in": query_ids}},
                    {"name": 1, "email": 1, "cardIdVerified": 1}
                )

            user_name = user.get("name", "Usuario") if user else "Usuario"
            is_verified = user.get("cardIdVerified", False) if user else False
            verification_text = "Verificado" if is_verified else "NO VERIFICADO (Requiere subir ID)"

            # Fetch active reservations for this user (as guest), up to 3
            reservations = list(reservations_col.find(
                {"userId": {"$in": query_ids}},
                {
                    "startDate": 1,
                    "endDate": 1,
                    "totalPrice": 1,
                    "status": 1,
                    "listingId": 1
                }
            ).sort("startDate", -1).limit(3))

            if not reservations:
                return (
                    f"User: {user_name}\n"
                    f"Active Reservations: None found. The user has no recent bookings on Mequedo."
                )

            # Format reservation context cleanly for the LLM
            # NOTE: We inform Laura about the limit so she can relay it to the user.
            context = f"User: {user_name}\nID Verification Status: {verification_text}\n"
            context += "CRITICAL NOTE: You (Laura) can only see the LAST 3 reservations for security and brevity. If the user has more, inform them they can see the full list in their dashboard.\n"
            context += "Active Reservations:\n"
            for r in reservations:
                start = str(r.get("startDate", "N/A")).split(" ")[0]
                end = str(r.get("endDate", "N/A")).split(" ")[0]
                total = r.get("totalPrice", "N/A")
                status = r.get("status", "Pending")
                
                listing_id = r.get("listingId")
                property_name = "Desconocida"
                location_val = ""
                
                if listing_id:
                    l_query_ids = [listing_id]
                    if isinstance(listing_id, str) and len(listing_id) == 24:
                        try: l_query_ids.append(ObjectId(listing_id))
                        except Exception: pass
                    
                    listing = listings_col.find_one(
                        {"_id": {"$in": l_query_ids}},
                        {"title": 1, "locationValue": 1}
                    )
                    if not listing:
                        listing = listings_col.find_one(
                            {"id": {"$in": l_query_ids}},
                            {"title": 1, "locationValue": 1}
                        )
                    
                    if listing:
                        property_name = listing.get("title", property_name)
                        location_val = listing.get("locationValue", "")
                        
                context += f"  - Alojamiento: {property_name} ({location_val}) | Status: {status} | Check-in: {start} → Check-out: {end} | Total: ${total}\n"

            return context

        except Exception as e:
            logger.error(f"UserContextTool failed for user_id={user_id}: {e}")
            return "Error: Could not retrieve user context at this time."
