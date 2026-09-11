"""Intelligence layer: dedup/cluster raw articles, summarize them in Persian
via a pluggable LLM, rank them, and turn the day's top stories into an audio
digest via a pluggable TTS engine.

Every external dependency here (embedding model, LLM, TTS engine) sits
behind a small Protocol so the concrete provider is a one-line swap — see
``dedup.Embedder``, ``llm_provider.LLMProvider``, and ``tts_provider.TTSProvider``.
"""
