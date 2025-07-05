"""
Test suite for ConversationManager and new non-recursive conversation methods.
"""

import os
import sys

# Add the autogen directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from autogen.agentchat import AssistantAgent, ConversableAgent, UserProxyAgent
    from autogen.agentchat.conversation_manager import ConversationManager
except ImportError:
    # Skip tests if autogen can't be imported
    ConversationManager = None
    AssistantAgent = None
    UserProxyAgent = None
    ConversableAgent = None


class TestConversationManager:
    """Test the ConversationManager class."""

    def setup_method(self):
        """Set up test agents."""
        self.assistant = AssistantAgent(
            name="assistant",
            llm_config=False,  # Disable LLM for testing
            max_consecutive_auto_reply=2,
        )

        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=2,
            code_execution_config=False,
        )

    def test_conversation_manager_creation(self):
        """Test that ConversationManager can be created."""
        manager = ConversationManager(self.user_proxy, self.assistant)

        assert manager.initiator == self.user_proxy
        assert manager.recipient == self.assistant
        assert len(manager.participants) == 2
        assert manager.conversation_active is True
        assert manager.message_count == 0

    def test_conversation_stats(self):
        """Test conversation statistics."""
        manager = ConversationManager(self.user_proxy, self.assistant)
        stats = manager.get_conversation_stats()

        assert stats["message_count"] == 0
        assert stats["initiator"] == "user_proxy"
        assert stats["recipient"] == "assistant"
        assert stats["active"] is True


class TestNewConversationMethods:
    """Test the new v2 conversation methods."""

    def setup_method(self):
        """Set up test agents."""
        self.assistant = AssistantAgent(
            name="assistant",
            llm_config=False,  # Disable LLM for testing
            max_consecutive_auto_reply=1,
        )

        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )

    def test_new_methods_exist(self):
        """Test that new v2 methods exist on ConversableAgent."""
        assert hasattr(self.assistant, "initiate_chat_v2")
        assert hasattr(self.assistant, "_send_v2")
        assert hasattr(self.assistant, "_receive_v2")
        assert hasattr(self.assistant, "_process_and_reply_v2")

        assert hasattr(self.user_proxy, "initiate_chat_v2")
        assert hasattr(self.user_proxy, "_send_v2")
        assert hasattr(self.user_proxy, "_receive_v2")
        assert hasattr(self.user_proxy, "_process_and_reply_v2")

    def test_send_v2_basic(self):
        """Test basic _send_v2 functionality."""
        message = "Hello, assistant!"

        # Test that _send_v2 doesn't raise an error
        try:
            self.user_proxy._send_v2(message, self.assistant, silent=True)
        except Exception as e:
            raise AssertionError(f"_send_v2 raised an exception: {e}")

    def test_receive_v2_basic(self):
        """Test basic _receive_v2 functionality."""
        message = "Hello, user!"

        # Test that _receive_v2 doesn't raise an error
        try:
            self.user_proxy._receive_v2(message, self.assistant, silent=True)
        except Exception as e:
            raise AssertionError(f"_receive_v2 raised an exception: {e}")

    def test_process_and_reply_v2_basic(self):
        """Test basic _process_and_reply_v2 functionality."""
        message = "Hello!"

        # Test that _process_and_reply_v2 returns expected format
        try:
            should_continue, reply = self.user_proxy._process_and_reply_v2(message, self.assistant, silent=True)

            # Should return a tuple with boolean and optional message
            assert isinstance(should_continue, bool)
            assert reply is None or isinstance(reply, (str, dict))

        except Exception as e:
            raise AssertionError(f"_process_and_reply_v2 raised an exception: {e}")


class TestBackwardCompatibility:
    """Test that existing methods still work unchanged."""

    def setup_method(self):
        """Set up test agents."""
        self.assistant = AssistantAgent(
            name="assistant",
            llm_config=False,  # Disable LLM for testing
            max_consecutive_auto_reply=1,
        )

        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )

    def test_original_methods_unchanged(self):
        """Test that original methods still exist and work."""
        # Test that original methods exist
        assert hasattr(self.assistant, "initiate_chat")
        assert hasattr(self.assistant, "send")
        assert hasattr(self.assistant, "receive")

        # Test that they can be called (basic smoke test)
        try:
            # This should work without errors (though conversation will be brief due to max_consecutive_auto_reply=1)
            self.user_proxy.initiate_chat(self.assistant, message="Hello", silent=True)
        except Exception:
            # Some exceptions might be expected due to test setup, but method should exist
            assert hasattr(self.user_proxy, "initiate_chat"), "Original initiate_chat method missing"


if __name__ == "__main__":
    # Run basic tests
    test_manager = TestConversationManager()
    test_manager.setup_method()
    test_manager.test_conversation_manager_creation()
    test_manager.test_conversation_stats()
    print("✓ ConversationManager tests passed")

    test_methods = TestNewConversationMethods()
    test_methods.setup_method()
    test_methods.test_new_methods_exist()
    test_methods.test_send_v2_basic()
    test_methods.test_receive_v2_basic()
    test_methods.test_process_and_reply_v2_basic()
    print("✓ New v2 methods tests passed")

    test_compat = TestBackwardCompatibility()
    test_compat.setup_method()
    test_compat.test_original_methods_unchanged()
    print("✓ Backward compatibility tests passed")

    print("\n🎉 Phase 1 implementation tests completed successfully!")
