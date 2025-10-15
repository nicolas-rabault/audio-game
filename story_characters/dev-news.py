"""Character: Dev (news)
"""

CHARACTER_NAME = "Dev (news)"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/developer-1.mp3', 'description': 'This is the voice of Václav Volhejn from Kyutai.'}

INSTRUCTIONS = {'type': 'news'}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import NewsInstructions

        inst = NewsInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()
