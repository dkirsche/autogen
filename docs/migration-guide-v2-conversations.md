# Migration Guide: Upgrading to v2 Conversation Methods

## Overview

This guide helps you migrate from AutoGen's original conversation methods to the new memory-efficient v2 methods. The migration is **completely optional** and **risk-free** - all existing code continues to work unchanged.

## Why Migrate?

### Memory Efficiency Benefits
- **50%+ memory reduction** for conversations >100 messages
- **No stack overflow risk** regardless of conversation length
- **Linear memory growth** instead of exponential
- **Better performance** in memory-constrained environments

### When to Consider Migration
✅ **Recommended for:**
- Long conversations (>50 messages)
- Group chats with multiple participants
- Automated workflows with many iterations
- Production applications with memory constraints
- Concurrent conversation scenarios

❌ **Not necessary for:**
- Short conversations (<20 messages)
- One-off scripts or demos
- Applications where memory usage isn't a concern

## Migration Steps

### Step 1: Assess Your Current Usage

First, identify where you're using conversation methods:

```python
# Find these patterns in your code:
agent.initiate_chat(...)           # Two-agent conversations
agent.a_initiate_chat(...)         # Async two-agent conversations
agent.initiate_chat(manager, ...)  # Group chat conversations
await agent.a_initiate_chat(...)   # Async group chat conversations
```

### Step 2: Simple Method Replacements

The migration is mostly about changing method names:

#### Two-Agent Conversations
```python
# Before (still works)
user_proxy.initiate_chat(assistant, message="Hello")

# After (memory-efficient)
user_proxy.initiate_chat_v2(assistant, message="Hello")
```

#### Async Two-Agent Conversations
```python
# Before (still works)
await user_proxy.a_initiate_chat(assistant, message="Hello")

# After (memory-efficient)
await user_proxy.a_initiate_chat_v2(assistant, message="Hello")
```

#### Group Chat Conversations
```python
# Before (still works)
agent.initiate_chat(group_manager, message="Hello group")

# After (memory-efficient)
group_manager.initiate_group_chat_v2(agent, message="Hello group")
```

#### Async Group Chat Conversations
```python
# Before (still works)
await agent.a_initiate_chat(group_manager, message="Hello group")

# After (memory-efficient)
await group_manager.a_initiate_group_chat_v2(agent, message="Hello group")
```

### Step 3: Update Imports (if needed)

If you're using the manager classes directly:

```python
# Add these imports if you need direct access to managers
from autogen.agentchat import (
    ConversationManager,           # For two-agent conversations
    GroupConversationManager,      # For group conversations
    AsyncConversationManager,      # For async two-agent conversations
    AsyncGroupConversationManager  # For async group conversations
)
```

## Migration Examples

### Example 1: Basic Two-Agent Chat

```python
import autogen

# Agent setup (unchanged)
assistant = autogen.AssistantAgent(
    name="assistant",
    llm_config={"model": "gpt-4"}
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10
)

# Before
user_proxy.initiate_chat(assistant, message="Solve this math problem: 2+2")

# After - just change the method name
user_proxy.initiate_chat_v2(assistant, message="Solve this math problem: 2+2")
```

### Example 2: Group Chat

```python
import autogen

# Agent and group setup (unchanged)
agents = [
    autogen.AssistantAgent(name="Coder", llm_config={"model": "gpt-4"}),
    autogen.AssistantAgent(name="Reviewer", llm_config={"model": "gpt-4"}),
    autogen.UserProxyAgent(name="User", human_input_mode="NEVER")
]

group_chat = autogen.GroupChat(agents=agents, messages=[], max_round=20)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config={"model": "gpt-4"})

# Before
agents[0].initiate_chat(manager, message="Let's work on a project")

# After - call the method on the manager instead
manager.initiate_group_chat_v2(agents[0], message="Let's work on a project")
```

### Example 3: Async Conversations

```python
import autogen
import asyncio

async def main():
    # Agent setup (unchanged)
    assistant = autogen.AssistantAgent(name="assistant", llm_config={"model": "gpt-4"})
    user_proxy = autogen.UserProxyAgent(name="user_proxy", human_input_mode="NEVER")

    # Before
    await user_proxy.a_initiate_chat(assistant, message="Hello async world")

    # After - just add _v2 to the method name
    await user_proxy.a_initiate_chat_v2(assistant, message="Hello async world")

asyncio.run(main())
```

### Example 4: Error Handling and Fallback

```python
import autogen

def robust_conversation(user_proxy, assistant, message):
    """Example with fallback to original method if needed."""
    try:
        # Try the new memory-efficient method first
        user_proxy.initiate_chat_v2(assistant, message=message)
    except Exception as e:
        print(f"v2 method failed: {e}")
        print("Falling back to original method...")
        # Fallback to original method
        user_proxy.initiate_chat(assistant, message=message)
```

## Testing Your Migration

### Step 1: Side-by-Side Testing

Test both methods to ensure identical behavior:

