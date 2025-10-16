"""Character: Watercooler
"""

CHARACTER_NAME = "Watercooler"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/p329_022.wav', 'description': 'From the Device Recorded VCTK dataset.', 'description_link': 'https://datashare.ed.ac.uk/handle/10283/3038'}

INSTRUCTIONS = {'type': 'smalltalk'}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions

        inst = SmalltalkInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()
