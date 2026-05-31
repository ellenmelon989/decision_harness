"""CLI entrypoint: run a sample AI-jury feedback meeting end-to-end.

    python backend/main.py

Prints opening statements + a couple of routed Q&A answers, and the Weave trace
URL. The whole meeting is one nested trace you can open and audit.
"""
from __future__ import annotations

import weave
from dotenv import load_dotenv

import orchestrator
from llm import PROJECT_PATH

load_dotenv()

SAMPLE_QUESTIONS = [
    "Why did you say my market is too unfocused? I'm going after a $900B space.",
    "My founding team is strong though, right? What would have changed your mind?",
]


def _print_turn(prefix: str, turn: dict) -> None:
    routed = f" (routed: {turn['routed_to']})" if turn.get("routed_to") else ""
    print(f"\n{prefix} {turn['speaker']} — {turn['role']}{routed}")
    print(f"  {turn['text']}")


def main() -> None:
    weave.init(PROJECT_PATH)

    record = orchestrator.load_record()
    # consider creating sample questions based on record.subject.summary or something, but for now we just hardcode a couple of good ones that trigger routing and interesting discussion.
    result = orchestrator.run_meeting(record, SAMPLE_QUESTIONS)

    print("=" * 72)
    print(f"MEETING {result['meeting_id']} — {result['subject']}")
    print(f"VERDICT: {result['verdict']}  (overall {result['overall_score']}/10)")
    print("=" * 72)

    # we gotta also play their pitch video initially before the opening statements, we have the video
    print("\n--- OPENING STATEMENTS ---")
    for turn in result["openings"]:
        _print_turn("•", turn)

    print("\n\n--- APPLICANT Q&A ---")
    for turn in result["qa"]:
        print(f"\nQ: {turn['question']}")
        _print_turn("→", turn)

    print("\n" + "=" * 72)
    print("Open the Weave trace for this run in the URL printed by weave.init above.")


if __name__ == "__main__":
    main()
