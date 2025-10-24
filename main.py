"""
IVR-to-AI Middleware API
Main application entry point with Twilio integration
Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import Response, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our custom modules
from models import (
    VXMLRequest, AIRequest, CallSession, 
    FlightBooking, FlightStatus
)
from session_manager import SessionManager
from vxml_handler import VXMLHandler
from ai_connector import AIConnector
from twilio_integration import TwilioIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="IVR-AI Middleware",
    description="Middleware layer connecting VXML IVR and Twilio to Conversational AI",
    version="1.0.0"
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
session_manager = SessionManager()
vxml_handler = VXMLHandler()
ai_connector = AIConnector()
twilio = TwilioIntegration()

# Health check endpoint
@app.get("/health")
def health_check():
    """Check if the middleware is running"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": session_manager.get_active_session_count(),
        "twilio_configured": twilio.client is not None,
        "twilio_number": twilio.phone_number
    }

# ============================================
# Twilio Integration Endpoints
# ============================================

@app.post("/twilio/voice", response_class=PlainTextResponse)
async def twilio_incoming_call(request: Request):
    """
    Entry point for incoming Twilio calls
    Twilio will POST to this URL when call comes to +19789694592
    
    WHERE THIS RUNS: Called by Twilio when someone calls your number
    """
    try:
        # Parse Twilio request
        form_data = await request.form()
        parsed_data = twilio.parse_twilio_request(dict(form_data))
        
        call_id = parsed_data["call_id"]
        caller_number = parsed_data["caller"]
        
        logger.info(f"Twilio incoming call: {call_id} from {caller_number}")
        
        # Create new session
        session = session_manager.create_session(
            call_id=call_id,
            caller_number=caller_number
        )
        
        # Generate welcome TwiML
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        callback_url = f"{base_url}/twilio/gather"
        
        twiml = twilio.generate_welcome_twiml(callback_url)
        
        return PlainTextResponse(content=twiml, media_type="text/xml")
    
    except Exception as e:
        logger.error(f"Error handling Twilio incoming call: {e}")
        error_twiml = twilio.generate_error_twiml()
        return PlainTextResponse(content=error_twiml, media_type="text/xml")


@app.post("/twilio/gather", response_class=PlainTextResponse)
async def twilio_gather_input(request: Request):
    """
    Receives user input from Twilio (voice or DTMF)
    
    WHERE THIS RUNS: Called by Twilio after user speaks or presses keys
    """
    try:
        # Parse Twilio request
        form_data = await request.form()
        parsed_data = twilio.parse_twilio_request(dict(form_data))
        
        call_id = parsed_data["call_id"]
        user_input = parsed_data["user_input"]
        input_type = parsed_data["input_type"]
        
        logger.info(f"Twilio input for {call_id}: {user_input} ({input_type})")
        
        # Get existing session
        session = session_manager.get_session(call_id)
        if not session:
            logger.error(f"Session not found for {call_id}")
            error_twiml = twilio.generate_error_twiml("Session expired")
            return PlainTextResponse(content=error_twiml, media_type="text/xml")
        
        # Update session with user input
        session_manager.add_interaction(call_id, "user", user_input)
        
        # Send to AI for processing
        ai_response = await ai_connector.process_input(
            call_id=call_id,
            user_input=user_input,
            session_context=session
        )
        
        # Update session with AI response
        session_manager.add_interaction(call_id, "ai", ai_response["message"])
        
        # Generate TwiML response
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        callback_url = f"{base_url}/twilio/gather"
        
        twiml = twilio.generate_response_twiml(
            message=ai_response["message"],
            callback_url=callback_url,
            enable_dtmf=True,
            next_action=ai_response.get("action")
        )
        
        return PlainTextResponse(content=twiml, media_type="text/xml")
    
    except Exception as e:
        logger.error(f"Error processing Twilio input: {e}")
        error_twiml = twilio.generate_error_twiml()
        return PlainTextResponse(content=error_twiml, media_type="text/xml")


