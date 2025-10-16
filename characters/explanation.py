"""Character: Explanation
"""

CHARACTER_NAME = "Explanation"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/ex04_narration_longform_00001.wav', 'description': 'This voice comes from the Expresso dataset.', 'description_link': 'https://speechbot.github.io/expresso/'}

INSTRUCTIONS = {'type': 'unmute_explanation'}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import UnmuteExplanationInstructions

        inst = UnmuteExplanationInstructions()
        return inst.make_system_prompt()
