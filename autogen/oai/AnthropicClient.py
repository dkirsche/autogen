"""
Create an OpenAI-compatible client for the Anthropic API.

Example usage:
Install the `anthropic` package by running `pip install --upgrade anthropic`.
- https://docs.anthropic.com/en/docs/quickstart-guide

import autogen

config_list = [
    {
        "model": "claude-3-sonnet-20240229",
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        "api_type": "anthropic",
    }
]

assistant = autogen.AssistantAgent("assistant", llm_config={"config_list": config_list})
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import warnings
from typing import Any, Dict, List, Tuple, Union

from anthropic import Anthropic
from anthropic import __version__ as anthropic_version
from anthropic.types import Completion, Message
from llm_clients.client_utils import validate_parameter
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion import ChatCompletionMessage, Choice
from typing_extensions import Annotated
from llm_logger import postgres_logger
import datetime
from autogen._pydantic import model_dump


from anthropic.types.tool_use_block_param import (
    ToolUseBlockParam,
)

llm_logger = postgres_logger.PostgresLogger(os.getenv("POSTGRES_URL"))
ANTHROPIC_PRICING_1k = {
    "claude-3-5-sonnet-20240620": (0.003, 0.015),
    "claude-3-5-sonnet-latest": (0.003, 0.015),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-2.0": (0.008, 0.024),
    "claude-2.1": (0.008, 0.024),
    "claude-3.0-opus": (0.015, 0.075),
    "claude-3-haiku-20240307": (0.00025, 0.00125),
}


class AnthropicClient:
    def __init__(self, **kwargs: Any):
        """
        Initialize the Anthropic API client.
        Args:
            api_key (str): The API key for the Anthropic API or set the `ANTHROPIC_API_KEY` environment variable.
        """
        self._api_key = kwargs.get("api_key", None)

        if not self._api_key:
            self._api_key = os.getenv("ANTHROPIC_API_KEY")

        if self._api_key is None:
            raise ValueError("API key is required to use the Anthropic API.")

        self._client = Anthropic(api_key=self._api_key)
        self._last_tooluse_status = {}

    def load_config(self, params: Dict[str, Any]):
        """Load the configuration for the Anthropic API client."""
        anthropic_params = {}

        anthropic_params["model"] = params.get("model", None)
        assert anthropic_params["model"], "Please provide a `model` in the config_list to use the Anthropic API."

        anthropic_params["temperature"] = validate_parameter(
            params, "temperature", (float, int), False, 1.0, (0.0, 1.0), None
        )
        anthropic_params["max_tokens"] = validate_parameter(params, "max_tokens", int, False, 4096, (1, None), None)
        anthropic_params["top_k"] = validate_parameter(params, "top_k", int, True, None, (1, None), None)
        anthropic_params["top_p"] = validate_parameter(params, "top_p", (float, int), True, None, (0.0, 1.0), None)
        anthropic_params["stop_sequences"] = validate_parameter(params, "stop_sequences", list, True, None, None, None)
        anthropic_params["stream"] = validate_parameter(params, "stream", bool, False, False, None, None)

        if anthropic_params["stream"]:
            warnings.warn(
                "Streaming is not currently supported, streaming will be disabled.",
                UserWarning,
            )
            anthropic_params["stream"] = False

        return anthropic_params

    def cost(self, response) -> float:
        """Calculate the cost of the completion using the Anthropic pricing."""
        return response.cost

    @property
    def api_key(self):
        return self._api_key

    def create(self, params: Dict[str, Any]) -> Completion:
        """Create a completion for a given config.

        Args:
            params: The params for the completion.

        Returns:
            The completion.
        """
        if "tools" in params:
            converted_functions = self.convert_tools_to_functions(params["tools"])
            params["functions"] = params.get("functions", []) + converted_functions
        start_time = datetime.datetime.now(datetime.timezone.utc)
        raw_contents = params["messages"]
        anthropic_params = self.load_config(params)
        agent = params.pop("agent", "anthropic_unknown")
        processed_messages = []
        pinned_messages = []
        self._tool_call_dict = {}  # Create an empty dictionary to hold the tool call data by ID

        for message in raw_contents:
            if message["role"] == "system":
                params["system"] = message["content"]
            elif message.get("pinned", False):  # Check if the message is pinned
                pinned_messages.append(message)  # Append to pinned_messages if 'pinned': True
            elif message["role"] == "function":
                processed_messages.append(self.return_function_call_result(message["content"]))
            elif "function_call" in message:
                processed_messages.append(self.restore_last_tooluse_status())
            elif "tool_calls" in message:  # a tool call is being made. cache it for later when the response is seen.
                self.process_tool_calls(message)
            elif message["role"] == "tool":
                processed_messages.extend(self.return_tool_call_result(message))
            elif message["content"] == "":
                message["content"] = "I'm done. Please send TERMINATE"  # Not sure about this one.
                processed_messages.append(message)
            else:
                processed_messages.append(message)
        # Check for interleaving roles and insert a message for missing roles
        i = 0

        processed_messages_count = len(processed_messages)
        while i < processed_messages_count:
            expected_role = "user" if i % 2 == 0 else "assistant"
            if processed_messages[i]["role"] != expected_role:
                # Insert a new message with the expected role and empty content
                new_message = {"content": "continue", "role": expected_role}
                processed_messages.insert(i, new_message)
            i += 1

        # Insert pinned messages after the first message
        insert_position = 1
        for pinned_message in pinned_messages:
            # Ensure pinned message has the role of 'assistant'
            pinned_message_with_role = {"content": pinned_message["content"], "role": "assistant"}
            processed_messages.insert(insert_position, pinned_message_with_role)

            # Insert a dummy 'user' message with empty content to ensure roles interleave
            dummy_user_message = {"content": "continue", "role": "user"}
            processed_messages.insert(insert_position + 1, dummy_user_message)

            # Move the insert position forward by 2 since we're inserting two messages
            insert_position += 2

        # Note: When using reflection_with_llm we may end up with an "assistant" message as the last message
        if processed_messages[-1]["role"] != "user":
            # If the last role is not user, add a continue message at the end
            continue_message = {"content": "continue", "role": "user"}
            processed_messages.append(continue_message)

        params["messages"] = processed_messages

        # TODO: support stream
        params = params.copy()
        if "functions" in params:
            tools_configs = params.pop("functions")
            tools_configs = [self.openai_func_to_anthropic(tool) for tool in tools_configs]
            params["tools"] = tools_configs

        # Anthropic doesn't accept None values, so we need to use keyword argument unpacking instead of setting parameters.
        # Copy params we need into anthropic_params
        # Remove any that don't have values
        anthropic_params["messages"] = params["messages"]
        if "system" in params:
            anthropic_params["system"] = params["system"]
        if "tools" in params:
            anthropic_params["tools"] = params["tools"]
        if anthropic_params["top_k"] is None:
            del anthropic_params["top_k"]
        if anthropic_params["top_p"] is None:
            del anthropic_params["top_p"]
        if anthropic_params["stop_sequences"] is None:
            del anthropic_params["stop_sequences"]

        response = self._client.messages.create(**anthropic_params)

        # Calculate and save the cost onto the response
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        response.cost = _calculate_cost(prompt_tokens, completion_tokens, anthropic_params["model"])
        end_time = datetime.datetime.now(datetime.timezone.utc)
        llm_logger.insert_chat_completion(
            agent=agent,
            request=json.dumps(params),
            response=str(response),
            is_cached=0,
            cost=response.cost,
            invocation_id="Anthropic",
            start_time=start_time,
            end_time=end_time,
            model_id=anthropic_params["model"],
        )
        return response

    def message_retrieval(self, response: Union[Message]) -> Union[List[str], List[ChatCompletionMessage]]:
        """Retrieve the messages from the response."""
        messages = response.content
        if len(messages) == 0:
            return None

        # Find tool_use and text choices
        tool_use_choice = None
        text_choice = None

        for choice in messages:
            if choice.type == "tool_use":
                tool_use_choice = choice
                self._last_tooluse_status["tool_use"] = choice.model_dump()
            elif choice.type == "text":
                text_choice = choice
                self._last_tooluse_status["think"] = choice.text

        # If there's a tool_use, pass both choices to response_to_openai_message
        if tool_use_choice:
            choice_selected = model_dump(self.response_to_openai_message(tool_use_choice, text_choice))
        else:
            # If no tool_use, return the text from the first choice
            choice_selected = messages[0].text

        return choice_selected

    def response_to_openai_message(self, response, thought) -> ChatCompletionMessage:
        """Convert the client response to OpenAI ChatCompletion Message"""
        dict_response = response.model_dump()

        # Create a Function object
        function = {"name": dict_response["name"], "arguments": json.dumps(dict_response["input"])}

        # Create a ChatCompletionMessageToolCall object using the existing ID
        tool_call = ChatCompletionMessageToolCall(
            id=dict_response["id"], function=function, type="function"  # Use the ID from ToolUseBlock
        )

        return ChatCompletionMessage(
            content=thought.text, role="assistant", function_call=None, tool_calls=[tool_call], refusal=None
        )

    def restore_last_tooluse_status(self) -> Dict:
        cached_content = []
        if "think" in self._last_tooluse_status:
            cached_content.append({"type": "text", "text": self._last_tooluse_status["think"]})
        cached_content.append(self._last_tooluse_status["tool_use"])
        res = {"role": "assistant", "content": cached_content}
        return res

    # store all tools that have been called for later retrieval so the call can be paired with the response
    def process_tool_calls(self, message):
        for tool_call in message.get("tool_calls", []):
            tool_call_id = tool_call["id"]
            tool_call_data = {
                "content": message["content"],
                "function_name": tool_call["function"]["name"],
                "function_arguments": tool_call["function"]["arguments"],
                "type": tool_call["type"],
            }
            # Initialize a list for this ID if it doesn't exist
            if tool_call_id not in self._tool_call_dict:
                self._tool_call_dict[tool_call_id] = []
            # Append the new tool call data to the list
            self._tool_call_dict[tool_call_id].append(tool_call_data)

    def return_tool_call_result(self, message):
        tool_call_id = message.get("tool_call_id", None)
        tool_call_info_list = self._tool_call_dict.get(tool_call_id, [])

        # Get the most recent tool call info from the list
        if not tool_call_info_list:
            raise ValueError(f"No tool call info found for ID: {tool_call_id}")

        tool_call_info = tool_call_info_list[-1]  # Get the most recent tool call

        assistant_msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": tool_call_info["content"]},
                {
                    "id": tool_call_id,
                    "input": json.loads(tool_call_info["function_arguments"]),
                    "name": tool_call_info["function_name"],
                    "type": "tool_use",
                },
            ],
        }

        user_msg = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": message["content"],
                }
            ],
        }
        return [assistant_msg, user_msg]

    def return_function_call_result(self, result: str) -> Dict:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": self._last_tooluse_status["tool_use"]["id"],
                    "content": result,
                }
            ],
        }

    @staticmethod
    def openai_func_to_anthropic(openai_func: dict) -> dict:
        res = openai_func.copy()
        res["input_schema"] = res.pop("parameters")
        return res

    @staticmethod
    def get_usage(response: Message) -> Dict:
        """Get the usage of tokens and their cost information."""
        return {
            "prompt_tokens": response.usage.input_tokens if response.usage is not None else 0,
            "completion_tokens": response.usage.output_tokens if response.usage is not None else 0,
            "total_tokens": (
                response.usage.input_tokens + response.usage.output_tokens if response.usage is not None else 0
            ),
            "cost": response.cost if hasattr(response, "cost") else 0.0,
            "model": response.model,
        }

    @staticmethod
    def convert_tools_to_functions(tools: List) -> List:
        functions = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                functions.append(tool["function"])

        return functions


def _calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate the cost of the completion using the Anthropic pricing."""
    total = 0.0

    if model in ANTHROPIC_PRICING_1k:
        input_cost_per_1k, output_cost_per_1k = ANTHROPIC_PRICING_1k[model]
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        total = input_cost + output_cost
    else:
        warnings.warn(f"Cost calculation not available for model {model}", UserWarning)

    return total
