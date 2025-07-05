"""
AsyncConversationManager for non-recursive async conversation handling.

This module provides the AsyncConversationManager class that enables memory-efficient
async conversations by using an event loop instead of recursive method calls.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Union

from .agent import Agent

logger = logging.getLogger(__name__)


class AsyncConversationManager:
    """Manages async conversation flow without recursion.

    This class implements an event-driven async conversation loop that eliminates
    the memory growth issues caused by recursive a_send() -> a_receive() -> a_send() calls.
    """

    def __init__(self, initiator, recipient):
        """Initialize async conversation manager.

        Args:
            initiator: The agent that starts the conversation
            recipient: The agent that receives the initial message
        """
        self.initiator = initiator
        self.recipient = recipient
        self.participants = [initiator, recipient]
        self.conversation_active = True
        self.message_count = 0

    async def run_conversation(self, initial_message: Union[str, Dict], silent: bool = False) -> None:
        """Run the async conversation loop without recursion.

        Args:
            initial_message: The message to start the conversation
            silent: Whether to suppress output during conversation
        """
        logger.debug(
            f"Starting non-recursive async conversation between {self.initiator.name} and {self.recipient.name}"
        )

        # Initialize conversation state
        current_message = initial_message
        current_sender = self.initiator
        current_recipient = self.recipient

        # Send the initial message
        await current_sender._a_send_v2(current_message, current_recipient, silent=silent)
        self.message_count += 1

        # Main async conversation loop - no recursion
        while self.conversation_active:
            # Switch roles: recipient becomes sender
            current_sender, current_recipient = current_recipient, current_sender

            # Process the received message and generate reply
            should_continue, reply = await current_sender._a_process_and_reply_v2(
                current_message, current_recipient, silent=silent
            )

            # Check if conversation should terminate
            if not should_continue or reply is None:
                logger.debug(f"Async conversation terminated after {self.message_count} messages")
                break

            # Send the reply
            await current_sender._a_send_v2(reply, current_recipient, silent=silent)
            current_message = reply
            self.message_count += 1

        logger.debug(f"Async conversation completed with {self.message_count} total messages")

    def get_conversation_stats(self) -> Dict[str, Union[int, str]]:
        """Get statistics about the async conversation.

        Returns:
            Dictionary with conversation statistics
        """
        return {
            "message_count": self.message_count,
            "initiator": self.initiator.name,
            "recipient": self.recipient.name,
            "active": self.conversation_active,
        }


class AsyncGroupConversationManager:
    """Manages async group conversation flow without recursion.

    This class implements an event-driven async group conversation loop that eliminates
    the memory growth issues caused by recursive async method calls in group chat scenarios.
    """

    def __init__(self, groupchat, manager_agent):
        """Initialize async group conversation manager.

        Args:
            groupchat: The GroupChat configuration object
            manager_agent: The GroupChatManager agent that coordinates the conversation
        """
        self.groupchat = groupchat
        self.manager_agent = manager_agent
        self.conversation_active = True
        self.message_count = 0
        self.current_round = 0

    async def run_group_conversation(
        self, initial_message: Union[str, Dict], initial_speaker: Agent, silent: bool = False
    ) -> None:
        """Run the async group conversation loop without recursion.

        Args:
            initial_message: The message to start the conversation
            initial_speaker: The agent that sends the initial message
            silent: Whether to suppress output during conversation
        """
        logger.debug(f"Starting non-recursive async group conversation with {len(self.groupchat.agents)} agents")

        # Initialize conversation state
        current_message = initial_message
        current_speaker = initial_speaker

        # Main async group conversation loop - no recursion
        for round_num in range(self.groupchat.max_round):
            self.current_round = round_num

            # Add message to group chat history
            self.groupchat.append(current_message, current_speaker)
            self.message_count += 1

            # Check for termination
            if self.manager_agent._is_termination_msg(current_message):
                logger.debug(
                    f"Async group conversation terminated by termination message after {self.message_count} messages"
                )
                break

            # Broadcast message to all agents except the speaker (non-recursive)
            await self._a_broadcast_message_v2(current_message, current_speaker, silent=silent)

            # Check if this is the last round
            if round_num == self.groupchat.max_round - 1:
                logger.debug(f"Async group conversation reached max rounds ({self.groupchat.max_round})")
                break

            try:
                # Select next speaker using existing async GroupChat logic
                next_speaker = await self.groupchat.a_select_speaker(current_speaker, self.manager_agent)

                # Generate reply from next speaker (non-recursive)
                should_continue, reply = await self._a_generate_speaker_reply_v2(
                    next_speaker, current_message, silent=silent
                )

                if not should_continue or reply is None:
                    logger.debug(
                        f"Async group conversation terminated by speaker decision after {self.message_count} messages"
                    )
                    break

                # Update for next iteration
                current_speaker = next_speaker
                current_message = reply

            except KeyboardInterrupt:
                # Handle admin intervention (same as original async GroupChatManager)
                if self.groupchat.admin_name in self.groupchat.agent_names:
                    admin_agent = self.groupchat.agent_by_name(self.groupchat.admin_name)
                    should_continue, reply = await self._a_generate_speaker_reply_v2(
                        admin_agent, current_message, silent=silent
                    )
                    if should_continue and reply is not None:
                        current_speaker = admin_agent
                        current_message = reply
                    else:
                        break
                else:
                    raise

        logger.debug(
            f"Async group conversation completed with {self.message_count} total messages in {self.current_round + 1} rounds"
        )

    async def _a_broadcast_message_v2(self, message: Union[str, Dict], speaker: Agent, silent: bool = False) -> None:
        """Broadcast message to all agents except the speaker (async non-recursive version).

        Args:
            message: The message to broadcast
            speaker: The agent who sent the message (excluded from broadcast)
            silent: Whether to suppress output
        """
        # Use asyncio.gather for concurrent message broadcasting
        broadcast_tasks = []
        for agent in self.groupchat.agents:
            if agent != speaker:
                # Use the manager agent's _a_send_v2 method to avoid recursion
                task = self.manager_agent._a_send_v2(message, agent, request_reply=False, silent=True)
                broadcast_tasks.append(task)

        if broadcast_tasks:
            await asyncio.gather(*broadcast_tasks)

    async def _a_generate_speaker_reply_v2(
        self, speaker: Agent, last_message: Union[str, Dict], silent: bool = False
    ) -> Tuple[bool, Optional[Union[str, Dict]]]:
        """Generate reply from a speaker without recursion (async version).

        Args:
            speaker: The agent to generate a reply
            last_message: The last message in the conversation
            silent: Whether to suppress output

        Returns:
            Tuple of (should_continue, reply)
        """
        try:
            # Generate reply using the speaker's existing async generate_reply method
            reply = await speaker.a_generate_reply(sender=self.manager_agent)

            if reply is None:
                return False, None

            # Check if the reply indicates conversation should continue
            should_continue = True
            if hasattr(speaker, "_is_termination_msg") and speaker._is_termination_msg(reply):
                should_continue = False

            return should_continue, reply

        except Exception as e:
            logger.error(f"Error generating async reply from {speaker.name}: {e}")
            return False, None

    def get_conversation_stats(self) -> Dict[str, Union[int, str, List[str]]]:
        """Get statistics about the async group conversation.

        Returns:
            Dictionary with conversation statistics
        """
        return {
            "message_count": self.message_count,
            "current_round": self.current_round,
            "max_rounds": self.groupchat.max_round,
            "agent_count": len(self.groupchat.agents),
            "agent_names": [agent.name for agent in self.groupchat.agents],
            "active": self.conversation_active,
        }