@app.post("/twilio/action", response_class=PlainTextResponse)
async def twilio_action(request: Request):
    """
    Handles completed actions (bookings, status checks, etc.)
    
    WHERE THIS RUNS: Called when user completes a transaction
    """
    try:
        form_data = await request.form()
        parsed_data = twilio.parse_twilio_request(dict(form_data))
        
        call_id = parsed_data["call_id"]
        
        logger.info(f"Twilio action for {call_id}")
        
        # Get session to check what action was completed
        session = session_manager.get_session(call_id)
        if not session:
            error_twiml = twilio.generate_error_twiml("Session expired")
            return PlainTextResponse(content=error_twiml, media_type="text/xml")
        
        # Process based on current intent
        if session.current_intent == "book_flight" and session.booking_data:
            # Complete booking
            result = await process_flight_booking(call_id, session.booking_data)
            message = result["message"]
            success = result["success"]
        else:
            message = "Thank you for using Air India customer support."
            success = True
        
        # Generate confirmation TwiML
        twiml = twilio.generate_confirmation_twiml(message, success)
        
        # End session
        session_manager.end_session(call_id)
        
        return PlainTextResponse(content=twiml, media_type="text/xml")
    
    except Exception as e:
        logger.error(f"Error in Twilio action: {e}")
        error_twiml = twilio.generate_error_twiml()
        return PlainTextResponse(content=error_twiml, media_type="text/xml")


@app.post("/twilio/status", response_class=PlainTextResponse)
async def twilio_status_callback(request: Request):
    """
    Receives call status updates from Twilio
    
    WHERE THIS RUNS: Called by Twilio for call events (ringing, answered, completed)
    """
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        
        logger.info(f"Twilio status callback: {call_sid} - {call_status}")
        
        # Update session status if needed
        if call_status in ["completed", "failed", "no-answer"]:
            session = session_manager.get_session(call_sid)
            if session:
                from models import CallStatus as SessionStatus
                status_map = {
                    "completed": SessionStatus.COMPLETED,
                    "failed": SessionStatus.FAILED,
                    "no-answer": SessionStatus.FAILED
                }
                session_manager.end_session(call_sid, status_map.get(call_status, SessionStatus.COMPLETED))
        
        return PlainTextResponse(content="OK", media_type="text/plain")
    
    except Exception as e:
        logger.error(f"Error in status callback: {e}")
        return PlainTextResponse(content="ERROR", media_type="text/plain")


# ============================================
# VXML IVR Integration Endpoints (Legacy Support)
# ============================================

