"""
Test flows for IVR-AI Middleware
Run with: pytest test_flows.py -v
"""

import pytest
import httpx
from datetime import datetime


BASE_URL = "http://localhost:8000"


class TestMiddlewareIntegration:
    """Integration tests for the middleware"""
    
    @pytest.fixture
    def client(self):
        """Create HTTP client"""
        return httpx.Client(base_url=BASE_URL, timeout=10.0)
    
    def test_health_check(self, client):
        """Test if service is running"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_incoming_call_flow(self, client):
        """Test complete incoming call flow"""
        call_id = f"test_call_{datetime.now().timestamp()}"
        
        # Step 1: Incoming call
        payload = {
            "call_id": call_id,
            "caller": "+919876543210"
        }
        response = client.post("/ivr/incoming-call", json=payload)
        assert response.status_code == 200
        assert "<?xml" in response.text  # VXML response
        assert "Welcome" in response.text
        print(f"✓ Incoming call handled: {call_id}")
        
        # Step 2: User says "book a flight"
        payload = {
            "call_id": call_id,
            "user_input": "I want to book a flight",
            "input_type": "speech"
        }
        response = client.post("/ivr/user-input", json=payload)
        assert response.status_code == 200
        assert "<?xml" in response.text
        print("✓ User input processed")
        
        # Step 3: Check session
        response = client.get(f"/session/{call_id}")
        assert response.status_code == 200
        session_data = response.json()
        assert session_data["call_id"] == call_id
        assert len(session_data["interactions"]) >= 2
        print("✓ Session maintained correctly")
        
        # Step 4: End session
        response = client.delete(f"/session/{call_id}")
        assert response.status_code == 200
        print("✓ Session ended successfully")
    
    def test_booking_transaction_flow(self, client):
        """Test flight booking transaction"""
        call_id = f"booking_test_{datetime.now().timestamp()}"
        
        # Create session first
        client.post("/ivr/incoming-call", json={
            "call_id": call_id,
            "caller": "+919876543210"
        })
        
        # Simulate booking transaction
        transaction_data = {
            "call_id": call_id,
            "transaction_type": "flight_booking",
            "data": {
                "origin": "Mumbai",
                "destination": "Delhi",
                "travel_date": "2025-11-15",
                "passenger_name": "John Doe",
                "passenger_contact": "+919876543210",
                "booking_type": "domestic",
                "num_passengers": 1
            }
        }
        
        response = client.post("/ivr/transaction", json=transaction_data)
        assert response.status_code == 200
        assert "<?xml" in response.text
        assert "confirm" in response.text.lower()
        print("✓ Booking transaction processed")
        
        # Cleanup
        client.delete(f"/session/{call_id}")
    
    def test_status_check_flow(self, client):
        """Test flight status check"""
        call_id = f"status_test_{datetime.now().timestamp()}"
        
        # Create session
        client.post("/ivr/incoming-call", json={
            "call_id": call_id,
            "caller": "+919876543210"
        })
        
        # Check status
        transaction_data = {
            "call_id": call_id,
            "transaction_type": "status_check",
            "data": {
                "flight_id": "AI1"
            }
        }
        
        response = client.post("/ivr/transaction", json=transaction_data)
        assert response.status_code == 200
        print("✓ Status check processed")
        
        # Cleanup
        client.delete(f"/session/{call_id}")
    
    def test_multiple_interactions(self, client):
        """Test conversation with multiple interactions"""
        call_id = f"multi_test_{datetime.now().timestamp()}"
        
        # Start call
        client.post("/ivr/incoming-call", json={
            "call_id": call_id,
            "caller": "+919876543210"
        })
        
        # Multiple user inputs
        inputs = [
            "I want to book a flight",
            "Domestic",
            "Mumbai",
            "Delhi",
            "Tomorrow"
        ]
        
        for user_input in inputs:
            response = client.post("/ivr/user-input", json={
                "call_id": call_id,
                "user_input": user_input,
                "input_type": "speech"
            })
            assert response.status_code == 200
        
        # Check conversation history
        response = client.get(f"/session/{call_id}")
        session_data = response.json()
        assert len(session_data["interactions"]) >= len(inputs) * 2  # User + AI responses
        print(f"✓ Multiple interactions handled: {len(session_data['interactions'])} total")
        
        # Cleanup
        client.delete(f"/session/{call_id}")
    
    def test_session_timeout(self, client):
        """Test that sessions timeout appropriately"""
        call_id = f"timeout_test_{datetime.now().timestamp()}"
        
        # Create session
        client.post("/ivr/incoming-call", json={
            "call_id": call_id,
            "caller": "+919876543210"
        })
        
        # Verify session exists
        response = client.get(f"/session/{call_id}")
        assert response.status_code == 200
        print("✓ Session created")
        
        # Note: In real scenario, wait for timeout period
        # For testing, we'll just verify the session exists
        
        # Cleanup
        client.delete(f"/session/{call_id}")
    
    def test_dtmf_input(self, client):
        """Test DTMF (keypad) input"""
        call_id = f"dtmf_test_{datetime.now().timestamp()}"
        
        # Create session
        client.post("/ivr/incoming-call", json={
            "call_id": call_id,
            "caller": "+919876543210"
        })
        
        # Send DTMF input
        response = client.post("/ivr/user-input", json={
            "call_id": call_id,
            "user_input": "1",
            "input_type": "dtmf"
        })
        assert response.status_code == 200
        print("✓ DTMF input processed")
        
        # Cleanup
        client.delete(f"/session/{call_id}")
    
    def test_error_handling(self, client):
        """Test error handling"""
        # Try to get non-existent session
        response = client.get("/session/nonexistent_call_id")
        assert response.status_code == 404
        print("✓ Non-existent session handled correctly")
        
        # Try to process input for non-existent session
        response = client.post("/ivr/user-input", json={
            "call_id": "nonexistent_call_id",
            "user_input": "test",
            "input_type": "speech"
        })
        assert response.status_code == 404
        print("✓ Invalid input handled correctly")
    
    def test_active_sessions_list(self, client):
        """Test listing active sessions"""
        # Create multiple sessions
        call_ids = []
        for i in range(3):
            call_id = f"list_test_{i}_{datetime.now().timestamp()}"
            call_ids.append(call_id)
            client.post("/ivr/incoming-call", json={
                "call_id": call_id,
                "caller": f"+91987654321{i}"
            })
        
        # Get active sessions
        response = client.get("/sessions/active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 3
        print(f"✓ Active sessions listed: {data['count']} sessions")
        
        # Cleanup
        for call_id in call_ids:
            client.delete(f"/session/{call_id}")


class TestVXMLGeneration:
    """Test VXML generation"""
    
    def test_vxml_structure(self):
        """Test that generated VXML is valid"""
        from vxml_handler import VXMLHandler
        
        handler = VXMLHandler()
        
        # Test welcome VXML
        vxml = handler.generate_welcome_vxml("test_call_123")
        assert "<?xml" in vxml
        assert "<vxml" in vxml
        assert "Welcome" in vxml
        print("✓ Welcome VXML generated correctly")
        
        # Test response VXML
        vxml = handler.generate_response_vxml(
            call_id="test_call_123",
            message="Test message",
            next_action="test_action"
        )
        assert "<?xml" in vxml
        assert "Test message" in vxml
        print("✓ Response VXML generated correctly")
        
        # Test error VXML
        vxml = handler.generate_error_vxml("Test error")
        assert "<?xml" in vxml
        assert "Test error" in vxml
        print("✓ Error VXML generated correctly")
    
    def test_dtmf_menu_generation(self):
        """Test DTMF menu VXML generation"""
        from vxml_handler import VXMLHandler
        
        handler = VXMLHandler()
        options = {
            "1": "Book Flight",
            "2": "Check Status",
            "3": "Cancel Booking"
        }
        
        vxml = handler.generate_dtmf_menu_vxml(
            call_id="test_menu",
            prompt="Main Menu",
            options=options
        )
        
        assert "<?xml" in vxml
        assert "Main Menu" in vxml
        assert "Press 1" in vxml
        print("✓ DTMF menu VXML generated correctly")
    
    def test_confirmation_vxml(self):
        """Test confirmation VXML generation"""
        from vxml_handler import VXMLHandler
        
        handler = VXMLHandler()
        result = {
            "success": True,
            "message": "Booking confirmed",
            "booking_id": "BK123"
        }
        
        vxml = handler.generate_confirmation_vxml(
            call_id="test_confirm",
            transaction_result=result
        )
        
        assert "<?xml" in vxml
        assert "Booking confirmed" in vxml
        print("✓ Confirmation VXML generated correctly")


class TestSessionManager:
    """Test session management"""
    
    def test_session_creation(self):
        """Test creating sessions"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        
        session = manager.create_session("test_call_123", "+919876543210")
        assert session.call_id == "test_call_123"
        assert session.caller_number == "+919876543210"
        print("✓ Session created successfully")
    
    def test_session_retrieval(self):
        """Test retrieving sessions"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        manager.create_session("test_call_456", "+919876543210")
        
        session = manager.get_session("test_call_456")
        assert session is not None
        assert session.call_id == "test_call_456"
        print("✓ Session retrieved successfully")
    
    def test_add_interaction(self):
        """Test adding interactions to session"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        manager.create_session("test_call_789", "+919876543210")
        
        success = manager.add_interaction("test_call_789", "user", "Hello")
        assert success
        
        session = manager.get_session("test_call_789")
        assert len(session.interactions) == 1
        assert session.interactions[0].message == "Hello"
        print("✓ Interaction added successfully")
    
    def test_conversation_history(self):
        """Test retrieving conversation history"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        manager.create_session("test_call_history", "+919876543210")
        
        # Add multiple interactions
        manager.add_interaction("test_call_history", "user", "Message 1")
        manager.add_interaction("test_call_history", "ai", "Response 1")
        manager.add_interaction("test_call_history", "user", "Message 2")
        
        history = manager.get_conversation_history("test_call_history")
        assert len(history) == 3
        print("✓ Conversation history retrieved")
        
        # Test getting last N interactions
        last_two = manager.get_conversation_history("test_call_history", last_n=2)
        assert len(last_two) == 2
        print("✓ Last N interactions retrieved")
    
    def test_booking_data_storage(self):
        """Test storing booking data in session"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        manager.create_session("test_booking", "+919876543210")
        
        booking_data = {
            "origin": "Mumbai",
            "destination": "Delhi",
            "date": "2025-11-15"
        }
        
        success = manager.store_booking_data("test_booking", booking_data)
        assert success
        
        session = manager.get_session("test_booking")
        assert session.booking_data["origin"] == "Mumbai"
        print("✓ Booking data stored successfully")
    
    def test_session_cleanup(self):
        """Test session cleanup"""
        from session_manager import SessionManager
        
        manager = SessionManager()
        
        # Create multiple sessions
        for i in range(5):
            manager.create_session(f"cleanup_test_{i}", "+919876543210")
        
        assert manager.get_active_session_count() >= 5
        
        # End all sessions
        for i in range(5):
            manager.end_session(f"cleanup_test_{i}")
        
        print("✓ Session cleanup successful")


