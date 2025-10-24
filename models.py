"""
Data models for IVR-AI Middleware
Defines the structure of data exchanged between systems
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class InputType(str, Enum):
    """Type of user input"""
    SPEECH = "speech"
    DTMF = "dtmf"
    TEXT = "text"


class CallStatus(str, Enum):
    """Status of a call session"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class VXMLRequest(BaseModel):
    """Incoming request from VXML IVR system"""
    call_id: str = Field(..., description="Unique call identifier")
    caller_number: str = Field(..., description="Caller's phone number")
    user_input: Optional[str] = Field(None, description="User's speech or DTMF input")
    input_type: InputType = Field(InputType.SPEECH, description="Type of input")
    timestamp: datetime = Field(default_factory=datetime.now)


class AIRequest(BaseModel):
    """Request sent to AI service"""
    call_id: str
    user_input: str
    context: Dict[str, Any] = Field(default_factory=dict)
    language: str = Field("en-US", description="Language code")
    session_id: Optional[str] = None


class AIResponse(BaseModel):
    """Response received from AI service"""
    call_id: str
    message: str
    action: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    intent: Optional[str] = None


class Interaction(BaseModel):
    """Single interaction in a conversation"""
    timestamp: datetime = Field(default_factory=datetime.now)
    speaker: str  # "user" or "ai"
    message: str
    input_type: Optional[InputType] = None


class CallSession(BaseModel):
    """Complete call session data"""
    call_id: str
    caller_number: str
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: CallStatus = CallStatus.ACTIVE
    interactions: List[Interaction] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Business-specific fields
    current_intent: Optional[str] = None
    booking_data: Optional[Dict[str, Any]] = None
    customer_id: Optional[str] = None


class FlightBooking(BaseModel):
    """Flight booking details"""
    origin: str = Field(..., min_length=3, max_length=50)
    destination: str = Field(..., min_length=3, max_length=50)
    travel_date: str = Field(..., description="Date in YYYY-MM-DD format")
    passenger_name: str
    passenger_contact: str
    booking_type: str = Field(..., description="domestic or international")
    num_passengers: int = Field(1, ge=1, le=9)


class FlightStatus(BaseModel):
    """Flight status query"""
    flight_id: str = Field(..., description="Flight identifier (e.g., AI123)")
    query_time: datetime = Field(default_factory=datetime.now)


class BookingCancellation(BaseModel):
    """Booking cancellation request"""
    booking_id: str
    reason: Optional[str] = None
    refund_requested: bool = False


class VXMLResponse(BaseModel):
    """Structured VXML response data"""
    prompt: str
    next_action: Optional[str] = None
    grammar: Optional[str] = None
    dtmf_options: Optional[Dict[str, str]] = None