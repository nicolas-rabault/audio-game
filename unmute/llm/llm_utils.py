import os
import re
from copy import deepcopy
from functools import cache
from typing import Any, AsyncIterator, Protocol, cast

from mistralai import Mistral
from openai import AsyncOpenAI, OpenAI

from unmute.kyutai_constants import LLM_SERVER

from ..kyutai_constants import KYUTAI_LLM_API_KEY, KYUTAI_LLM_MODEL

INTERRUPTION_CHAR = "—"  # em-dash
USER_SILENCE_MARKER = "..."


def preprocess_messages_for_llm(
    chat_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    output = []

    for message in chat_history:
        message = deepcopy(message)

        # Sometimes, an interruption happens before the LLM can say anything at all.
        # In that case, we're left with a message with only INTERRUPTION_CHAR.
        # Simplify by removing.
        if message["content"].replace(INTERRUPTION_CHAR, "") == "":
            continue

        if output and message["role"] == output[-1]["role"]:
            output[-1]["content"] += " " + message["content"]
        else:
            output.append(message)

    def role_at(index: int) -> str | None:
        if index >= len(output):
            return None
        return output[index]["role"]

    if role_at(0) == "system" and role_at(1) in [None, "assistant"]:
        # Some LLMs, like Gemma, get confused if the assistant message goes before user
        # messages, so add a dummy user message.
        output = [output[0]] + [{"role": "user", "content": "Hello."}] + output[1:]

    for message in chat_history:
        if (
            message["role"] == "user"
            and message["content"].startswith(USER_SILENCE_MARKER)
            and message["content"] != USER_SILENCE_MARKER
        ):
            # This happens when the user is silent but then starts talking again after
            # the silence marker was inserted but before the LLM could respond.
            # There are special instructions in the system prompt about how to handle
            # the silence marker, so remove the marker from the message to not confuse
            # the LLM
            message["content"] = message["content"][len(USER_SILENCE_MARKER) :]

    return output


async def rechunk_to_words(iterator: AsyncIterator[str]) -> AsyncIterator[str]:
    """Rechunk the stream of text to whole words.

    Otherwise the TTS doesn't know where word boundaries are and will mispronounce
    split words.

    The spaces will be included with the next word, so "foo bar baz" will be split into
    "foo", " bar", " baz".
    Multiple space-like characters will be merged to a single space.
    """
    buffer = ""
    space_re = re.compile(r"\s+")
    prefix = ""
    async for delta in iterator:
        buffer = buffer + delta
        while True:
            match = space_re.search(buffer)
            if match is None:
                break
            chunk = buffer[: match.start()]
            buffer = buffer[match.end() :]
            if chunk != "":
                yield prefix + chunk
            prefix = " "

    if buffer != "":
        yield prefix + buffer


class LLMStream(Protocol):
    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Get a chat completion from the LLM."""
        ...


class MistralStream:
    def __init__(self):
        self.current_message_index = 0
        self.mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    async def chat_completion(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        event_stream = await self.mistral.chat.stream_async(
            model="mistral-large-latest",
            messages=cast(Any, messages),  # It's too annoying to type this properly
            temperature=1.0,
        )

        async for event in event_stream:
            delta = event.data.choices[0].delta.content
            assert isinstance(delta, str)  # make Pyright happy
            yield delta


def get_openai_client(
    server_url: str = LLM_SERVER, api_key: str | None = KYUTAI_LLM_API_KEY
) -> AsyncOpenAI:
    # AsyncOpenAI() will complain if the API key is not set, so set a dummy string if it's None.
    # This still makes sense when using vLLM because it doesn't care about the API key.
    return AsyncOpenAI(api_key=api_key or "EMPTY", base_url=server_url + "/v1")


@cache
def autoselect_model() -> str:
    if KYUTAI_LLM_MODEL is not None:
        return KYUTAI_LLM_MODEL
    openai_client = get_openai_client()
    # OpenAI() will complain if the API key is not set, so set a dummy string if it's None.
    # This still makes sense when using vLLM because it doesn't care about the API key.
    client_sync = OpenAI(
        api_key=openai_client.api_key or "EMPTY", base_url=openai_client.base_url
    )
    models = client_sync.models.list()
    if len(models.data) != 1:
        raise ValueError("There are multiple models available. Please specify one.")
    return models.data[0].id


class VLLMStream:
    def __init__(
        self,
        client: AsyncOpenAI,
        temperature: float = 1.0,
        tools: list[dict[str, Any]] | None = None,
        prompt_generator: Any = None,
        tool_validators: dict[str, Any] | None = None,
        character_name: str = "Unknown",
    ):
        """
        Initialize VLLM stream with optional tool definitions.

        Args:
            client: AsyncOpenAI client instance
            temperature: Sampling temperature (default 1.0)
            tools: Optional list of OpenAI function calling tool definitions
            prompt_generator: Character's PromptGenerator instance (for tool execution)
            tool_validators: Dict of Pydantic validators for each tool
            character_name: Character name (for metrics)
        """
        self.client = client
        self.model = autoselect_model()
        self.temperature = temperature
        self.tools = tools
        self.prompt_generator = prompt_generator
        self.tool_validators = tool_validators or {}
        self.character_name = character_name

    async def chat_completion(
        self, messages: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        """
        Stream chat completion with automatic tool call handling.

        T015: Detects tool calls in streaming response
        T016-T017: Executes tools and re-queries LLM
        """
        # Build API call parameters
        api_params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
        }

        # Add tools if defined
        if self.tools:
            api_params["tools"] = self.tools

        stream = await self.client.chat.completions.create(**api_params)

        # T015: Collect tool calls if any
        tool_calls_buffer = {}
        assistant_message_content = []
        tool_calls_detected = False

        async with stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta

                # T015: Check for tool calls in streaming response
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    tool_calls_detected = True
                    for tool_call_delta in delta.tool_calls:
                        idx = tool_call_delta.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                'id': tool_call_delta.id or '',
                                'type': 'function',
                                'function': {
                                    'name': tool_call_delta.function.name or '',
                                    'arguments': ''
                                }
                            }

                        # Accumulate function name and arguments
                        if tool_call_delta.function.name:
                            tool_calls_buffer[idx]['function']['name'] = tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            tool_calls_buffer[idx]['function']['arguments'] += tool_call_delta.function.arguments
                        if tool_call_delta.id:
                            tool_calls_buffer[idx]['id'] = tool_call_delta.id

                # Regular content
                chunk_content = delta.content
                if chunk_content:
                    assistant_message_content.append(chunk_content)
                    # If not executing tools, yield content immediately
                    if not self.tools or not self.prompt_generator:
                        yield chunk_content

        # T016-T017: If tools were called and we have prompt_generator, execute them
        if tool_calls_detected and self.prompt_generator and self.tools:
            from unmute.llm.tool_executor import execute_tool
            import logging
            logger = logging.getLogger(__name__)

            # Convert buffer to list of tool calls
            tool_calls = [tool_calls_buffer[idx] for idx in sorted(tool_calls_buffer.keys())]

            logger.info(f"Detected {len(tool_calls)} tool calls: {[tc['function']['name'] for tc in tool_calls]}")

            # Add assistant message with tool calls to conversation
            messages.append({
                "role": "assistant",
                "content": "".join(assistant_message_content) if assistant_message_content else None,
                "tool_calls": tool_calls
            })

            # T016: Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call['function']['name']
                tool_arguments_json = tool_call['function']['arguments']
                tool_call_id = tool_call['id']

                logger.info(f"Executing tool: {tool_name} with args: {tool_arguments_json}")

                # Execute tool
                result = await execute_tool(
                    self.prompt_generator,
                    tool_name,
                    tool_arguments_json,
                    self.tool_validators,
                    self.character_name
                )

                # T017: Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result
                })

                logger.info(f"Tool {tool_name} result: {result[:100]}")

            # T017: Re-query LLM with tool results (no tools this time to avoid loops)
            logger.info("Re-querying LLM with tool results")
            final_stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=self.temperature,
                # Don't include tools in follow-up to avoid infinite loops
            )

            # Stream the final response
            async with final_stream:
                async for chunk in final_stream:
                    chunk_content = chunk.choices[0].delta.content
                    if chunk_content:
                        yield chunk_content

        elif not tool_calls_detected and assistant_message_content:
            # No tool calls, but we buffered content (shouldn't happen if tools not defined)
            for content in assistant_message_content:
                yield content
