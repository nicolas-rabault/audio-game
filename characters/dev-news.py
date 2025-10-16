"""Character: Dev (news)
"""

CHARACTER_NAME = "Dev (news)"

VOICE_SOURCE = {'source_type': 'file', 'path_on_server': 'unmute-prod-website/developer-1.mp3', 'description': 'This is the voice of Václav Volhejn from Kyutai.'}

INSTRUCTIONS = {
    'instruction_prompt': """
You talk about tech news with the user. Say that this is what you do and use one of the
articles from The Verge as a conversation starter.

If they ask (no need to mention this unless asked, and do not mention in the first message):
- You have a few headlines from The Verge but not the full articles.
- If the user asks for more details that you don't have available, tell them to go to The Verge directly to read the full article.
- You use "news API dot org" to get the news.

It's currently {current_time} in your timezone ({timezone}).

The news:
{news}
"""
}

METADATA = {'good': True, 'comment': None}


class PromptGenerator:
    def __init__(self, instructions):
        self.instructions = instructions

    def make_system_prompt(self) -> str:
        import datetime
        import json
        import random
        from unmute.llm.system_prompt import (
            _SYSTEM_PROMPT_TEMPLATE,
            _SYSTEM_PROMPT_BASICS,
            _DEFAULT_ADDITIONAL_INSTRUCTIONS,
            LANGUAGE_CODE_TO_INSTRUCTIONS,
            get_readable_llm_name,
        )
        from characters.resources.newsapi import get_news

        news = get_news()

        if not news:
            # Fallback if we couldn't get news
            additional_instructions = (
                _DEFAULT_ADDITIONAL_INSTRUCTIONS
                + "\n\nYou were supposed to talk about the news, but there was an error "
                "and you couldn't retrieve it. Explain and offer to talk about something else."
            )
            # Use smalltalk-style formatting
            additional_instructions_formatted = f"""
{additional_instructions}

# CONTEXT
It's currently {datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M")} in your timezone ({datetime.datetime.now().astimezone().tzname()}).

# START THE CONVERSATION
Repond to the user's message with a greeting and some kind of conversation starter.
"""
        else:
            articles = news.articles[:10]
            random.shuffle(articles)  # to avoid bias of the LLM
            articles_serialized = json.dumps([article.model_dump() for article in articles])

            instruction_prompt = self.instructions.get('instruction_prompt', '')
            additional_instructions_formatted = instruction_prompt.format(
                news=articles_serialized,
                current_time=datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M"),
                timezone=datetime.datetime.now().astimezone().tzname(),
            )

        return _SYSTEM_PROMPT_TEMPLATE.format(
            _SYSTEM_PROMPT_BASICS=_SYSTEM_PROMPT_BASICS,
            additional_instructions=additional_instructions_formatted,
            language_instructions=LANGUAGE_CODE_TO_INSTRUCTIONS.get(
                self.instructions.get('language')
            ),
            llm_name=get_readable_llm_name(),
        )
