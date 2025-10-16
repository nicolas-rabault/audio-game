"""Character: Développeuse
"""

CHARACTER_NAME = "Développeuse"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/developpeuse-3.wav', 'description': 'This is the voice of one of the developers at Kyutai.'}

INSTRUCTIONS = {
    'instruction_prompt': """
{additional_instructions}

# CONTEXT
It's currently {current_time} in your timezone ({timezone}).

# START THE CONVERSATION
Repond to the user's message with a greeting and some kind of conversation starter.
For example, you can {conversation_starter_suggestion}.
""",
    'language': 'fr'
}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        import datetime
        import random
        from unmute.llm.system_prompt import (
            _SYSTEM_PROMPT_TEMPLATE,
            _SYSTEM_PROMPT_BASICS,
            _DEFAULT_ADDITIONAL_INSTRUCTIONS,
            LANGUAGE_CODE_TO_INSTRUCTIONS,
            get_readable_llm_name,
        )
        from characters.resources.shared_constants import CONVERSATION_STARTER_SUGGESTIONS

        # Format the instruction prompt with dynamic values
        instruction_prompt = self.instructions.get('instruction_prompt', '')
        additional_instructions = instruction_prompt.format(
            additional_instructions=_DEFAULT_ADDITIONAL_INSTRUCTIONS,
            current_time=datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M"),
            timezone=datetime.datetime.now().astimezone().tzname(),
            conversation_starter_suggestion=random.choice(CONVERSATION_STARTER_SUGGESTIONS),
        )

        return _SYSTEM_PROMPT_TEMPLATE.format(
            _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
            additional_instructions=additional_instructions,
            language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                self.instructions.get('language')
            ),
            llm_name=get_readable_llm_name(),
        )
