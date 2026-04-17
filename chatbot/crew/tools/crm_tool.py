from pydantic import BaseModel, Field
from typing import Type
import logging
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)

class CRMQueryArgs(BaseModel):
    user_id: str = Field(..., description="The phone number or ID of the user requesting help.")

class MequedoInternalCRMTool(BaseTool):
    name: str = "Mequedo CRM Profile Fetcher"
    description: str = (
        "Fetches the user's single most recent reservation history and account status from the internal Mequedo CRM database. "
        "Use this exclusively when a user asks about their specific past bookings or reservation status."
    )
    args_schema: Type[BaseModel] = CRMQueryArgs

    def _run(self, user_id: str) -> str:
        try:
            from chatbot.crew.tools.search_accommodation import get_db
            db = get_db()
            if db is None:
                return "Error: Database connection unavailable for CRM query."

            users_col = db.get_collection("User")
            reservations_col = db.get_collection("Reservation")

            user = users_col.find_one({"phoneNumber": user_id})
            if not user:
                # If they passed an opaque ID instead of phone, try matching _id
                from bson.objectid import ObjectId
                try:
                    user = users_col.find_one({"_id": ObjectId(user_id)})
                except:
                    return f"User {user_id} not found in the Mequedo database."

            if not user:
                return f"User {user_id} not found in the Mequedo database."

            user_mongo_id = user["_id"]
            user_name = user.get("name", "Unknown")
            is_active = "Active" if user.get("isPhoneVerified") else "Pending Verification"

            # Query the user's latest reservation
            latest_res = reservations_col.find_one(
                {"userId": user_mongo_id},
                sort=[("createdAt", -1)]
            )

            if not latest_res:
                return f"User {user_name} ({is_active}) has no current or past reservations recorded."

            res_status = latest_res.get("status", "Unknown")
            res_total = latest_res.get("totalPrice", 0)
            check_in = latest_res.get("startDate", "Unknown date")
            check_out = latest_res.get("endDate", "Unknown date")

            # Try to fetch property info
            property_name = "Unknown Property"
            listing_id = latest_res.get("listingId")
            if listing_id:
                listings_col = db.get_collection("Listing")
                listing = listings_col.find_one({"_id": listing_id}, {"title": 1})
                if listing:
                    property_name = listing.get("title", "Unknown Property")

            return (
                f"CRM Record for {user_name} ({is_active}):\n"
                f"Most Recent Reservation:\n"
                f"- Property: {property_name}\n"
                f"- Status: {res_status}\n"
                f"- Check-In: {check_in} | Check-Out: {check_out}\n"
                f"- Total Price: ${res_total}"
            )
            
        except Exception as e:
            logger.error(f"CRM Tool Failed: {e}")
            return "An internal error occurred while fetching the reservation records."
