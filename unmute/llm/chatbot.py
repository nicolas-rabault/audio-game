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

# Maximum messages per character before truncation
MAX_MESSAGES_PER_CHARACTER = 100

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


class CharacterHistory:
    """Represents a single character's conversation history within a session.
    
    Each character maintains their own isolated history with automatic
    truncation to prevent memory growth.
    """
    
    def __init__(self, character_name: str, system_prompt: str, created_at: float):
        """Initialize a new character history.
        
        Args:
            character_name: Name of the character (e.g., "charles")
            system_prompt: Initial system prompt for this character
            created_at: Timestamp when this history was created
        """
        self.character_name = character_name
        self.messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        self.created_at = created_at
        self.last_accessed = created_at
    
    def add_message(self, message: dict[str, str]) -> None:
        """Add a message to history.
        
        Args:
            message: Dictionary with 'role' and 'content' keys
        """
        self.messages.append(message)
    
    def truncate_if_needed(self, max_messages: int = MAX_MESSAGES_PER_CHARACTER) -> int:
        """Remove oldest messages if exceeding max limit.
        
        Preserves the system prompt (first message) and keeps the most recent
        messages up to the limit.
        
        Args:
            max_messages: Maximum number of messages to keep (default: 100)
            
        Returns:
            Number of messages removed
        """
        if len(self.messages) <= max_messages:
            return 0
        
        num_to_remove = len(self.messages) - max_messages
        # Keep system prompt (index 0) + last (max_messages - 1) messages
        self.messages = [self.messages[0]] + self.messages[-max_messages + 1:]
        
        return num_to_remove
    
    def get_system_prompt(self) -> str:
        """Get the system prompt (always first message).
        
        Returns:
            System prompt content
        """
        assert self.messages[0]["role"] == "system", "First message must be system prompt"
        return self.messages[0]["content"]
    
    def update_system_prompt(self, prompt: str) -> None:
        """Update the system prompt (always first message).
        
        Args:
            prompt: New system prompt content
        """
        assert self.messages[0]["role"] == "system", "First message must be system prompt"
        self.messages[0]["content"] = prompt
    
    @property
    def message_count(self) -> int:
        """Total number of messages in history."""
        return len(self.messages)


