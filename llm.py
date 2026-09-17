"""
LLM wrapper.
Uses Groq (free tier) as the primary LLM provider.
Falls back to a local Ollama server if GROQ_API_KEY is not set.
"""

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")


def _ask_groq(prompt: str, system: str | None, temperature: float) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _ask_ollama(prompt: str, system: str | None, temperature: float) -> str:
    import requests

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def ask_llm(prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
    """Send a prompt to the LLM and return text. Prefers Groq, falls back to Ollama."""
    if GROQ_API_KEY:
        return _ask_groq(prompt, system, temperature)
    return _ask_ollama(prompt, system, temperature)


if __name__ == "__main__":
    print("Testing LLM...")
    print(f"Provider: {'Groq' if GROQ_API_KEY else 'Ollama'}")
    reply = ask_llm("Reply with exactly: HELLO WORLD")
    print(f"Response: {reply}")