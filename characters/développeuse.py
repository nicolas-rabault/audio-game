"""Character: Développeuse
"""

CHARACTER_NAME = "Développeuse"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/developpeuse-3.wav', 'description': 'This is the voice of one of the developers at Kyutai.'}

INSTRUCTIONS = {'type': 'smalltalk', 'language': 'fr'}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import SmalltalkInstructions

        inst = SmalltalkInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()
