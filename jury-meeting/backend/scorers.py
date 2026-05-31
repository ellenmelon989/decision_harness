"""Weave scorers + an Evaluation over the jury Q&A.

This is the "not a black box" story: we don't just produce answers, we grade
them. Two things matter for an auditable feedback meeting:

  - relevance:    did the orchestrator route the question to the right juror?
  - faithfulness: did the juror's answer stay inside its stored rationale, or did
                  it invent new reasons for the verdict? (the dangerous failure)

Run:  python backend/scorers.py   ->  prints a shareable Weave Evaluation URL.
"""
from __future__ import annotations

import asyncio
import json

import weave
from dotenv import load_dotenv

import orchestrator
from llm import PROJECT_PATH, chat

load_dotenv()


@weave.op
def score_relevance(expected_juror: str, output: dict) -> dict:
    """1.0 if the question was routed to the expected juror."""
    routed = (output or {}).get("routed_to")
    return {"correct": routed == expected_juror, "routed_to": routed}


@weave.op
def score_faithfulness(output: dict) -> dict:
    """LLM-judge: is the answer fully supported by the stored rationale?

    Penalizes hallucinated reasons — the thing that would make the feedback
    meeting untrustworthy.
    """
    if not output:
        return {"faithful": 0.0}
    sys = (
        "You are a strict grader auditing a jury's feedback. Given a juror's stored "
        "RATIONALE and the ANSWER they gave, decide if every claim in the answer is "
        "supported by the rationale (and general non-controversial framing). Return JSON "
        '{"faithful": 0.0-1.0, "reason": "..."}. Score 1.0 only if no new reason was '
        "invented."
    )
    user = (
        f"RATIONALE:\n{output.get('_rationale', '')}\n\n"
        f"ANSWER:\n{output.get('text', '')}\n\nJSON:"
    )
    raw = chat(sys, user, temperature=0.0, max_tokens=160)
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        return {"faithful": float(data.get("faithful", 0.0)), "reason": data.get("reason", "")}
    except Exception:
        return {"faithful": 0.0, "reason": f"unparseable judge output: {raw[:80]}"}


class JuryModel(weave.Model):
    """Wraps the orchestrator so Weave can evaluate it over a dataset."""

    record: dict

    @weave.op
    def predict(self, question: str) -> dict:
        turn = orchestrator.ask(question, self.record)
        # attach the rationale the routed juror was supposed to stay within
        by_name = {j["name"]: j for j in self.record["jurors"]}
        turn["_rationale"] = by_name.get(turn["routed_to"], {}).get("rationale", "")
        return turn


# A tiny eval set: question -> the juror who SHOULD field it (matches sample_decision.json).
EVAL_ROWS = [
    {"question": "Why is my market too unfocused if it's a $900B space?", "expected_juror": "Dana Okafor"},
    {"question": "My team is ex-Instacart and ex-DoorDash — wasn't that strong enough?", "expected_juror": "Marcus Lee"},
    {"question": "Couldn't ChatGPT just copy my fridge-photo feature?", "expected_juror": "Elena Vasquez"},
    {"question": "Is my 9% week-4 retention really that bad?", "expected_juror": "Sam Whitfield"},
    {"question": "You said my pitch was confusing — what was unclear?", "expected_juror": "Aisha Bello"},
]


async def run_eval() -> None:
    weave.init(PROJECT_PATH)
    record = orchestrator.load_record()
    model = JuryModel(record=record)
    evaluation = weave.Evaluation(
        dataset=EVAL_ROWS,
        scorers=[score_relevance, score_faithfulness],
        name="jury-feedback-qa",
    )
    await evaluation.evaluate(model)
    print("\nEvaluation complete — open the Weave URL above to see relevance/faithfulness.")


if __name__ == "__main__":
    asyncio.run(run_eval())
