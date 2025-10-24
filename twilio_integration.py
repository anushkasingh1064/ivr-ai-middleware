"""
Twilio Integration Module
Handles incoming calls from Twilio and converts to middleware format
Generates TwiML responses for Twilio IVR
Phone Number: +19789694592
"""

import logging
from typing import Dict, Optional
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os

logger = logging.getLogger(__name__)


class TwilioIntegration:
    """
    Integrates Twilio phone system with IVR middleware
    Handles TwiML generation and Twilio API calls
    """
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None
    ):
        # Load from environment variables (SECURE)
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER", "+19789694592")
        
        # Initialize Twilio client if credentials provided
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info(f"Twilio client initialized for {self.phone_number}")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("Twilio credentials not provided - client not initialized")
    
    def generate_welcome_twiml(self, callback_url: str) -> str:
        """
        Generate TwiML for initial call greeting
        
        Args:
            callback_url: URL for Twilio to send user input
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        # Welcome message
        response.say(
            "Welcome to Air India Customer Support. How can I help you today?",
            voice="Polly.Aditi",  # Indian English voice
            language="en-IN"
        )
        
        # Gather speech input
        gather = Gather(
            input='speech',
            action=callback_url,
            method='POST',
            speechTimeout='auto',
            language='en-IN'
        )
        
        gather.say(
            "You can say things like: book a flight, check flight status, or speak to an agent.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        
        response.append(gather)
        
        # If no input
        response.say(
            "I didn't hear anything. Please call back when you're ready.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        response.hangup()
        
        logger.info("Generated welcome TwiML")
        return str(response)
    
    def generate_response_twiml(
        self,
        message: str,
        callback_url: str,
        enable_dtmf: bool = False,
        next_action: Optional[str] = None
    ) -> str:
        """
        Generate TwiML response with AI message
        
        Args:
            message: Text to speak to caller
            callback_url: URL for next input
            enable_dtmf: Enable keypad input
            next_action: Next action identifier
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        # Speak the message
        response.say(
            message,
            voice="Polly.Aditi",
            language="en-IN"
        )
        
        # Gather next input
        input_type = 'speech dtmf' if enable_dtmf else 'speech'
        
        gather = Gather(
            input=input_type,
            action=callback_url,
            method='POST',
            speechTimeout='auto',
            language='en-IN',
            numDigits=1 if enable_dtmf else None
        )
        
        response.append(gather)
        
        # Timeout handling
        response.say(
            "I didn't receive your response. Let me transfer you to an agent.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        response.dial("+18005551234")  # Replace with actual agent number
        
        logger.info(f"Generated response TwiML with action: {next_action}")
        return str(response)
    
    def generate_menu_twiml(
        self,
        prompt: str,
        options: Dict[str, str],
        callback_url: str
    ) -> str:
        """
        Generate TwiML for DTMF menu
        
        Args:
            prompt: Menu prompt
            options: Dict of {digit: description}
            callback_url: URL for handling choice
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        # Build menu text
        menu_text = f"{prompt}. "
        for digit, description in options.items():
            menu_text += f"Press {digit} for {description}. "
        
        gather = Gather(
            input='dtmf',
            action=callback_url,
            method='POST',
            numDigits=1,
            timeout=5
        )
        
        gather.say(menu_text, voice="Polly.Aditi", language="en-IN")
        response.append(gather)
        
        # No input handling
        response.say(
            "I didn't receive your selection. Please try again.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        response.redirect(callback_url)
        
        logger.info("Generated menu TwiML")
        return str(response)
    
    def generate_confirmation_twiml(
        self,
        message: str,
        success: bool = True
    ) -> str:
        """
        Generate confirmation TwiML
        
        Args:
            message: Confirmation message
            success: Whether operation was successful
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        response.say(
            message,
            voice="Polly.Aditi",
            language="en-IN"
        )
        
        if success:
            response.say(
                "Thank you for calling Air India. Have a great day!",
                voice="Polly.Aditi",
                language="en-IN"
            )
        else:
            response.say(
                "Would you like to try again or speak to an agent? Say try again or agent.",
                voice="Polly.Aditi",
                language="en-IN"
            )
        
        response.hangup()
        
        logger.info(f"Generated confirmation TwiML (success={success})")
        return str(response)
    
    def generate_collect_info_twiml(
        self,
        field_name: str,
        prompt: str,
        callback_url: str,
        field_type: str = "text"
    ) -> str:
        """
        Generate TwiML to collect specific information
        
        Args:
            field_name: Name of field to collect
            prompt: What to ask the user
            callback_url: Where to send the response
            field_type: Type of data (text, date, number)
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        # Enhanced prompts based on field type
        enhanced_prompts = {
            "date": f"{prompt}. For example, say December 25th.",
            "number": f"{prompt}. Please speak the numbers clearly.",
            "text": prompt
        }
        
        gather = Gather(
            input='speech',
            action=callback_url,
            method='POST',
            speechTimeout='auto',
            language='en-IN',
            enhanced=True  # Better speech recognition
        )
        
        gather.say(
            enhanced_prompts.get(field_type, prompt),
            voice="Polly.Aditi",
            language="en-IN"
        )
        
        response.append(gather)
        
        # Retry on no input
        response.say(
            f"I didn't catch that. {prompt}",
            voice="Polly.Aditi",
            language="en-IN"
        )
        response.redirect(callback_url)
        
        logger.info(f"Generated info collection TwiML for {field_name}")
        return str(response)
    
    def generate_error_twiml(
        self,
        error_message: str = "Sorry, we're experiencing technical difficulties"
    ) -> str:
        """
        Generate error TwiML
        
        Args:
            error_message: Error message to speak
            
        Returns:
            TwiML string
        """
        response = VoiceResponse()
        
        response.say(
            f"{error_message}. Please try again later or press 0 to speak with an agent.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        
        gather = Gather(
            input='dtmf',
            numDigits=1,
            timeout=5
        )
        response.append(gather)
        
        response.say(
            "Thank you for calling. Goodbye.",
            voice="Polly.Aditi",
            language="en-IN"
        )
        response.hangup()
        
        logger.error(f"Generated error TwiML: {error_message}")
        return str(response)
    
    def parse_twilio_request(self, form_data: Dict) -> Dict:
        """
        Parse incoming Twilio request data
        
        Args:
            form_data: Form data from Twilio webhook
            
        Returns:
            Normalized request data
        """
        return {
            "call_id": form_data.get("CallSid"),
            "caller": form_data.get("From"),
            "user_input": form_data.get("SpeechResult") or form_data.get("Digits"),
            "input_type": "speech" if form_data.get("SpeechResult") else "dtmf",
            "call_status": form_data.get("CallStatus"),
            "from_country": form_data.get("FromCountry"),
            "to_number": form_data.get("To")
        }
    
    def make_outbound_call(
        self,
        to_number: str,
        twiml_url: str
    ) -> Optional[str]:
        """
        Make an outbound call using Twilio
        
        Args:
            to_number: Phone number to call
            twiml_url: URL with TwiML instructions
            
        Returns:
            Call SID if successful, None otherwise
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return None
        
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=twiml_url
            )
            logger.info(f"Outbound call initiated: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Failed to make outbound call: {e}")
            return None
    
    def send_sms(self, to_number: str, message: str) -> bool:
        """
        Send SMS notification
        
        Args:
            to_number: Recipient phone number
            message: Message text
            
        Returns:
            True if successful
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        try:
            message = self.client.messages.create(
                to=to_number,
                from_=self.phone_number,
                body=message
            )
            logger.info(f"SMS sent: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False