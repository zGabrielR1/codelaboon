"""Typed decision questions and provider wire protocols.

A decision request asks a model to answer one or more typed questions about an
input: a yes/no ``predicate`` (returned as a probability), a ``choice`` from a
list of values, or a ``score`` on ordered levels. Answers that a host declines
are represented as ``ErrorAnswer`` without discarding the other answers.

Two wire protocols are supported:

- ``openai``: OpenAI's ``/v1/decisions`` schema.
- ``systemone``: System One's ``/systemone`` schema, used by OpenRouter.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

ChoiceValue = Union[str, bool]


class DecisionError(ValueError):
    """Raised for invalid decision questions or responses."""


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


@dataclass
class PredicateQuestion:
    name: str
    instructions: str
    type: str = field(default="predicate", init=False)


@dataclass
class ChoiceOption:
    value: ChoiceValue
    description: Optional[str] = None


@dataclass
class ChoiceQuestion:
    name: str
    instructions: str
    choices: List[ChoiceOption]
    type: str = field(default="choice", init=False)


@dataclass
class ScoreLevel:
    label: str
    description: Optional[str] = None


@dataclass
class ScoreQuestion:
    name: str
    instructions: str
    levels: List[ScoreLevel]
    type: str = field(default="score", init=False)


Question = Union[PredicateQuestion, ChoiceQuestion, ScoreQuestion]


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------


@dataclass
class PredicateAnswer:
    name: str
    probability: float
    type: str = field(default="predicate", init=False)


@dataclass
class ChoiceAnswer:
    name: str
    choice: ChoiceValue
    probabilities: List[Tuple[ChoiceValue, float]]
    confidence: float
    type: str = field(default="choice", init=False)


@dataclass
class ScoreAnswer:
    name: str
    score: float
    probabilities: List[Tuple[int, str, float]]
    confidence: float
    type: str = field(default="score", init=False)


@dataclass
class ErrorAnswer:
    name: str
    reason: str
    message: Optional[str] = None
    type: str = field(default="error", init=False)


Answer = Union[PredicateAnswer, ChoiceAnswer, ScoreAnswer, ErrorAnswer]


def _probability(value: Any, field_name: str = "probability") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DecisionError(f"{field_name} must be a number") from exc
    if not 0.0 <= number <= 1.0:
        raise DecisionError(f"{field_name} must be between 0 and 1")
    return number


def _number(value: Any, field_name: str = "score") -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DecisionError(f"{field_name} must be a number") from exc


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionError("question name must be a non-empty string")
    return value.strip()


def question_from_dict(raw: Dict[str, Any]) -> Question:
    """Build a typed question from JSON-style data."""
    if not isinstance(raw, dict):
        raise DecisionError("each question must be a JSON object")

    name = _name(raw.get("name"))
    kind = raw.get("type")
    instructions = raw.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        raise DecisionError(f"question '{name}' needs non-empty instructions")

    if kind == "predicate":
        return PredicateQuestion(name, instructions)

    if kind == "choice":
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise DecisionError(f"choice question '{name}' needs a non-empty choices list")
        options: List[ChoiceOption] = []
        seen = set()
        for item in choices:
            if isinstance(item, dict):
                value = item.get("value")
                description = item.get("description")
            else:
                value, description = item, None
            if not isinstance(value, (str, bool)):
                raise DecisionError(f"choice '{name}' values must be strings or booleans")
            if value in seen:
                raise DecisionError(f"choice question '{name}' has duplicate value {value!r}")
            seen.add(value)
            if description is not None and not isinstance(description, str):
                raise DecisionError(f"choice '{name}' description must be a string")
            options.append(ChoiceOption(value, description))
        return ChoiceQuestion(name, instructions, options)

    if kind == "score":
        levels = raw.get("levels")
        if not isinstance(levels, list) or not levels:
            raise DecisionError(f"score question '{name}' needs a non-empty levels list")
        parsed: List[ScoreLevel] = []
        for item in levels:
            if isinstance(item, dict):
                label = item.get("label")
                description = item.get("description")
            else:
                label, description = item, None
            if not isinstance(label, str) or not label.strip():
                raise DecisionError(f"score level for '{name}' needs a non-empty label")
            if description is not None and not isinstance(description, str):
                raise DecisionError(f"score level description for '{name}' must be a string")
            parsed.append(ScoreLevel(label, description))
        return ScoreQuestion(name, instructions, parsed)

    raise DecisionError(f"question '{name}' has unknown type {kind!r}")


def questions_from_data(data: Any) -> List[Question]:
    """Validate a JSON-style list of questions and enforce unique names."""
    if not isinstance(data, list) or not data:
        raise DecisionError("questions must be a non-empty list")
    questions = [question_from_dict(item) for item in data]
    names = [question.name for question in questions]
    if len(set(names)) != len(names):
        raise DecisionError("question names must be unique")
    return questions


def questions_from_json(path: str) -> List[Question]:
    """Load questions from a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise DecisionError(f"could not read questions file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DecisionError(f"invalid questions JSON: {exc}") from exc
    return questions_from_data(data)


def parse_question_spec(kind: str, spec: str) -> Question:
    """Parse an inline question specification.

    Forms:
      predicate: NAME=INSTRUCTIONS
      choice:    NAME=INSTRUCTIONS|VALUE1,VALUE2
      score:     NAME=INSTRUCTIONS|LABEL1,LABEL2
    """
    if "=" not in spec:
        raise DecisionError(f"--{kind} expects NAME=INSTRUCTIONS")
    name, rest = spec.split("=", 1)
    name = _name(name)

    if kind == "predicate":
        if not rest.strip():
            raise DecisionError("predicate instructions cannot be empty")
        return PredicateQuestion(name, rest.strip())

    if kind not in ("choice", "score"):
        raise DecisionError(f"unknown inline question kind: {kind}")

    if "|" not in rest:
        suffix = "VALUE1,VALUE2" if kind == "choice" else "LABEL1,LABEL2"
        raise DecisionError(f"--{kind} expects NAME=INSTRUCTIONS|{suffix}")
    instructions, values = rest.split("|", 1)
    if not instructions.strip():
        raise DecisionError(f"{kind} instructions cannot be empty")
    items = [item.strip() for item in values.split(",")]
    if not items or any(not item for item in items):
        raise DecisionError(f"{kind} needs a non-empty comma-separated list")

    if kind == "choice":
        return ChoiceQuestion(name, instructions.strip(), [ChoiceOption(item) for item in items])
    return ScoreQuestion(name, instructions.strip(), [ScoreLevel(item) for item in items])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


def openai_body(model: str, input_text: str, questions: Sequence[Question]) -> Dict[str, Any]:
    """Build an OpenAI ``/v1/decisions`` request body."""
    encoded: List[Dict[str, Any]] = []
    for question in questions:
        if isinstance(question, PredicateQuestion):
            encoded.append(
                {"name": question.name, "type": "predicate", "instructions": question.instructions}
            )
        elif isinstance(question, ChoiceQuestion):
            encoded.append(
                {
                    "name": question.name,
                    "type": "choice",
                    "instructions": question.instructions,
                    "choices": [
                        {
                            "value": option.value,
                            **({"description": option.description} if option.description else {}),
                        }
                        for option in question.choices
                    ],
                }
            )
        else:
            encoded.append(
                {
                    "name": question.name,
                    "type": "score",
                    "instructions": question.instructions,
                    "levels": [
                        {
                            "label": level.label,
                            **({"description": level.description} if level.description else {}),
                        }
                        for level in question.levels
                    ],
                }
            )

    return {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
        "questions": encoded,
    }


def _systemone_key(value: ChoiceValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def systemone_body(model: str, input_text: str, questions: Sequence[Question]) -> Dict[str, Any]:
    """Build a System One ``/systemone`` request body."""
    encoded: Dict[str, Any] = {}
    for question in questions:
        if isinstance(question, PredicateQuestion):
            encoded[question.name] = {"type": "noul", "instructions": question.instructions}
        elif isinstance(question, ChoiceQuestion):
            keys = [_systemone_key(option.value) for option in question.choices]
            if len(set(keys)) != len(keys):
                raise DecisionError(
                    f"System One choice question '{question.name}' has values that collide as strings"
                )
            encoded[question.name] = {
                "type": "choice",
                "instructions": question.instructions,
                "criteria": {
                    _systemone_key(option.value): option.description for option in question.choices
                },
            }
        else:
            encoded[question.name] = {
                "type": "score",
                "instructions": question.instructions,
                "criteria": [
                    level.label if level.description is None else f"{level.label}: {level.description}"
                    for level in question.levels
                ],
            }

    return {"model": model, "state": input_text, "questions": encoded}


def build_body(protocol: str, model: str, input_text: str, questions: Sequence[Question]) -> Dict[str, Any]:
    if protocol == "openai":
        return openai_body(model, input_text, questions)
    if protocol == "systemone":
        return systemone_body(model, input_text, questions)
    raise DecisionError(f"unknown decision protocol: {protocol}")


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _openai_answer(question: Question, raw: Dict[str, Any]) -> Answer:
    kind = raw.get("type")
    if kind == "refusal":
        return ErrorAnswer(
            question.name,
            reason="refusal",
            message=raw.get("message"),
        )

    if isinstance(question, PredicateQuestion) and kind == "predicate":
        return PredicateAnswer(question.name, _probability(raw.get("probability")))

    if isinstance(question, ChoiceQuestion) and kind == "choice":
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, list):
            raise DecisionError(f"choice answer '{question.name}' has no probabilities")
        values = [option.value for option in question.choices]

        def choose(value: Any) -> ChoiceValue:
            for candidate in values:
                if candidate == value or str(candidate) == str(value):
                    return candidate
            raise DecisionError(f"unknown choice value {value!r} for '{question.name}'")

        parsed: List[Tuple[ChoiceValue, float]] = []
        for item in probabilities:
            if not isinstance(item, dict):
                raise DecisionError(f"invalid probability entry for '{question.name}'")
            parsed.append(
                (choose(item.get("value")), _probability(item.get("probability")))
            )
        return ChoiceAnswer(
            question.name,
            choose(raw.get("choice")),
            parsed,
            _probability(raw.get("confidence"), "confidence"),
        )

    if isinstance(question, ScoreQuestion) and kind == "score":
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, list):
            raise DecisionError(f"score answer '{question.name}' has no probabilities")
        parsed_scores: List[Tuple[int, str, float]] = []
        for item in probabilities:
            if not isinstance(item, dict):
                raise DecisionError(f"invalid score probability for '{question.name}'")
            index = item.get("value")
            if not isinstance(index, int) or isinstance(index, bool):
                raise DecisionError(f"score index for '{question.name}' must be an integer")
            label = item.get("label")
            if not isinstance(label, str):
                if 0 <= index < len(question.levels):
                    label = question.levels[index].label
                else:
                    raise DecisionError(f"score index {index} is out of range for '{question.name}'")
            parsed_scores.append((index, label, _probability(item.get("probability"))))
        return ScoreAnswer(
            question.name,
            _number(raw.get("score")),
            sorted(parsed_scores),
            _probability(raw.get("confidence"), "confidence"),
        )

    raise DecisionError(f"answer for '{question.name}' has unexpected type {kind!r}")


