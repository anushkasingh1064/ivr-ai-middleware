"""
AI Connector
Integrates with Conversational AI platforms
Supports: Dialogflow, Rasa, OpenAI, custom AI services
"""

import logging
import httpx
from typing import Dict, Optional, Any
from models import AIRequest, AIResponse, CallSession

logger = logging.getLogger(__name__)


class AIConnector:
    """
    Connects middleware to AI/NLP services
    Handles intent recognition, entity extraction, and response generation
    """
    
    def __init__(
        self, 
        ai_service: str = "mock",  # Options: "mock", "dialogflow", "openai", "rasa"
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        self.ai_service = ai_service
        self.api_key = api_key
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"AIConnector initialized with service: {ai_service}")
    
    async def process_input(
        self, 
        call_id: str, 
        user_input: str,
        session_context: CallSession
    ) -> Dict[str, Any]:
        """
        Process user input through AI service
        
        Args:
            call_id: Call identifier
            user_input: User's speech/text input
            session_context: Current session data
            
        Returns:
            AI response with message and action
        """
        logger.info(f"Processing input for {call_id}: {user_input}")
        
        # Route to appropriate AI service
        if self.ai_service == "mock":
            return await self._mock_ai_response(user_input, session_context)
        elif self.ai_service == "dialogflow":
            return await self._dialogflow_request(call_id, user_input, session_context)
        elif self.ai_service == "openai":
            return await self._openai_request(call_id, user_input, session_context)
        elif self.ai_service == "rasa":
            return await self._rasa_request(call_id, user_input, session_context)
        else:
            raise ValueError(f"Unsupported AI service: {self.ai_service}")
    
    async def _mock_ai_response(
        self, 
        user_input: str,
        session_context: CallSession
    ) -> Dict[str, Any]:
        """
        Mock AI responses for testing (without external AI service)
        Replace this with real AI integration
        """
        user_input_lower = user_input.lower()
        
        # Intent detection (simple keyword matching)
        if any(word in user_input_lower for word in ["book", "booking", "reserve", "ticket"]):
            intent = "book_flight"
            message = "I can help you book a flight. Are you looking for a domestic or international flight?"
            action = "collect_booking_type"
            
        elif any(word in user_input_lower for word in ["status", "check", "flight status"]):
            intent = "check_status"
            message = "I can check your flight status. Please provide your flight number."
            action = "collect_flight_id"
            
        elif any(word in user_input_lower for word in ["cancel", "cancellation"]):
            intent = "cancel_booking"
            message = "I can help you cancel your booking. Please provide your booking ID."
            action = "collect_booking_id"
            
        elif any(word in user_input_lower for word in ["domestic"]):
            intent = "domestic_flight"
            message = "Great! Where would you like to fly from?"
            action = "collect_origin"
            
        elif any(word in user_input_lower for word in ["international"]):
            intent = "international_flight"
            message = "Perfect! Which city will you be departing from?"
            action = "collect_origin"
            
        elif any(word in user_input_lower for word in ["agent", "representative", "human"]):
            intent = "speak_to_agent"
            message = "I'll connect you with an agent. Please hold."
            action = "transfer_agent"
            
        else:
            # Handle context-based responses
            current_intent = session_context.current_intent
            
            if current_intent == "book_flight" and session_context.booking_data:
                booking = session_context.booking_data
                
                if "origin" not in booking:
                    booking["origin"] = user_input
                    message = "Great! And where would you like to fly to?"
                    action = "collect_destination"
                    
                elif "destination" not in booking:
                    booking["destination"] = user_input
                    message = "When would you like to travel? Please provide the date."
                    action = "collect_date"
                    
                elif "date" not in booking:
                    booking["date"] = user_input
                    message = "May I have your full name for the booking?"
                    action = "collect_passenger_name"
                    
                elif "passenger_name" not in booking:
                    booking["passenger_name"] = user_input
                    message = "And your contact number?"
                    action = "collect_contact"
                    
                elif "contact" not in booking:
                    booking["contact"] = user_input
                    message = f"Perfect! Let me confirm: Flying from {booking['origin']} to {booking['destination']} on {booking['date']} for {booking['passenger_name']}. Should I proceed with the booking?"
                    action = "confirm_booking"
                    
                else:
                    intent = "unknown"
                    message = "I didn't quite understand. Could you rephrase that?"
                    action = None
            else:
                intent = "unknown"
                message = "I didn't quite understand. You can say 'book a flight', 'check flight status', or 'cancel booking'."
                action = None
        
        return {
            "call_id": session_context.call_id,
            "message": message,
            "intent": intent,
            "action": action,
            "confidence": 0.85,
            "parameters": {}
        }
    
    async def _dialogflow_request(
        self, 
        call_id: str,
        user_input: str,
        session_context: CallSession
    ) -> Dict[str, Any]:
        """
        Send request to Google Dialogflow
        
        Documentation: https://cloud.google.com/dialogflow/es/docs/reference/rest/v2/projects.agent.sessions/detectIntent
        """
        if not self.api_key or not self.endpoint:
            raise ValueError("Dialogflow API key and endpoint required")
        
        url = f"{self.endpoint}/sessions/{call_id}:detectIntent"
        
        payload = {
            "queryInput": {
                "text": {
                    "text": user_input,
                    "languageCode": "en-US"
                }
            },
            "queryParams": {
                "contexts": self._build_dialogflow_contexts(session_context)
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            query_result = result.get("queryResult", {})
            
            return {
                "call_id": call_id,
                "message": query_result.get("fulfillmentText", "I didn't understand that."),
                "intent": query_result.get("intent", {}).get("displayName"),
                "action": query_result.get("action"),
                "confidence": query_result.get("intentDetectionConfidence", 0.0),
                "parameters": query_result.get("parameters", {})
            }
            
        except Exception as e:
            logger.error(f"Dialogflow request failed: {e}")
            return self._error_response(call_id)
    
    async def _openai_request(
        self, 
        call_id: str,
        user_input: str,
        session_context: CallSession
    ) -> Dict[str, Any]:
        """
        Send request to OpenAI API
        
        Documentation: https://platform.openai.com/docs/api-reference/chat
        """
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        # Build conversation history
        messages = [
            {
                "role": "system",
                "content": "You are an Air India customer support assistant. Help users book flights, check status, and handle cancellations. Keep responses concise and clear for voice interaction."
            }
        ]
        
        # Add conversation history
        for interaction in session_context.interactions[-5:]:  # Last 5 interactions
            role = "user" if interaction.speaker == "user" else "assistant"
            messages.append({"role": role, "content": interaction.message})
        
        # Add current input
        messages.append({"role": "user", "content": user_input})
        
        payload = {
            "model": "gpt-4",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            ai_message = result["choices"][0]["message"]["content"]
            
            # Extract intent and action from response (you may need function calling)
            intent = self._extract_intent(user_input, ai_message)
            action = self._determine_action(intent)
            
            return {
                "call_id": call_id,
                "message": ai_message,
                "intent": intent,
                "action": action,
                "confidence": 0.9,
                "parameters": {}
            }
            
        except Exception as e:
            logger.error(f"OpenAI request failed: {e}")
            return self._error_response(call_id)
    
    async def _rasa_request(
        self, 
        call_id: str,
        user_input: str,
        session_context: CallSession
    ) -> Dict[str, Any]:
        """
        Send request to Rasa NLU
        
        Documentation: https://rasa.com/docs/rasa/http-api
        """
        if not self.endpoint:
            raise ValueError("Rasa endpoint required")
        
        url = f"{self.endpoint}/model/parse"
        
        payload = {
            "text": user_input,
            "message_id": call_id
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            intent_data = result.get("intent", {})
            
            # Get response from Rasa Core
            core_url = f"{self.endpoint}/webhooks/rest/webhook"
            core_payload = {
                "sender": call_id,
                "message": user_input
            }
            
            core_response = await self.client.post(core_url, json=core_payload)
            core_result = core_response.json()
            
            bot_message = core_result[0].get("text", "") if core_result else "I didn't understand that."
            
            return {
                "call_id": call_id,
                "message": bot_message,
                "intent": intent_data.get("name"),
                "action": self._determine_action(intent_data.get("name")),
                "confidence": intent_data.get("confidence", 0.0),
                "parameters": {entity["entity"]: entity["value"] for entity in result.get("entities", [])}
            }
            
        except Exception as e:
            logger.error(f"Rasa request failed: {e}")
            return self._error_response(call_id)
    
    def _build_dialogflow_contexts(self, session_context: CallSession) -> list:
        """Build Dialogflow context objects from session"""
        contexts = []
        
        if session_context.current_intent:
            contexts.append({
                "name": f"projects/your-project/agent/sessions/{session_context.call_id}/contexts/{session_context.current_intent}",
                "lifespanCount": 5,
                "parameters": session_context.context
            })
        
        return contexts
    
    def _extract_intent(self, user_input: str, ai_response: str) -> str:
        """Extract intent from user input and AI response"""
        # Simple keyword-based extraction (enhance with better NLP)
        user_lower = user_input.lower()
        
        if "book" in user_lower:
            return "book_flight"
        elif "status" in user_lower or "check" in user_lower:
            return "check_status"
        elif "cancel" in user_lower:
            return "cancel_booking"
        else:
            return "general_inquiry"
    
    def _determine_action(self, intent: Optional[str]) -> Optional[str]:
        """Map intent to next action"""
        action_map = {
            "book_flight": "collect_booking_type",
            "check_status": "collect_flight_id",
            "cancel_booking": "collect_booking_id",
            "speak_to_agent": "transfer_agent"
        }
        
        return action_map.get(intent) if intent else None
    
    def _error_response(self, call_id: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            "call_id": call_id,
            "message": "I'm having trouble processing that. Could you try again?",
            "intent": "error",
            "action": None,
            "confidence": 0.0,
            "parameters": {}
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()