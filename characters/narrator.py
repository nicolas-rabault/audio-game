"""Character: Narrator - Storytelling narrator with event logging capability
"""

CHARACTER_NAME = "Narrator"

VOICE_SOURCE = {
    'source_type': 'file',
    'path_on_server': 'clm-tts/fr/7601_7727_000062-0001.wav',
    'description': 'Narrator voice for storytelling'
}

INSTRUCTIONS = {
    'instruction_prompt': """
    Tu es le narrateur et tu dois aider ton hote a selectionner une histoire qui lui sera compté. Tu parle français.
    Tu dois demander a ton hote ces préférences et en fonction de ses réponses, tu dois selectionner une histoire parmis la liste des histoires suivantes:
     - mochi - une histoire de chat
     - the-other-side-of-the-mountain - une histoire de montagne
    une fois qu'une histoire a été selectionnée, tu dois lancer l'histoire.
    """,
    'language': 'fr'
}

# T018: Add TOOLS variable with log_story_event tool definition
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "log_story_event",
            "description": "Log an important narrative event to the terminal for the developer to see",
            "parameters": {
                "type": "object",
                "properties": {
                    "event": {
                        "type": "string",
                        "description": "The story event to log (e.g., 'User revealed their motivation')"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Importance level of this event"
                    }
                },
                "required": ["event"]
            }
        }
    }
]

METADATA = {'good': True, 'comment': 'Narrator character with tool support'}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import (
            _SYSTEM_PROMPT_TEMPLATE,
            _SYSTEM_PROMPT_BASICS,
            LANGUAGE_CODE_TO_INSTRUCTIONS,
            get_readable_llm_name,
        )

        additional_instructions = self.instructions.get('instruction_prompt', '')

        return _SYSTEM_PROMPT_TEMPLATE.format(
            _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
            additional_instructions=additional_instructions,
            language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                self.instructions.get('language')
            ),
            llm_name=get_readable_llm_name(),
        )

    # T019: Implement get_tools() method
    def get_tools(self) -> list[dict] | None:
        """Return tool definitions for LLM."""
        return globals().get('TOOLS')

    # T020: Implement handle_tool_call() method
    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute tool and return result."""
        if tool_name == "log_story_event":
            event = tool_input["event"]
            importance = tool_input.get("importance", "medium")

            # Log to terminal
            print(f"[NARRATOR EVENT] [{importance.upper()}] {event}")

            # Return confirmation
            return f"Logged story event: {event}"

        raise ValueError(f"Unknown tool: {tool_name}")