def parse_openai_response(payload: Dict[str, Any], questions: Sequence[Question]) -> List[Answer]:
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        raise DecisionError("OpenAI decision response has no answers")
    by_name = {
        answer.get("name"): answer
        for answer in payload["answers"]
        if isinstance(answer, dict) and isinstance(answer.get("name"), str)
    }
    answers: List[Answer] = []
    for question in questions:
        raw = by_name.get(question.name)
        if raw is None:
            answers.append(ErrorAnswer(question.name, "missing", "host returned no answer"))
        else:
            answers.append(_openai_answer(question, raw))
    return answers


def _systemone_answer(question: Question, raw: Dict[str, Any]) -> Answer:
    kind = raw.get("type")
    if isinstance(question, PredicateQuestion) and kind == "noul":
        return PredicateAnswer(question.name, _probability(raw.get("noul")))

    if isinstance(question, ChoiceQuestion) and kind == "choice":
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, dict):
            raise DecisionError(f"choice answer '{question.name}' has no probabilities")
        by_key = {_systemone_key(option.value): option.value for option in question.choices}
        choice_key = _systemone_key(raw.get("choice"))
        if choice_key not in by_key:
            raise DecisionError(f"unknown choice {raw.get('choice')!r} for '{question.name}'")
        parsed = [
            (by_key[key], _probability(value))
            for key, value in probabilities.items()
            if key in by_key
        ]
        return ChoiceAnswer(
            question.name,
            by_key[choice_key],
            parsed,
            _probability(raw.get("confidence"), "confidence"),
        )

    if isinstance(question, ScoreQuestion) and kind == "score":
        probabilities = raw.get("probabilities")
        if not isinstance(probabilities, dict):
            raise DecisionError(f"score answer '{question.name}' has no probabilities")
        parsed_scores: List[Tuple[int, str, float]] = []
        for key, value in probabilities.items():
            try:
                index = int(key)
            except (TypeError, ValueError) as exc:
                raise DecisionError(f"invalid score index {key!r} for '{question.name}'") from exc
            if not 0 <= index < len(question.levels):
                raise DecisionError(f"score index {index} is out of range for '{question.name}'")
            parsed_scores.append((index, question.levels[index].label, _probability(value)))
        return ScoreAnswer(
            question.name,
            _number(raw.get("score")),
            sorted(parsed_scores),
            _probability(raw.get("confidence"), "confidence"),
        )

    raise DecisionError(f"answer for '{question.name}' has unexpected type {kind!r}")


