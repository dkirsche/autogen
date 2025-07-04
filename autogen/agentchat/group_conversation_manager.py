"""
GroupConversationManager for non-recursive group chat handling.

This module provides the GroupConversationManager class that enables memory-efficient
group conversations by using an event loop instead of recursive method calls.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union

from .agent import Agent
from .groupchat import GroupChat

logger = logging.getLogger(__name__)


class GroupConversationManager:
    """Manages group conversation flow without recursion.

    This class implements an event-driven group conversation loop that eliminates
    the memory growth issues caused by recursive send() -> receive() -> send() calls
    in group chat scenarios.
    """

    def __init__(self, groupchat: GroupChat, manager_agent):
        """Initialize group conversation manager.

        Args:
            groupchat: The GroupChat configuration object
            manager_agent: The GroupChatManager agent that coordinates the conversation
        """
        self.groupchat = groupchat
        self.manager_agent = manager_agent
        self.conversation_active = True
        self.message_count = 0
        self.current_round = 0

    def run_group_conversation(
        self, initial_message: Union[str, Dict], initial_speaker: Agent, silent: bool = False
    ) -> None:
        """Run the group conversation loop without recursion.

        Args:
            initial_message: The message to start the conversation
            initial_speaker: The agent that sends the initial message
            silent: Whether to suppress output during conversation
        """
        logger.debug(f"Starting non-recursive group conversation with {len(self.groupchat.agents)} agents")

        # Initialize conversation state
        current_message = initial_message
        current_speaker = initial_speaker

        # Main group conversation loop - no recursion
        for round_num in range(self.groupchat.max_round):
            self.current_round = round_num

            # Add message to group chat history
            self.groupchat.append(current_message, current_speaker)
            self.message_count += 1

            # Check for termination
            if self.manager_agent._is_termination_msg(current_message):
                logger.debug(
                    f"Group conversation terminated by termination message after {self.message_count} messages"
                )
                break

            # Broadcast message to all agents except the speaker (non-recursive)
            self._broadcast_message_v2(current_message, current_speaker, silent=silent)

            # Check if this is the last round
            if round_num == self.groupchat.max_round - 1:
                logger.debug(f"Group conversation reached max rounds ({self.groupchat.max_round})")
                break

            try:
                # Select next speaker using existing GroupChat logic
                next_speaker = self.groupchat.select_speaker(current_speaker, self.manager_agent)

                # Generate reply from next speaker (non-recursive)
                should_continue, reply = self._generate_speaker_reply_v2(next_speaker, current_message, silent=silent)

                if not should_continue or reply is None:
                    logger.debug(
                        f"Group conversation terminated by speaker decision after {self.message_count} messages"
                    )
                    break

                # Update for next iteration
                current_speaker = next_speaker
                current_message = reply

            except KeyboardInterrupt:
                # Handle admin intervention (same as original GroupChatManager)
                if self.groupchat.admin_name in self.groupchat.agent_names:
                    admin_agent = self.groupchat.agent_by_name(self.groupchat.admin_name)
                    should_continue, reply = self._generate_speaker_reply_v2(
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
            f"Group conversation completed with {self.message_count} total messages in {self.current_round + 1} rounds"
        )

    def _broadcast_message_v2(self, message: Union[str, Dict], speaker: Agent, silent: bool = False) -> None:
        """Broadcast message to all agents except the speaker (non-recursive version).

        Args:
            message: The message to broadcast
            speaker: The agent who sent the message (excluded from broadcast)
            silent: Whether to suppress output
        """
        for agent in self.groupchat.agents:
            if agent != speaker:
                # Use the manager agent's _send_v2 method to avoid recursion
                self.manager_agent._send_v2(message, agent, request_reply=False, silent=True)

    def _generate_speaker_reply_v2(
        self, speaker: Agent, last_message: Union[str, Dict], silent: bool = False
    ) -> Tuple[bool, Optional[Union[str, Dict]]]:
        """Generate reply from a speaker without recursion.

        Args:
            speaker: The agent to generate a reply
            last_message: The last message in the conversation
            silent: Whether to suppress output

        Returns:
            Tuple of (should_continue, reply)
        """
        try:
            # Generate reply using the speaker's existing generate_reply method
            reply = speaker.generate_reply(sender=self.manager_agent)

            if reply is None:
                return False, None

            # Check if the reply indicates conversation should continue
            should_continue = True
            if hasattr(speaker, "_is_termination_msg") and speaker._is_termination_msg(reply):
                should_continue = False

            return should_continue, reply

        except Exception as e:
            logger.error(f"Error generating reply from {speaker.name}: {e}")
            return False, None

    def get_conversation_stats(self) -> Dict[str, Union[int, str, List[str]]]:
        """Get statistics about the group conversation.

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
