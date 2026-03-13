from __future__ import annotations

import ollama

from talky.prompting import build_llm_system_prompt


class OllamaTextCleaner:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def warm_up(self) -> None:
        ollama.generate(
            model=self.model_name,
            prompt="ping",
            options={"temperature": 0.0},
            keep_alive="1h",
        )

    def clean(self, raw_text: str, dictionary_terms: list[str]) -> str:
        system_prompt = build_llm_system_prompt(dictionary_terms)
        stream = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            think=False,
            stream=True,
            options={
                "temperature": 0,
                "num_predict": 300,
                "top_p": 0.1,
            },
            keep_alive="1h",
        )
        parts: list[str] = []
        thinking_parts: list[str] = []
        for chunk in stream:
            message = chunk.get("message", {})
            piece = message.get("content", "") or ""
            thinking_piece = message.get("thinking", "") or ""
            if thinking_piece:
                print(thinking_piece, end="", flush=True)
                thinking_parts.append(thinking_piece)
            if piece:
                print(piece, end="", flush=True)
                parts.append(piece)
        print()
        final = "".join(parts).strip()
        if final:
            return final
        # Never surface model thinking as final content.
        # If content stream is empty, preserve the source transcript instead.
        return raw_text.strip()
