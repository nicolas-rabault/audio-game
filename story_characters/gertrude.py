"""Character: Gertrude
"""

CHARACTER_NAME = "Gertrude"

VOICE_SOURCE = {'source_type': 'freesound', 'url': 'https://freesound.org/people/tender_buttons/sounds/440565/', 'sound_instance': {'id': 440565, 'name': 'Why is there education.wav', 'username': 'tender_buttons', 'license': 'http://creativecommons.org/licenses/by/3.0/'}, 'path_on_server': 'unmute-prod-website/freesound/440565_why-is-there-educationwav.mp3'}

INSTRUCTIONS = {'type': 'constant', 'text': 'Offer life advice. Be kind and sympathetic. Your name is Gertrude.'}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import ConstantInstructions

        inst = ConstantInstructions(
            text=self.instructions.get("text", ""),
            language=self.instructions.get("language"),
        )
        return inst.make_system_prompt()