class Chatbot:
    def __init__(self):
        # Per-character conversation histories (Feature 003)
        self.character_histories: dict[str, CharacterHistory] = {}
        self.current_character: str | None = None
        self._prompt_generator: PromptGenerator | None = None
    
    def get_current_history(self) -> list[dict[str, Any]]:
        """Get the current character's message history.
        
        Returns the messages list for the current character, or a default
        history with system prompt if no character is active.
        
        Returns:
            List of message dictionaries
        """
        if self.current_character is None or self.current_character not in self.character_histories:
            # No character active - return default history with system prompt
            return [{"role": "system", "content": _default_system_prompt()}]
        return self.character_histories[self.current_character].messages
    
    def switch_character(self, character_name: str, system_prompt: str) -> None:
        """Switch to a different character, creating history if needed.
        
        This method either creates a new CharacterHistory for first-time characters
        or retrieves the existing history for previously-used characters.
        
        Args:
            character_name: Name of character to switch to
            system_prompt: System prompt for this character
            
        Effects:
            - Updates self.current_character
            - Creates new CharacterHistory if character is new
            - Updates last_accessed timestamp
            - Emits CHARACTER_SWITCH metrics
        """
        from unmute.timer import get_time, Stopwatch
        from unmute import metrics as mt
        
        # Validate inputs
        if not character_name or not character_name.strip():
            logger.error("Cannot switch to character with empty name")
            return
        
        if not system_prompt or not system_prompt.strip():
            logger.error(f"Cannot switch to character {character_name} with empty system prompt")
            return
        
        # Track previous character for metrics
        from_character = self.current_character if self.current_character else "none"
        
        # Start timing
        stopwatch = Stopwatch()
        
        # Create history if this is a new character
        if character_name not in self.character_histories:
            current_time = get_time()
            self.character_histories[character_name] = CharacterHistory(
                character_name=character_name,
                system_prompt=system_prompt,
                created_at=current_time
            )
            logger.info(f"Created new history for character: {character_name}")
        else:
            # Update last accessed time for existing character
            current_time = get_time()
            self.character_histories[character_name].last_accessed = current_time
            logger.info(f"Restored history for character: {character_name} ({self.character_histories[character_name].message_count} messages)")
        
        # Switch to this character
        self.current_character = character_name
        
        # Emit metrics
        duration = stopwatch.time()
        mt.CHARACTER_SWITCH_COUNT.labels(
            from_character=from_character,
            to_character=character_name
        ).inc()
        mt.CHARACTER_SWITCH_DURATION.observe(duration)
        mt.CHARACTER_HISTORIES_PER_SESSION.set(len(self.character_histories))
        mt.CHARACTER_HISTORY_SIZE.labels(character=character_name).set(
            self.character_histories[character_name].message_count
        )
        
        logger.debug(f"Character switch completed in {duration:.3f}s: {from_character} → {character_name}")
    
    def clear_character_history(self, character_name: str) -> None:
        """Clear conversation history for a specific character.
        
        Removes the character from character_histories dict. Next switch
        to this character will create fresh history.
        
        Args:
            character_name: Name of character whose history to clear
            
        Effects:
            - Removes character from character_histories
            - Sets current_character to None if clearing active character
            - Emits CHARACTER_HISTORY_CLEARS metric
        """
        from unmute import metrics as mt
        
        if character_name not in self.character_histories:
            logger.warning(f"Attempted to clear non-existent character: {character_name}")
            return
        
        # If clearing the active character, set current to None
        if self.current_character == character_name:
            logger.info(f"Clearing active character: {character_name}")
            self.current_character = None
        
        # Remove the character history
        del self.character_histories[character_name]
        
        # Emit metrics
        mt.CHARACTER_HISTORY_CLEARS.labels(
            character=character_name,
            reason="manual"
        ).inc()
        mt.CHARACTER_HISTORIES_PER_SESSION.set(len(self.character_histories))
        
        logger.info(f"Cleared history for character: {character_name}")
    
    def clear_all_histories(self) -> None:
        """Clear all character conversation histories.
        
        Called on session disconnect (__aexit__). Clears the entire
        character_histories dict and resets current_character to None.
        
        Effects:
            - Emits CHARACTER_HISTORY_CLEARS metric for each character
            - Clears character_histories dict
            - Sets current_character to None
        """
        from unmute import metrics as mt
        
        # Emit metrics for each character
        for character_name in self.character_histories:
            mt.CHARACTER_HISTORY_CLEARS.labels(
                character=character_name,
                reason="session_end"
            ).inc()
        
        num_cleared = len(self.character_histories)
        
        # Clear all histories
        self.character_histories.clear()
        self.current_character = None
        
        # Update gauge
        mt.CHARACTER_HISTORIES_PER_SESSION.set(0)
        
        logger.info(f"Cleared all character histories ({num_cleared} characters)")

    def conversation_state(self) -> ConversationState:
        current_history = self.get_current_history()
        if not current_history:
            return "waiting_for_user"

        last_message = current_history[-1]
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
        """Add a partial message to the current character's chat history, adding spaces if necessary.

        Returns:
            True if the message is a new message, False if it is a continuation of
            the last message.
        """
        # Get current history (operates on current character)
        current_history = self.get_current_history()
        
        if (
            generating_message_i is not None
            and len(current_history) > generating_message_i
        ):
            logger.warning(
                f"Tried to add {delta=} {role=} "
                f"but {generating_message_i=} didn't match"
            )
            return False

        is_new_message = False
        
        if not current_history or current_history[-1]["role"] != role:
            current_history.append({"role": role, "content": delta})
            is_new_message = True
        else:
            last_message: str = current_history[-1]["content"]

            # Add a space if necessary
            needs_space_left = last_message != "" and not last_message[-1].isspace()
            needs_space_right = delta != "" and not delta[0].isspace()

            if needs_space_left and needs_space_right:
                delta = " " + delta

            current_history[-1]["content"] += delta
            is_new_message = last_message == ""  # new message if `last_message` was empty
        
        # Apply truncation if needed for current character
        if self.current_character and self.current_character in self.character_histories:
            from unmute import metrics as mt
            removed = self.character_histories[self.current_character].truncate_if_needed()
            if removed > 0:
                mt.CHARACTER_HISTORY_TRUNCATIONS.labels(character=self.current_character).inc()
                mt.CHARACTER_HISTORY_SIZE.labels(character=self.current_character).set(
                    self.character_histories[self.current_character].message_count
                )
                logger.info(f"Truncated {removed} messages from {self.current_character}'s history")
        
        return is_new_message

    def preprocessed_messages(self):
        current_history = self.get_current_history()
        if len(current_history) > 2:
            messages = current_history
        else:
            assert len(current_history) >= 1
            assert current_history[0]["role"] == "system"

            messages = [
                current_history[0],
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

    def _update_system_prompt(self, system_prompt: str):
        """Update the system prompt for the current character."""
        if self.current_character and self.current_character in self.character_histories:
            self.character_histories[self.current_character].update_system_prompt(system_prompt)
        # If no current character, the system prompt will be used when a character is created

    def get_system_prompt(self) -> str:
        """Get the system prompt for the current character."""
        current_history = self.get_current_history()
        assert len(current_history) > 0
        assert current_history[0]["role"] == "system"
        return current_history[0]["content"]

    def get_prompt_generator(self) -> PromptGenerator | None:
        return self._prompt_generator

    def last_message(self, role: str) -> str | None:
        current_history = self.get_current_history()
        valid_messages = [
            message
            for message in current_history
            if message["role"] == role and message["content"].strip() != ""
        ]
        if valid_messages:
            return valid_messages[-1]["content"]
        else:
            return None
