"""
VXML Handler
Generates VXML responses for legacy IVR systems
Converts AI responses into VXML format
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class VXMLHandler:
    """
    Handles VXML generation for IVR responses
    VXML = VoiceXML, the markup language for voice applications
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        logger.info("VXMLHandler initialized")
    
    def generate_welcome_vxml(self, call_id: str) -> str:
        """
        Generate initial welcome VXML when call starts
        
        Args:
            call_id: Unique call identifier
            
        Returns:
            VXML string
        """
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="welcome">
        <block>
            <prompt>
                Welcome to Air India Customer Support. 
                How can I help you today?
            </prompt>
            
            <!-- Capture user's speech input -->
            <field name="user_input">
                <grammar type="application/srgs+xml" mode="voice">
                    <![CDATA[
                    #JSGF V1.0;
                    grammar request;
                    public <request> = book flight | check status | cancel booking | speak to agent;
                    ]]>
                </grammar>
                
                <filled>
                    <!-- Send user input back to middleware -->
                    <submit 
                        next="{self.base_url}/ivr/user-input" 
                        method="post" 
                        namelist="user_input"
                        enctype="application/json">
                        <param name="call_id" expr="'{call_id}'"/>
                        <param name="user_input" expr="user_input"/>
                        <param name="input_type" expr="'speech'"/>
                    </submit>
                </filled>
                
                <noinput count="1">
                    <prompt>I didn't hear you. Please say how I can help you.</prompt>
                    <reprompt/>
                </noinput>
                
                <nomatch count="1">
                    <prompt>I didn't understand that. You can say book flight, check status, or cancel booking.</prompt>
                    <reprompt/>
                </nomatch>
            </field>
        </block>
    </form>
</vxml>"""
        
        logger.info(f"Generated welcome VXML for {call_id}")
        return vxml
    
    def generate_response_vxml(
        self, 
        call_id: str, 
        message: str,
        next_action: Optional[str] = None,
        enable_dtmf: bool = True
    ) -> str:
        """
        Generate VXML response with AI message
        
        Args:
            call_id: Call identifier
            message: Text to speak to user
            next_action: Next action (e.g., "collect_origin", "confirm_booking")
            enable_dtmf: Whether to enable keypad input
            
        Returns:
            VXML string
        """
        # Escape special XML characters
        message = self._escape_xml(message)
        
        dtmf_grammar = ""
        if enable_dtmf:
            dtmf_grammar = """
                <grammar type="application/srgs+xml" mode="dtmf">
                    <![CDATA[
                    #JSGF V1.0;
                    grammar digits;
                    public <digit> = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
                    ]]>
                </grammar>
            """
        
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="response">
        <block>
            <prompt>{message}</prompt>
        </block>
        
        <field name="user_response">
            <!-- Voice grammar -->
            <grammar type="application/srgs+xml" mode="voice">
                <![CDATA[
                #JSGF V1.0;
                grammar response;
                public <response> = <word>+;
                ]]>
            </grammar>
            
            {dtmf_grammar}
            
            <filled>
                <submit 
                    next="{self.base_url}/ivr/user-input" 
                    method="post" 
                    enctype="application/json">
                    <param name="call_id" expr="'{call_id}'"/>
                    <param name="user_input" expr="user_response"/>
                    <param name="next_action" expr="'{next_action or ''}'"/>
                </submit>
            </filled>
            
            <noinput count="1">
                <prompt>I didn't hear you. Please repeat.</prompt>
                <reprompt/>
            </noinput>
            
            <noinput count="2">
                <prompt>I still didn't hear you. Let me transfer you to an agent.</prompt>
                <goto next="#transfer_agent"/>
            </noinput>
        </field>
    </form>
    
    <form id="transfer_agent">
        <block>
            <prompt>Please hold while I transfer you.</prompt>
            <transfer dest="tel:+18005551234"/>
        </block>
    </form>
</vxml>"""
        
        logger.info(f"Generated response VXML for {call_id}")
        return vxml
    
    def generate_confirmation_vxml(
        self, 
        call_id: str, 
        transaction_result: Dict
    ) -> str:
        """
        Generate VXML for transaction confirmation
        
        Args:
            call_id: Call identifier
            transaction_result: Result of transaction
            
        Returns:
            VXML string
        """
        success = transaction_result.get("success", False)
        message = self._escape_xml(transaction_result.get("message", "Transaction completed"))
        
        if success:
            prompt = f"{message}. Is there anything else I can help you with?"
        else:
            prompt = f"Sorry, there was an issue: {message}. Would you like to try again?"
        
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="confirmation">
        <block>
            <prompt>{prompt}</prompt>
        </block>
        
        <field name="continue_response">
            <grammar type="application/srgs+xml" mode="voice">
                <![CDATA[
                #JSGF V1.0;
                grammar yesno;
                public <yesno> = yes | no | sure | nope;
                ]]>
            </grammar>
            
            <filled>
                <if cond="continue_response == 'yes' || continue_response == 'sure'">
                    <submit 
                        next="{self.base_url}/ivr/user-input" 
                        method="post" 
                        enctype="application/json">
                        <param name="call_id" expr="'{call_id}'"/>
                        <param name="user_input" expr="'yes'"/>
                    </submit>
                <else/>
                    <prompt>Thank you for calling Air India. Goodbye!</prompt>
                    <disconnect/>
                </if>
            </filled>
        </field>
    </form>