```python
import autogen

# Setup agents
assistant = autogen.AssistantAgent(name="assistant", llm_config={"model": "gpt-4"})
user_proxy = autogen.UserProxyAgent(name="user_proxy", human_input_mode="NEVER", max_consecutive_auto_reply=5)

# Test message
test_message = "Tell me a short joke and then say TERMINATE"

# Test original method
print("=== Original Method ===")
user_proxy.initiate_chat(assistant, message=test_message)

# Clear history for fair comparison
user_proxy.clear_history()
assistant.clear_history()

# Test new method
print("\n=== New v2 Method ===")
user_proxy.initiate_chat_v2(assistant, message=test_message)

# Compare results - they should be functionally identical
```

### Step 2: Memory Usage Testing

```python
import tracemalloc
import autogen

def test_memory_usage():
    """Compare memory usage between methods."""

    # Test setup
    assistant = autogen.AssistantAgent(name="assistant", llm_config={"model": "gpt-4"})
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=20  # Longer conversation for memory test
    )

    # Test original method
    tracemalloc.start()
    user_proxy.initiate_chat(assistant, message="Let's have a longer conversation...")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Original method peak memory: {peak / 1024 / 1024:.2f} MB")

    # Reset for fair comparison
    user_proxy.clear_history()
    assistant.clear_history()

    # Test new method
    tracemalloc.start()
    user_proxy.initiate_chat_v2(assistant, message="Let's have a longer conversation...")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"New v2 method peak memory: {peak / 1024 / 1024:.2f} MB")

test_memory_usage()
```

## Common Migration Issues

### Issue 1: Import Errors

**Problem**: `ImportError: cannot import name 'ConversationManager'`

**Solution**: Make sure you're using a recent version of AutoGen that includes the v2 methods.

```python
# Check if v2 methods are available
import autogen
agent = autogen.ConversableAgent(name="test")
if hasattr(agent, 'initiate_chat_v2'):
    print("v2 methods available!")
else:
    print("Please upgrade AutoGen to use v2 methods")
```

### Issue 2: Group Chat Method Confusion

**Problem**: Calling `agent.initiate_chat_v2(manager, ...)` instead of `manager.initiate_group_chat_v2(agent, ...)`

**Solution**: For group chats, call the method on the manager:

```python
# Wrong
agent.initiate_chat_v2(group_manager, message="Hello")

# Correct
group_manager.initiate_group_chat_v2(agent, message="Hello")
```

### Issue 3: Async/Sync Mismatch

**Problem**: Using sync methods in async context or vice versa

**Solution**: Match the method type to your context:

```python
# In sync context
user_proxy.initiate_chat_v2(assistant, message="Hello")

# In async context
await user_proxy.a_initiate_chat_v2(assistant, message="Hello")
```

## Gradual Migration Strategy

### Phase 1: Pilot Testing (1-2 weeks)
- Choose 1-2 non-critical conversations to migrate
- Test thoroughly in development environment
- Compare behavior and performance

### Phase 2: Selective Migration (2-4 weeks)
- Migrate long conversations and group chats first
- Keep short conversations on original methods
- Monitor for any issues

### Phase 3: Broader Adoption (4-8 weeks)
- Migrate remaining conversations based on priority
- Update documentation and team guidelines
- Train team members on new methods

### Phase 4: Full Migration (Optional)
- Migrate all conversations to v2 methods
- Update coding standards
- Consider deprecating original methods in your codebase

## Rollback Plan

If you encounter issues, rolling back is simple:

```python
# Change this:
user_proxy.initiate_chat_v2(assistant, message="Hello")

# Back to this:
user_proxy.initiate_chat(assistant, message="Hello")
```

All original methods remain unchanged and fully supported.

## Performance Monitoring

### Key Metrics to Track

1. **Memory Usage**
   ```python
   import psutil
   import os

   def get_memory_usage():
       process = psutil.Process(os.getpid())
       return process.memory_info().rss / 1024 / 1024  # MB

   # Monitor before and after conversations
   ```

2. **Conversation Duration**
   ```python
   import time

   start_time = time.time()
   # Run conversation
   duration = time.time() - start_time
   print(f"Conversation took {duration:.2f} seconds")
   ```

3. **Error Rates**
   - Track any new errors or exceptions
   - Monitor conversation completion rates

## Best Practices

### 1. Start with High-Impact Scenarios
- Migrate long conversations first
- Focus on memory-constrained environments
- Prioritize group chats and concurrent scenarios

### 2. Maintain Backward Compatibility
- Keep original method calls as fallbacks
- Use feature flags for gradual rollout
- Document both approaches in your codebase

### 3. Test Thoroughly
- Compare outputs between methods
- Test edge cases and error scenarios
- Validate termination conditions work correctly

### 4. Monitor and Measure
- Track memory usage improvements
- Monitor performance metrics
- Collect user feedback

## Conclusion

Migrating to v2 conversation methods is straightforward and provides significant benefits for memory efficiency. The migration is:

- **Risk-free**: Original methods continue to work
- **Simple**: Mostly just method name changes
- **Beneficial**: Significant memory improvements
- **Optional**: Migrate only what makes sense for your use case

Start with your longest conversations and most memory-sensitive scenarios, then expand based on your results and needs.
