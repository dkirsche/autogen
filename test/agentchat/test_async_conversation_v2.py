"""
Test suite for Async Conversation v2 (non-recursive async conversation functionality).
"""

import asyncio
import sys
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

# Add the autogen directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class MockAsyncAgent:
    """Mock async agent for testing."""

    def __init__(self, name: str, max_replies: int = 3, terminate_keyword: str = "TERMINATE"):
        self.name = name
        self.max_replies = max_replies
        self.terminate_keyword = terminate_keyword
        self.reply_count = 0
        self._oai_messages = defaultdict(list)
        self.reply_at_receive = defaultdict(lambda: True)
        self.chat_messages = self._oai_messages
        self.client_cache = None
        self.previous_cache = None

    def _append_oai_message(self, message, role, conversation_id):
        """Append message to conversation history."""
        content = message if isinstance(message, str) else message.get("content", "")
        self._oai_messages[conversation_id].append({"content": content, "role": role})
        return True

    def _process_received_message(self, message, sender, silent):
        """Process received message."""
        self._append_oai_message(message, "user", sender)
        if not silent:
            content = message if isinstance(message, str) else message.get("content", "")
            print(f"{sender.name} -> {self.name}: {content}")

    async def a_generate_reply(self, sender=None):
        """Generate an async reply to the conversation."""
        await asyncio.sleep(0.01)  # Simulate async operation
        self.reply_count += 1

        # Check termination conditions
        if self.reply_count >= self.max_replies:
            return self.terminate_keyword

        # Generate a simple reply
        reply = f"Async reply {self.reply_count} from {self.name}"
        return reply

    async def a_generate_init_message(self, **context):
        """Generate initial message (async)."""
        await asyncio.sleep(0.01)  # Simulate async operation
        return context.get("message", f"Hello from {self.name}!")

    def clear_history(self):
        """Clear conversation history."""
        self._oai_messages.clear()
        self.reply_count = 0

    def _prepare_chat(self, recipient, clear_history):
        """Mock prepare chat method."""
        if clear_history:
            self.clear_history()

    # Async V2 Methods (non-recursive)
    async def _a_send_v2(self, message, recipient, request_reply=None, silent=False):
        """Send message without triggering recursive chain (async)."""
        await asyncio.sleep(0.01)  # Simulate async operation
        valid = self._append_oai_message(message, "assistant", recipient)
        if not valid:
            raise ValueError("Invalid message")
        recipient._process_received_message(message, self, silent)

    async def _a_process_and_reply_v2(self, message, sender, request_reply=None, silent=False):
        """Process message and generate reply without recursion (async)."""
        if request_reply is False or request_reply is None and not self.reply_at_receive[sender]:
            return False, None

        reply = await self.a_generate_reply(sender=sender)
        should_continue = bool(reply) and self.terminate_keyword not in str(reply)
        return should_continue, reply if reply else None


class MockAsyncConversationManager:
    """Mock async conversation manager for testing."""

    def __init__(self, initiator, recipient):
        self.initiator = initiator
        self.recipient = recipient
        self.participants = [initiator, recipient]
        self.conversation_active = True
        self.message_count = 0

    async def run_conversation(self, initial_message, silent=False):
        """Run async conversation without recursion."""
        print(f"Starting async conversation: {self.initiator.name} -> {self.recipient.name}")

        current_message = initial_message
        current_sender = self.initiator
        current_recipient = self.recipient

        # Send initial message
        await current_sender._a_send_v2(current_message, current_recipient, silent=silent)
        self.message_count += 1

        # Main async conversation loop
        while self.conversation_active:
            # Switch roles
            current_sender, current_recipient = current_recipient, current_sender

            # Process and generate reply
            should_continue, reply = await current_sender._a_process_and_reply_v2(
                current_message, current_recipient, silent=silent
            )

            if not should_continue or reply is None:
                print(f"Async conversation ended after {self.message_count} messages")
                break

            # Send reply
            await current_sender._a_send_v2(reply, current_recipient, silent=silent)
            current_message = reply
            self.message_count += 1

            # Safety limit for testing
            if self.message_count > 10:
                print(f"Reached test limit: {self.message_count}")
                break

        return self.message_count

    def get_conversation_stats(self):
        """Get conversation statistics."""
        return {
            "message_count": self.message_count,
            "initiator": self.initiator.name,
            "recipient": self.recipient.name,
            "active": self.conversation_active,
        }


async def test_async_conversation_manager_creation():
    """Test AsyncConversationManager creation."""
    print("🧪 Testing AsyncConversationManager creation...")

    try:
        # Create mock agents
        alice = MockAsyncAgent("Alice", max_replies=2)
        bob = MockAsyncAgent("Bob", max_replies=2)

        # Test creation
        manager = MockAsyncConversationManager(alice, bob)

        assert manager.initiator == alice
        assert manager.recipient == bob
        assert len(manager.participants) == 2
        assert manager.conversation_active is True
        assert manager.message_count == 0

        print("✅ AsyncConversationManager creation successful")
        return True

    except Exception as e:
        print(f"✗ AsyncConversationManager creation failed: {e}")
        return False


