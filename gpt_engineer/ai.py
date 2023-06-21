from __future__ import annotations

import logging
import os

import openai

from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)


class AI:
    def __init__(self, model="gpt-4", **kwargs):
        self.temperature = kwargs.get("temperature", 0.1)
        self.max_tokens = kwargs.get("max_tokens", 4096)

        try:
            openai.Model.retrieve(model)
            self.model = model
        except openai.InvalidRequestError:
            print(
                f"Model {model} not available for provided API key. Reverting "
                f"to {kwargs.get('model')}. Sign up for the GPT-4 wait list here: "
                "https://openai.com/waitlist/gpt-4-api"
            )
            self.model = kwargs.get("model", "gpt-3.5-turbo")

    def start(self, system, user):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        return self.next(messages)

    def fsystem(self, msg):
        return {"role": "system", "content": msg}

    def fuser(self, msg):
        return {"role": "user", "content": msg}

    def fassistant(self, msg):
        return {"role": "assistant", "content": msg}

    def next(self, messages: list[dict[str, str]], prompt=None):
        if prompt:
            messages += [{"role": "user", "content": prompt}]

        logger.debug(f"Creating a new chat completion: {messages}")
        response = openai.ChatCompletion.create(
            messages=messages,
            stream=True,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        chat = []
        for chunk in response:
            delta = chunk["choices"][0]["delta"] # type: ignore
            msg = delta.get("content", "")
            print(msg, end="")
            chat.append(msg)
        print()
        messages += [{"role": "assistant", "content": "".join(chat)}]
        logger.debug(f"Chat completion finished: {messages}")
        return messages