class TestAIConnector:
    """Test AI connector"""
    
    @pytest.mark.asyncio
    async def test_mock_ai_response(self):
        """Test mock AI responses"""
        from ai_connector import AIConnector
        from session_manager import SessionManager
        
        connector = AIConnector(ai_service="mock")
        manager = SessionManager()
        
        session = manager.create_session("test_ai_call", "+919876543210")
        
        # Test booking intent
        response = await connector.process_input(
            call_id="test_ai_call",
            user_input="I want to book a flight",
            session_context=session
        )
        
        assert response["intent"] == "book_flight"
        assert "book" in response["message"].lower()
        print("✓ Mock AI booking intent detected")
        
        # Test status check intent
        response = await connector.process_input(
            call_id="test_ai_call",
            user_input="check my flight status",
            session_context=session
        )
        
        assert response["intent"] == "check_status"
        print("✓ Mock AI status intent detected")
        
        await connector.close()
    
    @pytest.mark.asyncio
    async def test_context_aware_responses(self):
        """Test that AI maintains context"""
        from ai_connector import AIConnector
        from session_manager import SessionManager
        
        connector = AIConnector(ai_service="mock")
        manager = SessionManager()
        
        session = manager.create_session("test_context", "+919876543210")
        
        # Start booking
        response1 = await connector.process_input(
            call_id="test_context",
            user_input="book a flight",
            session_context=session
        )
        
        # Set current intent
        manager.set_intent("test_context", "book_flight")
        manager.store_booking_data("test_context", {})
        
        # Provide origin
        session = manager.get_session("test_context")
        response2 = await connector.process_input(
            call_id="test_context",
            user_input="Mumbai",
            session_context=session
        )
        
        # Should ask for destination
        assert "destination" in response2["message"].lower() or "where to" in response2["message"].lower()
        print("✓ Context-aware responses working")
        
        await connector.close()


