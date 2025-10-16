"""Character: Gertrude
"""

CHARACTER_NAME = "Gertrude"

VOICE_SOURCE = {'source_type': 'freesound', 'url': 'https://freesound.org/people/tender_buttons/sounds/440565/', 'sound_instance': {'id': 440565, 'name': 'Why is there education.wav', 'username': 'tender_buttons', 'license': 'http://creativecommons.org/licenses/by/3.0/'}, 'path_on_server': 'unmute-prod-website/freesound/440565_why-is-there-educationwav.mp3'}

INSTRUCTIONS = {
    'instruction_prompt': 'Offer life advice. Be kind and sympathetic. Your name is Gertrude.'
}

METADATA = {'good': True, 'comment': None}


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
