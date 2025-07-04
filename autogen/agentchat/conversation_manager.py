"""
ConversationManager for non-recursive conversation handling.

This module provides the ConversationManager class that enables memory-efficient
conversations by using an event loop instead of recursive method calls.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union

from .agent import Agent

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation flow without recursion.

    This class implements an event-driven conversation loop that eliminates
    the memory growth issues caused by recursive send() -> receive() -> send() calls.
    """

    def __init__(self, initiator, recipient):
        """Initialize conversation manager.

        Args:
            initiator: The agent that starts the conversation
            recipient: The agent that receives the initial message
        """
        self.initiator = initiator
        self.recipient = recipient
        self.participants = [initiator, recipient]
        self.conversation_active = True
        self.message_count = 0

    def run_conversation(self, initial_message: Union[str, Dict], silent: bool = False) -> None:
        """Run the conversation loop without recursion.

        Args:
            initial_message: The message to start the conversation
            silent: Whether to suppress output during conversation
        """
        logger.debug(f"Starting non-recursive conversation between {self.initiator.name} and {self.recipient.name}")

        # Initialize conversation state
        current_message = initial_message
        current_sender = self.initiator
        current_recipient = self.recipient

        # Send the initial message
        current_sender._send_v2(current_message, current_recipient, silent=silent)
        self.message_count += 1

        # Main conversation loop - no recursion
        while self.conversation_active:
            # Switch roles: recipient becomes sender
            current_sender, current_recipient = current_recipient, current_sender

            # Process the received message and generate reply
            should_continue, reply = current_sender._process_and_reply_v2(
                current_message, current_recipient, silent=silent
            )

            # Check if conversation should terminate
            if not should_continue or reply is None:
                logger.debug(f"Conversation terminated after {self.message_count} messages")
                break

            # Send the reply
            current_sender._send_v2(reply, current_recipient, silent=silent)
            current_message = reply
            self.message_count += 1

        logger.debug(f"Conversation completed with {self.message_count} total messages")

    def get_conversation_stats(self) -> Dict[str, Union[int, str]]:
        """Get statistics about the conversation.

        Returns:
            Dictionary with conversation statistics
        """
        return {
            "message_count": self.message_count,
            "initiator": self.initiator.name,
            "recipient": self.recipient.name,
            "active": self.conversation_active,
        }