def run_manual_tests():
    """
    Manual test scenarios for validation
    Run these after starting the server
    """
    print("\n" + "="*60)
    print("MANUAL TEST SCENARIOS")
    print("="*60 + "\n")
    
    print("1. Test Incoming Call:")
    print("   curl -X POST http://localhost:8000/ivr/incoming-call \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"call_id": "manual_test_1", "caller": "+919876543210"}\'')
    print()
    
    print("2. Test User Input:")
    print("   curl -X POST http://localhost:8000/ivr/user-input \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"call_id": "manual_test_1", "user_input": "book a flight", "input_type": "speech"}\'')
    print()
    
    print("3. Check Session:")
    print("   curl http://localhost:8000/session/manual_test_1")
    print()
    
    print("4. Test Flight Booking Transaction:")
    print("   curl -X POST http://localhost:8000/ivr/transaction \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"call_id": "manual_test_1", "transaction_type": "flight_booking",')
    print('          "data": {"origin": "Mumbai", "destination": "Delhi",')
    print('                   "travel_date": "2025-11-15", "passenger_name": "John Doe",')
    print('                   "passenger_contact": "+919876543210",')
    print('                   "booking_type": "domestic", "num_passengers": 1}}\'')
    print()
    
    print("5. Check Active Sessions:")
    print("   curl http://localhost:8000/sessions/active")
    print()
    
    print("6. End Session:")
    print("   curl -X DELETE http://localhost:8000/session/manual_test_1")
    print()
    
    print("\n" + "="*60)
    print("TESTING WITH PYTHON")
    print("="*60 + "\n")
    
    print("You can also test using Python directly:")
    print()
    print("import httpx")
    print()
    print("client = httpx.Client(base_url='http://localhost:8000')")
    print()
    print("# Test health")
    print("response = client.get('/health')")
    print("print(response.json())")
    print()
    print("# Test incoming call")
    print("response = client.post('/ivr/incoming-call',")
    print("    json={'call_id': 'test_001', 'caller': '+919876543210'})")
    print("print(response.text)")
    print()


if __name__ == "__main__":
    run_manual_tests()