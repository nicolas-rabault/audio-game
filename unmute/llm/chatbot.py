from logging import getLogger
from typing import Any, Literal, Protocol

from unmute.llm.llm_utils import preprocess_messages_for_llm
from unmute.llm.system_prompt import (
    _SYSTEM_PROMPT_TEMPLATE,
    _SYSTEM_PROMPT_BASICS,
    _DEFAULT_ADDITIONAL_INSTRUCTIONS,
    LANGUAGE_CODE_TO_INSTRUCTIONS,
    get_readable_llm_name,
)

ConversationState = Literal["waiting_for_user", "user_speaking", "bot_speaking"]

logger = getLogger(__name__)


class PromptGenerator(Protocol):
    """Protocol for objects that can generate system prompts."""

    def make_system_prompt(self) -> str:
        ...


def _default_system_prompt() -> str:
    """Generate a default system prompt using constant instructions."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
        additional_instructions=_DEFAULT_ADDITIONAL_INSTRUCTIONS,
        language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS[None],
        llm_name=get_readable_llm_name(),
    )


class Chatbot:
    def __init__(self):
        # It's actually a list of ChatCompletionStreamRequestMessagesTypedDict but then
        # it's really difficult to convince Python you're passing in the right type
        self.chat_history: list[dict[Any, Any]] = [
            {"role": "system", "content": _default_system_prompt()}
        ]
        self._prompt_generator: PromptGenerator | None = None

    def conversation_state(self) -> ConversationState:
        if not self.chat_history:
            return "waiting_for_user"

        last_message = self.chat_history[-1]
        if last_message["role"] == "assistant":
            return "bot_speaking"
        elif last_message["role"] == "user":
            if last_message["content"].strip() != "":
                return "user_speaking"
            else:
                # Or do we want "user_speaking" here?
                return "waiting_for_user"
        elif last_message["role"] == "system":
            return "waiting_for_user"
        else:
            raise RuntimeError(f"Unknown role: {last_message['role']}")

    async def add_chat_message_delta(
        self,
        delta: str,
        role: Literal["user", "assistant"],
        generating_message_i: int | None = None,  # Avoid race conditions
    ) -> bool:
        """Add a partial message to the chat history, adding spaces if necessary.

        Returns:
            True if the message is a new message, False if it is a continuation of
            the last message.
        """
        if (
            generating_message_i is not None
            and len(self.chat_history) > generating_message_i
        ):
            logger.warning(
                f"Tried to add {delta=} {role=} "
                f"but {generating_message_i=} didn't match"
            )
            return False

        if not self.chat_history or self.chat_history[-1]["role"] != role:
            self.chat_history.append({"role": role, "content": delta})
            return True
        else:
            last_message: str = self.chat_history[-1]["content"]

            # Add a space if necessary
            needs_space_left = last_message != "" and not last_message[-1].isspace()
            needs_space_right = delta != "" and not delta[0].isspace()

            if needs_space_left and needs_space_right:
                delta = " " + delta

            self.chat_history[-1]["content"] += delta
            return last_message == ""  # new message if `last_message` was empty

    def preprocessed_messages(self):
        if len(self.chat_history) > 2:
            messages = self.chat_history
        else:
            assert len(self.chat_history) >= 1
            assert self.chat_history[0]["role"] == "system"

            messages = [
                self.chat_history[0],
                # Some models, like Gemma, don't like it when there is no user message
                # so we add one.
                {"role": "user", "content": "Hello!"},
            ]

        messages = preprocess_messages_for_llm(messages)
        return messages

    def set_prompt_generator(self, prompt_generator: PromptGenerator):
        """Set the prompt generator and update the system prompt.

        Note that make_system_prompt() might not be deterministic, so we run it only
        once and save the result. We still keep self._prompt_generator because it's used
        to check whether initial instructions have been set.
        """
        self._update_system_prompt(prompt_generator.make_system_prompt())
        self._prompt_generator = prompt_generator

    # Legacy method for backwards compatibility
    def set_instructions(self, instructions: dict[str, Any] | PromptGenerator):
        """Set instructions using either a dict or a PromptGenerator.

        If a dict is provided, it should have a 'instruction_prompt' field and
        will be wrapped in a simple PromptGenerator.
        """
        if hasattr(instructions, 'make_system_prompt'):
            # It's already a PromptGenerator
            self.set_prompt_generator(instructions)  # type: ignore
        else:
            # It's a dict, create a simple wrapper
            class SimplePromptGenerator:
                def __init__(self, instructions_dict: dict[str, Any]):
                    self.instructions = instructions_dict

                def make_system_prompt(self) -> str:
                    instruction_prompt = self.instructions.get('instruction_prompt', _DEFAULT_ADDITIONAL_INSTRUCTIONS)
                    return _SYSTEM_PROMPT_TEMPLATE.format(
                        _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
                        additional_instructions=instruction_prompt,
                        language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                            self.instructions.get('language')
                        ),
                        llm_name=get_readable_llm_name(),
                    )

            self.set_prompt_generator(SimplePromptGenerator(instructions))  # type: ignore

    def _update_system_prompt(self, system_prompt: str):
        self.chat_history[0] = {"role": "system", "content": system_prompt}

    def get_system_prompt(self) -> str:
        assert len(self.chat_history) > 0
        assert self.chat_history[0]["role"] == "system"
        return self.chat_history[0]["content"]

    def get_prompt_generator(self) -> PromptGenerator | None:
        return self._prompt_generator

    def last_message(self, role: str) -> str | None:
        valid_messages = [
            message
            for message in self.chat_history
            if message["role"] == role and message["content"].strip() != ""
        ]
        if valid_messages:
            return valid_messages[-1]["content"]
        else:
            return None
