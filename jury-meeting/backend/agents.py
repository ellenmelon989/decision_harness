"""Jury agents — persona-driven, fed by the decision record.

A "juror" is just a dict pulled from the record (ultimately the team's DB):
  {agent_id, name, role, weight, voice_id, stance, score, rationale}

Each juror can, both @weave.op so they show up in the trace:
  - explain(juror, record): voice its stored position to the subject.
  - answer(question, juror, record): respond to a live follow-up, grounded ONLY
    in its stored rationale (no inventing new reasons).
"""
from __future__ import annotations

import json

import weave

from llm import chat

# Stock ElevenLabs voices, assigned by seat order when a juror has no voice_id.
DEFAULT_VOICES = [
    "EXAVITQu4vr4xnSDxMaL",  # Sarah
    "onwK4e9ZLuTAKqWW03F9",  # Daniel
    "pFZP5JQG7iQjIQuC4Bku",  # Lily
    "TX3LPaxmHKxFdv7VOQHJ",  # Liam
    "XB0fDUnXU5powFXDhCwa",  # Charlotte
    "pNInz6obpgDQGcFmaJgB",  # Adam
]


def voice_for(juror: dict, index: int) -> str:
    return juror.get("voice_id") or DEFAULT_VOICES[index % len(DEFAULT_VOICES)]


def _subject_brief(record: dict) -> str:
    s = record.get("subject", {})
    return (
        f"Subject under review: {s.get('title')}\n"
        f"Summary: {s.get('summary')}\n"
        f"Details: {json.dumps(s.get('details', {}), indent=2)}"
    )


def _juror_brief(juror: dict) -> str:
    return (
        f"You are {juror['name']}, {juror.get('role', 'a juror')} on the panel.\n"
        f"Your stance: {juror.get('stance')} (score {juror.get('score')}/10, "
        f"panel weight {juror.get('weight')}).\n"
        f"Your stored rationale: {juror.get('rationale')}"
    )


_EXPLAIN_SYS = (
    "You are a member of a decision jury, speaking aloud in a feedback meeting with the "
    "team/founder behind the subject you reviewed. Speak in first person, conversational, "
    "2-3 sentences, as if on a call. Deliver ONLY your own verdict, grounded in your stored "
    "rationale — do not invent new reasons. No preamble like 'As a juror'; just talk."
)

_ANSWER_SYS = (
    "You are a member of a decision jury on a live call with the team/founder behind the "
    "subject you reviewed. Answer their question in first person, 2-4 sentences, "
    "conversational. Stay grounded in YOUR stored rationale and the subject below. If the "
    "question is outside what you evaluated, briefly say so and defer to a colleague. NEVER "
    "invent new reasons for your verdict that your rationale does not support."
)


def _turn(juror: dict, index: int, kind: str, text: str) -> dict:
    return {
        "speaker": juror["name"],
        "role": juror.get("role", ""),
        "agent_id": juror.get("agent_id"),
        "voice_id": voice_for(juror, index),
        "stance": juror.get("stance"),
        "score": juror.get("score"),
        "kind": kind,
        "text": text,
    }


@weave.op
def explain(juror: dict, record: dict, index: int = 0) -> dict:
    """A juror voices its stored position to the subject's team."""
    user = (
        f"{_subject_brief(record)}\n\n{_juror_brief(juror)}\n\n"
        "Deliver your verdict to them in your own voice."
    )
    text = chat(_EXPLAIN_SYS, user, temperature=0.6, max_tokens=200)
    return _turn(juror, index, "opening", text)


@weave.op
def answer(question: str, juror: dict, record: dict, index: int = 0) -> dict:
    """A juror answers a live follow-up, grounded in its rationale."""
    user = (
        f"{_subject_brief(record)}\n\n{_juror_brief(juror)}\n\n"
        f"Their question: {question}\n\nAnswer them directly, grounded in your rationale."
    )
    text = chat(_ANSWER_SYS, user, temperature=0.55, max_tokens=260)
    return _turn(juror, index, "answer", text)
