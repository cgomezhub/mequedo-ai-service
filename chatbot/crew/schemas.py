from pydantic import BaseModel, Field
from typing import Optional

class IntentSchema(BaseModel):
    intent_type: str = Field(..., description="Classification of the user input: 'search', 'faq', 'crm', or 'other'.")
    search_city: Optional[str] = Field(None, description="Extracted city name for accommodation searches.")
    search_max_price: Optional[int] = Field(None, description="Extracted strict maximum price limit.")
    search_guests: Optional[int] = Field(None, description="Extracted guest count.")
    search_bedrooms: Optional[int] = Field(None, description="Extracted bedroom requirement.")
    search_bathrooms: Optional[int] = Field(None, description="Extracted bathroom requirement.")
