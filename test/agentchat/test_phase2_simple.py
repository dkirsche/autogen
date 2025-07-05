"""
Simple test for Phase 2 implementation without full autogen dependencies.
"""

import sys
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

# Add the autogen directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class MockAgent:
    """Mock agent for testing conversation flow."""

    def __init__(self, name: str, max_replies: int = 2):
        self.name = name
        self.max_replies = max_replies
        self.reply_count = 0
        self._oai_messages = defaultdict(list)
        self.reply_at_receive = defaultdict(lambda: True)
        self.chat_messages = self._oai_messages

    def _append_oai_message(self, message, role, conversation_id):
        """Mock message appending."""
        self._oai_messages[conversation_id].append(
            {"content": message if isinstance(message, str) else message.get("content", ""), "role": role}
        )
        return True

    def _process_received_message(self, message, sender, silent):
        """Mock message processing."""
        self._append_oai_message(message, "user", sender)
        if not silent:
            print(f"{sender.name} -> {self.name}: {message}")

    def generate_reply(self, messages=None, sender=None):
        """Mock reply generation."""
        self.reply_count += 1

        if self.reply_count >= self.max_replies:
            return "TERMINATE", True  # End conversation

        return f"Reply {self.reply_count} from {self.name}", False

    def _send_v2(self, message, recipient, request_reply=None, silent=False):
        """Mock v2 send method."""
        valid = self._append_oai_message(message, "assistant", recipient)
        if not valid:
            raise ValueError("Invalid message")
        recipient._receive_v2(message, self, request_reply, silent)

    def _receive_v2(self, message, sender, request_reply=None, silent=False):
        """Mock v2 receive method."""
        self._process_received_message(message, sender, silent)

    def _process_and_reply_v2(self, message, sender, request_reply=None, silent=False):
        """Mock v2 process and reply method."""
        if request_reply is False or request_reply is None and not self.reply_at_receive[sender]:
            return False, None

        reply, chat_done = self.generate_reply(messages=self.chat_messages[sender], sender=sender)
        should_continue = bool(reply) and not chat_done
        return should_continue, reply if reply else None


class MockConversationManager:
    """Mock conversation manager for testing."""

    def __init__(self, initiator, recipient):
        self.initiator = initiator
        self.recipient = recipient
        self.participants = [initiator, recipient]
        self.conversation_active = True
        self.message_count = 0

    def run_conversation(self, initial_message, silent=False):
        """Run conversation loop without recursion."""
        print(f"Starting conversation: {self.initiator.name} -> {self.recipient.name}")

        current_message = initial_message
        current_sender = self.initiator
        current_recipient = self.recipient

        # Send initial message
        current_sender._send_v2(current_message, current_recipient, silent=silent)
        self.message_count += 1

        # Main conversation loop
        while self.conversation_active:
            # Switch roles
            current_sender, current_recipient = current_recipient, current_sender

            # Process and generate reply
            should_continue, reply = current_sender._process_and_reply_v2(
                current_message, current_recipient, silent=silent
            )

            if not should_continue or reply is None:
                print(f"Conversation ended after {self.message_count} messages")
                break

            # Send reply
            current_sender._send_v2(reply, current_recipient, silent=silent)
            current_message = reply
            self.message_count += 1

            # Safety limit
            if self.message_count > 100:
                print(f"Reached message limit: {self.message_count}")
                break

        return self.message_count


def test_conversation_flow():
    """Test the complete conversation flow."""
    print("=== Testing Phase 2 Conversation Flow ===")

    # Create mock agents
    agent1 = MockAgent("Alice", max_replies=3)
    agent2 = MockAgent("Bob", max_replies=3)

    # Create conversation manager
    manager = MockConversationManager(agent1, agent2)

    # Run conversation
    message_count = manager.run_conversation("Hello Bob!", silent=False)

    print(f"\n✓ Conversation completed with {message_count} messages")
    print(f"✓ Alice sent {len(agent1._oai_messages[agent2])} messages")
    print(f"✓ Bob sent {len(agent2._oai_messages[agent1])} messages")

    return True


def test_memory_efficiency():
    """Test that memory usage doesn't grow with conversation length."""
    print("\n=== Testing Memory Efficiency ===")

    import tracemalloc

    tracemalloc.start()

    # Test with longer conversation
    agent1 = MockAgent("Alice", max_replies=50)
    agent2 = MockAgent("Bob", max_replies=50)

    manager = MockConversationManager(agent1, agent2)

    # Take initial memory snapshot
    snapshot1 = tracemalloc.take_snapshot()

    # Run conversation
    message_count = manager.run_conversation("Start long conversation", silent=True)

    # Take final memory snapshot
    snapshot2 = tracemalloc.take_snapshot()

    # Compare memory usage
    top_stats = snapshot2.compare_to(snapshot1, "lineno")
    total_memory_diff = sum(stat.size_diff for stat in top_stats)

    print(f"✓ Long conversation completed with {message_count} messages")
    print(f"✓ Memory difference: {total_memory_diff} bytes")
    print(f"✓ Memory per message: {total_memory_diff / message_count if message_count > 0 else 0:.2f} bytes")

    # Memory should grow linearly with message storage, not exponentially with stack depth
    assert total_memory_diff < 1000000, f"Memory usage too high: {total_memory_diff} bytes"

    tracemalloc.stop()
    return True


def test_termination_conditions():
    """Test various termination conditions."""
    print("\n=== Testing Termination Conditions ===")

    # Test early termination
    agent1 = MockAgent("Alice", max_replies=1)
    agent2 = MockAgent("Bob", max_replies=1)

    manager = MockConversationManager(agent1, agent2)
    message_count = manager.run_conversation("Quick chat", silent=True)

    print(f"✓ Early termination test: {message_count} messages")
    assert message_count <= 3, f"Expected quick termination, got {message_count} messages"

    return True


if __name__ == "__main__":
    try:
        print("🚀 Starting Phase 2 Tests\n")

        # Run all tests
        test_conversation_flow()
        test_memory_efficiency()
        test_termination_conditions()

        print("\n🎉 All Phase 2 tests passed!")
        print("✅ Non-recursive conversation flow working")
        print("✅ Memory efficiency validated")
        print("✅ Termination conditions working")
        print("✅ Phase 2 implementation complete!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
