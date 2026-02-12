from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal
from enum import Enum
import uuid

class PackageType(str, Enum):
    HOLIDAY = "holiday"
    PARTY = "party"
    SHOPPING = "shopping"
    ACTIVITY = "activity"
    MIXED = "mixed"

class BookingStatus(str, Enum):
    DRAFT = "draft"
    BOOKED = "booked"
    FAILED = "failed"
    PARTIAL = "partial"

class PackageItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # e.g., "Flight to Paris", "Dinosaur Cake"
    description: Optional[str] = None
    item_type: str # flight, hotel, activity, product
    price: float = 0.0
    status: BookingStatus = BookingStatus.DRAFT
    metadata: Dict = {} # Store specific details like dates, size, etc.

class Package(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str = "web_user" # Default for now
    title: str = "New Package"
    type: PackageType = PackageType.MIXED
    items: List[PackageItem] = []
    total_price: float = 0.0
    status: BookingStatus = BookingStatus.DRAFT
    
    def calculate_total(self):
        self.total_price = sum(item.price for item in self.items)