def parse_systemone_response(payload: Dict[str, Any], questions: Sequence[Question]) -> List[Answer]:
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise DecisionError("System One decision response has no answers")
    answers: List[Answer] = []
    for question in questions:
        raw = payload["answers"].get(question.name)
        if not isinstance(raw, dict):
            answers.append(ErrorAnswer(question.name, "missing", "host returned no answer"))
        else:
            answers.append(_systemone_answer(question, raw))
    return answers


def parse_response(protocol: str, payload: Dict[str, Any], questions: Sequence[Question]) -> List[Answer]:
    if protocol == "openai":
        return parse_openai_response(payload, questions)
    if protocol == "systemone":
        return parse_systemone_response(payload, questions)
    raise DecisionError(f"unknown decision protocol: {protocol}")


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def answer_to_dict(answer: Answer) -> Dict[str, Any]:
    if isinstance(answer, PredicateAnswer):
        return {"name": answer.name, "type": answer.type, "probability": answer.probability}
    if isinstance(answer, ChoiceAnswer):
        return {
            "name": answer.name,
            "type": answer.type,
            "choice": answer.choice,
            "probabilities": [
                {"value": value, "probability": probability}
                for value, probability in answer.probabilities
            ],
            "confidence": answer.confidence,
        }
    if isinstance(answer, ScoreAnswer):
        return {
            "name": answer.name,
            "type": answer.type,
            "score": answer.score,
            "probabilities": [
                {"value": index, "label": label, "probability": probability}
                for index, label, probability in answer.probabilities
            ],
            "confidence": answer.confidence,
        }
    return {
        "name": answer.name,
        "type": answer.type,
        "reason": answer.reason,
        "message": answer.message,
    }


def format_answers(answers: Iterable[Answer]) -> str:
    lines: List[str] = []
    for answer in answers:
        if isinstance(answer, PredicateAnswer):
            lines.append(f"{answer.name} (predicate): {answer.probability:.4f}")
        elif isinstance(answer, ChoiceAnswer):
            lines.append(
                f"{answer.name} (choice): {answer.choice} (confidence {answer.confidence:.4f})"
            )
            for value, probability in answer.probabilities:
                lines.append(f"  {value}: {probability:.4f}")
        elif isinstance(answer, ScoreAnswer):
            lines.append(
                f"{answer.name} (score): {answer.score:g} (confidence {answer.confidence:.4f})"
            )
            for index, label, probability in answer.probabilities:
                lines.append(f"  {index} {label}: {probability:.4f}")
        else:
            message = f": {answer.message}" if answer.message else ""
            lines.append(f"{answer.name} (error): {answer.reason}{message}")
    return "\n".join(lines)