@app.post("/ivr/incoming-call")
async def handle_incoming_call(request: Request):
    """
    Entry point when a call comes into the IVR system
    VXML system will POST to this endpoint with call details
    
    WHERE THIS RUNS: Called by your VXML IVR system
    """
    try:
        # Parse incoming VXML request
        body = await request.json()
        call_id = body.get("CallSid") or body.get("call_id")
        caller_number = body.get("From") or body.get("caller")
        
        logger.info(f"Incoming call: {call_id} from {caller_number}")
        
        # Create new session
        session = session_manager.create_session(
            call_id=call_id,
            caller_number=caller_number
        )
        
        # Generate initial VXML response
        vxml_response = vxml_handler.generate_welcome_vxml(call_id)
        
        return Response(content=vxml_response, media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ivr/user-input")
async def handle_user_input(request: Request):
    """
    Receives user input from VXML (voice/DTMF) and processes it
    This is called after user speaks or presses keys
    
    WHERE THIS RUNS: Called by VXML IVR after capturing user input
    """
    try:
        body = await request.json()
        call_id = body.get("call_id")
        user_input = body.get("user_input")  # Speech transcript or DTMF
        input_type = body.get("input_type", "speech")  # "speech" or "dtmf"
        
        logger.info(f"User input for {call_id}: {user_input} ({input_type})")
        
        # Get existing session
        session = session_manager.get_session(call_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update session with user input
        session_manager.add_interaction(call_id, "user", user_input)
        
        # Send to AI for processing
        ai_response = await ai_connector.process_input(
            call_id=call_id,
            user_input=user_input,
            session_context=session
        )
        
        # Update session with AI response
        session_manager.add_interaction(call_id, "ai", ai_response["message"])
        
        # Convert AI response to VXML
        vxml_response = vxml_handler.generate_response_vxml(
            call_id=call_id,
            message=ai_response["message"],
            next_action=ai_response.get("action")
        )
        
        return Response(content=vxml_response, media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Error processing user input: {e}")
        # Return error VXML
        error_vxml = vxml_handler.generate_error_vxml()
        return Response(content=error_vxml, media_type="application/xml")


@app.post("/ivr/transaction")
async def handle_transaction(request: Request):
    """
    Handles specific transactions like booking, cancellation, status check
    
    WHERE THIS RUNS: Called when user completes a specific action
    """
    try:
        body = await request.json()
        call_id = body.get("call_id")
        transaction_type = body.get("transaction_type")
        transaction_data = body.get("data")
        
        logger.info(f"Transaction for {call_id}: {transaction_type}")
        
        # Process based on transaction type
        if transaction_type == "flight_booking":
            result = await process_flight_booking(call_id, transaction_data)
        elif transaction_type == "status_check":
            result = await process_status_check(call_id, transaction_data)
        elif transaction_type == "cancellation":
            result = await process_cancellation(call_id, transaction_data)
        else:
            raise HTTPException(status_code=400, detail="Unknown transaction type")
        
        # Generate confirmation VXML
        vxml_response = vxml_handler.generate_confirmation_vxml(
            call_id=call_id,
            transaction_result=result
        )
        
        return Response(content=vxml_response, media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Transaction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# AI Integration Endpoints
# ============================================

@app.post("/ai/webhook")
async def ai_webhook(request: Request):
    """
    Receives callbacks from AI service
    Used for async AI responses or events
    
    WHERE THIS RUNS: Called by your AI service (e.g., Dialogflow, Rasa)
    """
    try:
        body = await request.json()
        call_id = body.get("call_id")
        ai_event = body.get("event")
        
        logger.info(f"AI webhook for {call_id}: {ai_event}")
        
        # Process AI event and update session
        session_manager.update_session(call_id, {"ai_event": ai_event})
        
        return {"status": "received", "call_id": call_id}
    
    except Exception as e:
        logger.error(f"AI webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Session Management Endpoints
# ============================================

@app.get("/session/{call_id}")
def get_session(call_id: str):
    """
    Retrieve session data for a specific call
    Useful for debugging and monitoring
    """
    session = session_manager.get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/session/{call_id}")
def end_session(call_id: str):
    """
    End a call session and cleanup resources
    """
    session_manager.end_session(call_id)
    return {"status": "session ended", "call_id": call_id}


@app.get("/sessions/active")
def get_active_sessions():
    """
    Get all active call sessions
    """
    return {
        "count": session_manager.get_active_session_count(),
        "sessions": session_manager.get_all_sessions()
    }


# ============================================
# Business Logic Functions
# ============================================

async def process_flight_booking(call_id: str, data: dict):
    """Process a flight booking transaction"""
    booking = FlightBooking(**data)
    
    # Add business logic here (database, external API calls, etc.)
    booking_id = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return {
        "success": True,
        "booking_id": booking_id,
        "message": f"Booking confirmed from {booking.origin} to {booking.destination}",
        "details": booking.dict()
    }


async def process_status_check(call_id: str, data: dict):
    """Check flight status"""
    flight_id = data.get("flight_id")
    
    # Mock flight data (replace with actual database query)
    flights = {
        "AI1": {"status": "On Time", "origin": "Mumbai", "destination": "Delhi"},
        "AI2": {"status": "Delayed", "origin": "Chennai", "destination": "Bangalore"},
    }
    
    if flight_id in flights:
        return {
            "success": True,
            "flight_id": flight_id,
            **flights[flight_id]
        }
    else:
        return {
            "success": False,
            "message": "Flight not found"
        }


async def process_cancellation(call_id: str, data: dict):
    """Process booking cancellation"""
    booking_id = data.get("booking_id")
    
    # Add cancellation logic here
    return {
        "success": True,
        "booking_id": booking_id,
        "message": "Booking cancelled successfully"
    }


# ============================================
# Error Handlers
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler"""
    logger.error(f"Unhandled exception: {exc}")
    return Response(
        content=vxml_handler.generate_error_vxml(),
        media_type="application/xml",
        status_code=500
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)