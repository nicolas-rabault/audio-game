"""Character: Quiz show
 - man, UK, skeptical
"""

CHARACTER_NAME = "Quiz show"

VOICE_SOURCE = {'source_type': 'freesound', 'url': 'https://freesound.org/people/InspectorJ/sounds/519189/', 'sound_instance': {'id': 519189, 'name': "Request #42 - Hmm, I don't know.wav", 'username': 'InspectorJ', 'license': 'https://creativecommons.org/licenses/by/4.0/'}, 'path_on_server': 'unmute-prod-website/freesound/519189_request-42---hmm-i-dont-knowwav.mp3'}

INSTRUCTIONS = {'type': 'quiz_show'}

METADATA = {'good': True, 'comment': 'man, UK, skeptical'}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        from unmute.llm.system_prompt import QuizShowInstructions

        inst = QuizShowInstructions(language=self.instructions.get("language"))
        return inst.make_system_prompt()
