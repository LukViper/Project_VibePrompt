"""Linguistic preprocessing.

Transformer models should receive lightly cleaned text. Aggressive stop-word
removal and stemming are reserved for classical paths (TF-IDF baselines).
"""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior) instructions",
    r"reveal (your |the )?(system prompt|api key|hidden prompt)",
    r"you are now (a |an )?",
    r"disregard (the )?(system|developer) (prompt|message)",
]

STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "with",
    "is", "are", "be", "this", "that", "it", "as", "at", "by", "from",
}

_SPACY = None
_SPACY_TRIED = False


def detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in INJECTION_PATTERNS)


def _spacy():
    global _SPACY, _SPACY_TRIED
    if _SPACY_TRIED:
        return _SPACY
    _SPACY_TRIED = True
    try:
        import spacy

        try:
            _SPACY = spacy.load("en_core_web_sm")
        except Exception:
            _SPACY = spacy.blank("en")
            if "sentencizer" not in _SPACY.pipe_names:
                _SPACY.add_pipe("sentencizer")
    except Exception:
        _SPACY = None
    return _SPACY


def _simple_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _simple_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9+#.-]*", text)


def preprocess(text: str, for_transformer: bool = False) -> dict:
    """Return linguistic features.

    When ``for_transformer`` is true, only whitespace and control-character
    cleanup is applied. Sentence-transformer and NLI models keep their own
    tokenizers.
    """
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    injection = detect_prompt_injection(cleaned)
    if for_transformer:
        return {
            "text": cleaned,
            "sentences": _simple_sentences(cleaned),
            "tokens": [],
            "lemmas": [],
            "method": "identity",
            "prompt_injection": injection,
        }

    nlp = _spacy()
    if nlp is not None and nlp.pipe_names:
        doc = nlp(cleaned)
        sentences = [sent.text.strip() for sent in doc.sents] or _simple_sentences(cleaned)
        tokens = [token.text for token in doc if not token.is_space]
        content_tokens = [
            token.text.lower()
            for token in doc
            if not token.is_space and not token.is_punct and token.text.lower() not in STOPWORDS
        ]
        if doc.has_annotation("LEMMA"):
            lemmas = [token.lemma_.lower() for token in doc if not token.is_space and not token.is_punct]
            method = "spacy"
        else:
            lemmas = content_tokens
            method = "spacy-blank"
        features = {
            "sentence_count": len(sentences),
            "token_count": len(tokens),
            "entities": [
                {"text": ent.text, "label": ent.label_}
                for ent in getattr(doc, "ents", [])
            ],
        }
        return {
            "text": cleaned,
            "sentences": sentences,
            "tokens": tokens,
            "content_tokens": content_tokens,
            "lemmas": lemmas,
            "features": features,
            "method": method,
            "prompt_injection": injection,
        }

    tokens = _simple_tokens(cleaned)
    content_tokens = [token.lower() for token in tokens if token.lower() not in STOPWORDS]
    return {
        "text": cleaned,
        "sentences": _simple_sentences(cleaned),
        "tokens": tokens,
        "content_tokens": content_tokens,
        "lemmas": content_tokens,
        "features": {"sentence_count": len(_simple_sentences(cleaned)), "token_count": len(tokens), "entities": []},
        "method": "regex",
        "prompt_injection": injection,
    }
