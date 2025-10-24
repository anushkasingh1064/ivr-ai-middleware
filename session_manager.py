"""
Session Manager
Handles call session storage and management
Maintains state across multiple IVR interactions
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from models import CallSession, Interaction, CallStatus, InputType

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages active call sessions
    In production, use Redis or a database for distributed systems
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, CallSession] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        logger.info("SessionManager initialized")
    
    def create_session(self, call_id: str, caller_number: str) -> CallSession:
        """
        Create a new call session
        
        Args:
            call_id: Unique call identifier
            caller_number: Caller's phone number
            
        Returns:
            CallSession object
        """
        if call_id in self.sessions:
            logger.warning(f"Session {call_id} already exists, returning existing")
            return self.sessions[call_id]
        
        session = CallSession(
            call_id=call_id,
            caller_number=caller_number,
            start_time=datetime.now(),
            status=CallStatus.ACTIVE,
            interactions=[],
            context={}
        )
        
        self.sessions[call_id] = session
        logger.info(f"Created session for call {call_id}")
        return session
    
    def get_session(self, call_id: str) -> Optional[CallSession]:
        """
        Retrieve an existing session
        
        Args:
            call_id: Call identifier
            
        Returns:
            CallSession if found, None otherwise
        """
        session = self.sessions.get(call_id)
        
        if session:
            # Check if session has timed out
            if self._is_session_expired(session):
                logger.warning(f"Session {call_id} has expired")
                self.end_session(call_id)
                return None
            
            return session
        
        logger.warning(f"Session {call_id} not found")
        return None
    
    def update_session(self, call_id: str, updates: Dict) -> bool:
        """
        Update session context with new data
        
        Args:
            call_id: Call identifier
            updates: Dictionary of updates to apply to context
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(call_id)
        if not session:
            return False
        
        session.context.update(updates)
        logger.info(f"Updated session {call_id} with {len(updates)} fields")
        return True
    
    def add_interaction(
        self, 
        call_id: str, 
        speaker: str, 
        message: str,
        input_type: Optional[InputType] = None
    ) -> bool:
        """
        Add an interaction (user or AI message) to the session
        
        Args:
            call_id: Call identifier
            speaker: "user" or "ai"
            message: The message content
            input_type: Type of input (speech, dtmf, text)
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(call_id)
        if not session:
            return False
        
        interaction = Interaction(
            timestamp=datetime.now(),
            speaker=speaker,
            message=message,
            input_type=input_type
        )
        
        session.interactions.append(interaction)
        logger.info(f"Added {speaker} interaction to session {call_id}")
        return True
    
    def get_conversation_history(
        self, 
        call_id: str, 
        last_n: Optional[int] = None
    ) -> List[Interaction]:
        """
        Get conversation history for a session
        
        Args:
            call_id: Call identifier
            last_n: If specified, return only last N interactions
            
        Returns:
            List of Interaction objects
        """
        session = self.get_session(call_id)
        if not session:
            return []
        
        interactions = session.interactions
        if last_n:
            return interactions[-last_n:]
        return interactions
    
    def set_intent(self, call_id: str, intent: str) -> bool:
        """
        Set the current intent for a session
        
        Args:
            call_id: Call identifier
            intent: Intent name (e.g., "book_flight", "check_status")
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(call_id)
        if not session:
            return False
        
        session.current_intent = intent
        logger.info(f"Set intent for {call_id}: {intent}")
        return True
    
    def store_booking_data(self, call_id: str, booking_data: Dict) -> bool:
        """
        Store booking-related data in session
        
        Args:
            call_id: Call identifier
            booking_data: Dictionary containing booking information
            
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(call_id)
        if not session:
            return False
        
        if not session.booking_data:
            session.booking_data = {}
        
        session.booking_data.update(booking_data)
        logger.info(f"Stored booking data for {call_id}")
        return True
    
    def end_session(self, call_id: str, status: CallStatus = CallStatus.COMPLETED) -> bool:
        """
        End a call session
        
        Args:
            call_id: Call identifier
            status: Final status of the call
            
        Returns:
            True if successful, False otherwise
        """
        session = self.sessions.get(call_id)
        if not session:
            return False
        
        session.end_time = datetime.now()
        session.status = status
        
        # In production, you would:
        # 1. Save session to database for analytics
        # 2. Trigger any cleanup tasks
        # 3. Send session data to analytics pipeline
        
        logger.info(f"Ended session {call_id} with status {status}")
        
        # Remove from active sessions
        del self.sessions[call_id]
        return True
    
    def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get summary of all active sessions
        
        Returns:
            List of session summaries
        """
        return [
            {
                "call_id": session.call_id,
                "caller_number": session.caller_number,
                "start_time": session.start_time.isoformat(),
                "status": session.status,
                "interaction_count": len(session.interactions),
                "current_intent": session.current_intent
            }
            for session in self.sessions.values()
        ]
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove sessions that have exceeded timeout
        Should be called periodically
        
        Returns:
            Number of sessions cleaned up
        """
        expired_ids = [
            call_id for call_id, session in self.sessions.items()
            if self._is_session_expired(session)
        ]
        
        for call_id in expired_ids:
            self.end_session(call_id, status=CallStatus.FAILED)
        
        logger.info(f"Cleaned up {len(expired_ids)} expired sessions")
        return len(expired_ids)
    
    def _is_session_expired(self, session: CallSession) -> bool:
        """Check if a session has expired"""
        if not session.interactions:
            # No interactions yet, check start time
            time_diff = datetime.now() - session.start_time
        else:
            # Check last interaction time
            last_interaction = session.interactions[-1]
            time_diff = datetime.now() - last_interaction.timestamp
        
        return time_diff > self.session_timeout
    
    def get_session_duration(self, call_id: str) -> Optional[timedelta]:
        """
        Get duration of a session
        
        Args:
            call_id: Call identifier
            
        Returns:
            timedelta object or None
        """
        session = self.get_session(call_id)
        if not session:
            return None
        
        end = session.end_time or datetime.now()
        return end - session.start_time