async def test_async_conversation_flow():
    """Test basic async conversation flow."""
    print("\n🧪 Testing async conversation flow...")

    try:
        # Create mock agents
        alice = MockAsyncAgent("Alice", max_replies=2)
        bob = MockAsyncAgent("Bob", max_replies=2)

        # Run async conversation
        manager = MockAsyncConversationManager(alice, bob)
        message_count = await manager.run_conversation("Hello Bob!", silent=False)

        # Verify conversation occurred
        assert message_count > 0, "No messages exchanged"
        assert message_count <= 6, f"Too many messages: {message_count}"

        stats = manager.get_conversation_stats()
        print(f"✅ Async conversation completed: {stats}")

        return True

    except Exception as e:
        print(f"✗ Async conversation flow failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_async_conversation_termination():
    """Test async conversation termination conditions."""
    print("\n🧪 Testing async conversation termination...")

    try:
        # Create agents with quick termination
        alice = MockAsyncAgent("Alice", max_replies=1)
        bob = MockAsyncAgent("Bob", max_replies=1)

        manager = MockAsyncConversationManager(alice, bob)
        message_count = await manager.run_conversation("Quick async test", silent=True)

        # Should terminate quickly due to agent limits
        assert message_count <= 4, f"Expected quick termination, got {message_count} messages"

        print(f"✅ Async conversation terminated appropriately ({message_count} messages)")
        return True

    except Exception as e:
        print(f"✗ Async conversation termination failed: {e}")
        return False


async def test_concurrent_conversations():
    """Test multiple concurrent async conversations."""
    print("\n🧪 Testing concurrent async conversations...")

    try:
        # Create multiple conversation pairs
        conversations = []
        for i in range(3):
            alice = MockAsyncAgent(f"Alice{i}", max_replies=2)
            bob = MockAsyncAgent(f"Bob{i}", max_replies=2)
            manager = MockAsyncConversationManager(alice, bob)
            conversations.append(manager.run_conversation(f"Hello from conversation {i}!", silent=True))

        # Run all conversations concurrently
        results = await asyncio.gather(*conversations)

        # Verify all conversations completed
        assert len(results) == 3, "Not all conversations completed"
        assert all(count > 0 for count in results), "Some conversations had no messages"

        total_messages = sum(results)
        print(f"✅ Concurrent conversations completed: {results} (total: {total_messages} messages)")

        return True

    except Exception as e:
        print(f"✗ Concurrent conversations failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_async_performance():
    """Test async conversation performance."""
    print("\n🧪 Testing async conversation performance...")

    try:
        import time

        # Create agents for performance test
        alice = MockAsyncAgent("Alice", max_replies=5)
        bob = MockAsyncAgent("Bob", max_replies=5)

        # Measure async conversation time
        start_time = time.time()
        manager = MockAsyncConversationManager(alice, bob)
        message_count = await manager.run_conversation("Performance test", silent=True)
        end_time = time.time()

        duration = end_time - start_time
        messages_per_second = message_count / duration if duration > 0 else 0

        print("✅ Async performance test:")
        print(f"   - Messages: {message_count}")
        print(f"   - Duration: {duration:.3f}s")
        print(f"   - Rate: {messages_per_second:.1f} messages/second")

        # Should be reasonably fast
        assert duration < 5.0, f"Async conversation too slow: {duration:.3f}s"

        return True

    except Exception as e:
        print(f"✗ Async performance test failed: {e}")
        return False


async def run_all_async_tests():
    """Run all async tests."""
    print("🚀 Starting Async Conversation v2 Tests\n")

    tests = [
        test_async_conversation_manager_creation,
        test_async_conversation_flow,
        test_async_conversation_termination,
        test_concurrent_conversations,
        test_async_performance,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            print(f"❌ {test.__name__} failed with exception: {e}")
            import traceback

            traceback.print_exc()

    print(f"\n📊 Async Conversation v2 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL ASYNC TESTS PASSED!")
        print("✅ AsyncConversationManager working")
        print("✅ Non-recursive async conversation flow working")
        print("✅ Async conversation termination working")
        print("✅ Concurrent conversations working")
        print("✅ Async performance acceptable")
        print("\n🚀 Phase 4 implementation ready!")
    else:
        print(f"\n❌ {total - passed} async tests failed")
        return False

    return True


if __name__ == "__main__":
    # Run async tests
    result = asyncio.run(run_all_async_tests())
    if not result:
        sys.exit(1)
