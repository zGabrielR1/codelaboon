"""Offline smoke and unit tests for the codelaboon harness."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ORIGINAL_CONFIG_DIR = os.environ.get("CODELABOON_CONFIG_DIR")
_TMPDIR = tempfile.TemporaryDirectory()
os.environ["CODELABOON_CONFIG_DIR"] = _TMPDIR.name

from config.providers import get_providers_config, save_provider_config  # noqa: E402
from codelaboon.cli import CodelaboonCLI  # noqa: E402
from codelaboon.decision import (  # noqa: E402
    ChoiceAnswer,
    ChoiceOption,
    ChoiceQuestion,
    DecisionError,
    PredicateAnswer,
    PredicateQuestion,
    ScoreAnswer,
    ScoreLevel,
    ScoreQuestion,
    answer_to_dict,
    build_body,
    format_answers,
    parse_question_spec,
    parse_response,
    questions_from_data,
)
from providers.chatgpt.chatgpt_provider import ChatGPTProvider  # noqa: E402
from providers.luna.luna_provider import LunaProvider  # noqa: E402
from providers.nvidia.nvidia_provider import NVIDIAProvider  # noqa: E402
from providers.openrouter.openrouter_provider import OpenRouterProvider  # noqa: E402


def tearDownModule():
    if _ORIGINAL_CONFIG_DIR is None:
        os.environ.pop("CODELABOON_CONFIG_DIR", None)
    else:
        os.environ["CODELABOON_CONFIG_DIR"] = _ORIGINAL_CONFIG_DIR
    _TMPDIR.cleanup()


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class ConfigTests(unittest.TestCase):
    def test_default_config_is_created_with_restrictive_permissions(self):
        config_dir = Path(os.environ["CODELABOON_CONFIG_DIR"])

        config = get_providers_config()

        self.assertEqual(set(config), {"chatgpt", "nvidia", "openrouter", "luna"})
        self.assertTrue((config_dir / "providers.toml").is_file())
        self.assertEqual((config_dir / "providers.toml").stat().st_mode & 0o777, 0o600)

    def test_save_provider_config_roundtrips(self):
        self.assertTrue(
            save_provider_config("openrouter", {"api_key": "test-key", "models": ["a/b"]})
        )
        reloaded = get_providers_config()
        self.assertEqual(reloaded["openrouter"]["api_key"], "test-key")
        self.assertEqual(reloaded["openrouter"]["models"], ["a/b"])


class DoctorTests(unittest.TestCase):
    def test_doctor_passes_on_a_clean_checkout(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertTrue(CodelaboonCLI().doctor())
        self.assertIn("Doctor passed.", out.getvalue())


class ProviderTests(unittest.TestCase):
    def test_default_model_lists_are_non_empty(self):
        for provider_class in (ChatGPTProvider, NVIDIAProvider, OpenRouterProvider, LunaProvider):
            with self.subTest(provider=provider_class.__name__):
                provider = provider_class(api_key="", models=[])
                models = provider.list_models()
                self.assertTrue(models)

    def test_chat_requires_a_key(self):
        provider = OpenRouterProvider(api_key="", models=["model"])
        with self.assertRaises(ValueError):
            provider.chat("model", [{"role": "user", "content": "hi"}])

    def test_chat_sends_expected_payload(self):
        payload = {"choices": [{"message": {"content": "hello back"}}]}
        with mock.patch("requests.post", return_value=FakeResponse(payload)) as request:
            provider = ChatGPTProvider(api_key="test-key", models=["gpt-x"])
            answer = provider.chat("gpt-x", [{"role": "user", "content": "hi"}], temperature=0)

        self.assertEqual(answer, "hello back")
        _, kwargs = request.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "gpt-x")

    def test_chat_surfaces_api_errors(self):
        fake = FakeResponse({"error": "nope"}, status_code=429)
        with mock.patch("requests.post", return_value=fake):
            provider = NVIDIAProvider(api_key="test-key", models=["model"])
            with self.assertRaises(Exception):
                provider.chat("model", [{"role": "user", "content": "hi"}])


class DecisionModelTests(unittest.TestCase):
    def setUp(self):
        self.questions = [
            PredicateQuestion("refund", "Is the customer asking for a refund?"),
            ChoiceQuestion(
                "department",
                "Which team should handle this?",
                [ChoiceOption("billing"), ChoiceOption("technical")],
            ),
            ScoreQuestion(
                "urgency",
                "How urgent is this?",
                [ScoreLevel("Can wait"), ScoreLevel("High")],
            ),
        ]

    def test_questions_validate_and_require_unique_names(self):
        questions = questions_from_data(
            [
                {"name": "ok", "type": "predicate", "instructions": "OK?"},
                {
                    "name": "team",
                    "type": "choice",
                    "instructions": "Team?",
                    "choices": [{"value": "a"}, {"value": True}],
                },
            ]
        )
        self.assertEqual(questions[1].choices[1].value, True)
        with self.assertRaises(DecisionError):
            questions_from_data(
                [
                    {"name": "dup", "type": "predicate", "instructions": "A?"},
                    {"name": "dup", "type": "predicate", "instructions": "B?"},
                ]
            )

    def test_inline_question_specs(self):
        predicate = parse_question_spec("predicate", "ok=Is this OK?")
        choice = parse_question_spec("choice", "team=Which team?|billing,technical")
        score = parse_question_spec("score", "urgency=How urgent?|Low,High")
        self.assertIsInstance(predicate, PredicateQuestion)
        self.assertEqual([c.value for c in choice.choices], ["billing", "technical"])
        self.assertEqual([level.label for level in score.levels], ["Low", "High"])

    def test_openai_body_and_parse(self):
        body = build_body("openai", "model-x", "hello", self.questions)
        self.assertEqual(body["input"][0]["content"][0]["text"], "hello")
        payload = {
            "answers": [
                {"type": "predicate", "name": "refund", "probability": 0.91},
                {
                    "type": "choice",
                    "name": "department",
                    "choice": "billing",
                    "probabilities": [
                        {"value": "billing", "probability": 0.8},
                        {"value": "technical", "probability": 0.2},
                    ],
                    "confidence": 0.7,
                },
                {
                    "type": "score",
                    "name": "urgency",
                    "score": 1.2,
                    "probabilities": [
                        {"value": 0, "label": "Can wait", "probability": 0.3},
                        {"value": 1, "label": "High", "probability": 0.7},
                    ],
                    "confidence": 0.6,
                },
            ]
        }
        answers = parse_response("openai", payload, self.questions)
        self.assertIsInstance(answers[0], PredicateAnswer)
        self.assertAlmostEqual(answers[0].probability, 0.91)
        self.assertIsInstance(answers[1], ChoiceAnswer)
        self.assertEqual(answers[1].choice, "billing")
        self.assertIsInstance(answers[2], ScoreAnswer)
        self.assertEqual(answers[2].score, 1.2)
        self.assertIn("refund (predicate)", format_answers(answers))
        self.assertEqual(answer_to_dict(answers[1])["choice"], "billing")

    def test_systemone_rejects_colliding_choice_values(self):
        question = ChoiceQuestion(
            "flag",
            "Pick one",
            [ChoiceOption(True), ChoiceOption("true")],
        )
        with self.assertRaises(DecisionError):
            build_body("systemone", "model-x", "hello", [question])

    def test_systemone_body_and_parse(self):
        body = build_body("systemone", "model-x", "hello", self.questions)
        self.assertEqual(body["state"], "hello")
        self.assertEqual(body["questions"]["refund"]["type"], "noul")
        self.assertEqual(body["questions"]["department"]["criteria"]["billing"], None)
        payload = {
            "model": "model-x",
            "answers": {
                "refund": {"type": "noul", "noul": 0.91},
                "department": {
                    "type": "choice",
                    "choice": "billing",
                    "probabilities": {"billing": 0.8, "technical": 0.2},
                    "confidence": 0.7,
                },
                "urgency": {
                    "type": "score",
                    "score": 1.2,
                    "probabilities": {"0": 0.3, "1": 0.7},
                    "confidence": 0.6,
                },
            },
        }
        answers = parse_response("systemone", payload, self.questions)
        self.assertAlmostEqual(answers[0].probability, 0.91)
        self.assertEqual(answers[1].choice, "billing")
        self.assertEqual([p[0] for p in answers[1].probabilities], ["billing", "technical"])
        self.assertEqual(answers[2].probabilities[1][1], "High")

    def test_openai_provider_posts_to_decisions(self):
        payload = {
            "answers": [{"type": "predicate", "name": "refund", "probability": 0.5}]
        }
        with mock.patch("requests.post", return_value=FakeResponse(payload)) as request:
            provider = ChatGPTProvider(api_key="key", models=["m"])
            answers = provider.decision("m", "hello", [self.questions[0]])
        self.assertEqual(request.call_args.args[0], "https://api.openai.com/v1/decisions")
        self.assertEqual(answers[0].probability, 0.5)

    def test_openrouter_provider_posts_to_systemone(self):
        payload = {
            "answers": {"refund": {"type": "noul", "noul": 0.5}}
        }
        with mock.patch("requests.post", return_value=FakeResponse(payload)) as request:
            provider = OpenRouterProvider(api_key="key", models=["m"])
            answers = provider.decision("m", "hello", [self.questions[0]])
        self.assertEqual(
            request.call_args.args[0], "https://openrouter.ai/api/v1/systemone"
        )
        self.assertEqual(answers[0].probability, 0.5)

    def test_provider_without_decision_route_raises(self):
        provider = NVIDIAProvider(api_key="key", models=["m"])
        self.assertFalse(provider.supports_decisions())
        with self.assertRaises(NotImplementedError):
            provider.decision("m", "hello", [self.questions[0]])


if __name__ == "__main__":
    unittest.main()