</vxml>"""
        
        logger.info(f"Generated confirmation VXML for {call_id}")
        return vxml
    
    def generate_dtmf_menu_vxml(
        self, 
        call_id: str, 
        prompt: str,
        options: Dict[str, str]
    ) -> str:
        """
        Generate VXML with DTMF (keypad) menu
        
        Args:
            call_id: Call identifier
            prompt: Menu prompt text
            options: Dict of {digit: action} pairs
            
        Returns:
            VXML string
        """
        prompt = self._escape_xml(prompt)
        
        # Build options text
        options_text = ". ".join([f"Press {digit} for {action}" for digit, action in options.items()])
        full_prompt = f"{prompt}. {options_text}"
        
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="dtmf_menu">
        <field name="digit_choice" type="digits?length=1">
            <prompt>{full_prompt}</prompt>
            
            <filled>
                <submit 
                    next="{self.base_url}/ivr/user-input" 
                    method="post" 
                    enctype="application/json">
                    <param name="call_id" expr="'{call_id}'"/>
                    <param name="user_input" expr="digit_choice"/>
                    <param name="input_type" expr="'dtmf'"/>
                </submit>
            </filled>
            
            <noinput>
                <prompt>I didn't receive any input. {options_text}</prompt>
                <reprompt/>
            </noinput>
        </field>
    </form>
</vxml>"""
        
        logger.info(f"Generated DTMF menu VXML for {call_id}")
        return vxml
    
    def generate_error_vxml(self, error_message: str = "Sorry, we're experiencing technical difficulties") -> str:
        """
        Generate error VXML
        
        Args:
            error_message: Custom error message
            
        Returns:
            VXML string
        """
        error_message = self._escape_xml(error_message)
        
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="error">
        <block>
            <prompt>
                {error_message}. 
                Please try again later or press 0 to speak with an agent.
            </prompt>
            <disconnect/>
        </block>
    </form>
</vxml>"""
        
        logger.error(f"Generated error VXML: {error_message}")
        return vxml
    
    def generate_collect_info_vxml(
        self, 
        call_id: str,
        field_name: str,
        prompt: str,
        field_type: str = "text"
    ) -> str:
        """
        Generate VXML to collect specific information
        
        Args:
            call_id: Call identifier
            field_name: Name of field to collect (e.g., "origin", "date")
            prompt: What to ask the user
            field_type: Type of data (text, date, number, etc.)
            
        Returns:
            VXML string
        """
        prompt = self._escape_xml(prompt)
        
        grammar_map = {
            "text": """<grammar type="application/srgs+xml" mode="voice">
                <![CDATA[
                #JSGF V1.0;
                grammar text;
                public <text> = <word>+;
                ]]>
            </grammar>""",
            "date": """<grammar type="application/srgs+xml" mode="voice">
                <![CDATA[
                #JSGF V1.0;
                grammar date;
                public <date> = <month> <day> | <day> <month>;
                <month> = january | february | march | april | may | june | july | august | september | october | november | december;
                <day> = 1..31;
                ]]>
            </grammar>""",
            "number": """<grammar type="application/srgs+xml" mode="voice">
                <![CDATA[
                #JSGF V1.0;
                grammar number;
                public <number> = <digit>+;
                <digit> = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
                ]]>
            </grammar>"""
        }
        
        grammar = grammar_map.get(field_type, grammar_map["text"])
        
        vxml = f"""<?xml version="1.0" encoding="UTF-8"?>
<vxml version="2.1">
    <form id="collect_{field_name}">
        <field name="{field_name}">
            <prompt>{prompt}</prompt>
            {grammar}
            
            <filled>
                <submit 
                    next="{self.base_url}/ivr/user-input" 
                    method="post" 
                    enctype="application/json">
                    <param name="call_id" expr="'{call_id}'"/>
                    <param name="field_name" expr="'{field_name}'"/>
                    <param name="user_input" expr="{field_name}"/>
                </submit>
            </filled>
            
            <noinput>
                <prompt>I didn't catch that. {prompt}</prompt>
                <reprompt/>
            </noinput>
        </field>
    </form>
</vxml>"""
        
        logger.info(f"Generated info collection VXML for {field_name}")
        return vxml
    
    def _escape_xml(self, text: str) -> str:
        """
        Escape special XML characters
        
        Args:
            text: Input text
            
        Returns:
            XML-safe text
        """
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&apos;'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text