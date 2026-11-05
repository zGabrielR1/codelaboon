"""Offline smoke and unit tests for the codelaboon harness."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
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
from providers.kilo.kilo_provider import (  # noqa: E402
    DEFAULT_BASE_URL as DEFAULT_KILO_BASE_URL,
    KiloProvider,
)
from providers.luna.luna_provider import LunaProvider  # noqa: E402
from providers.nvidia.nvidia_provider import NVIDIAProvider  # noqa: E402
from providers.openrouter.openrouter_provider import OpenRouterProvider  # noqa: E402
from providers.ourfree.ourfree_provider import (  # noqa: E402
    DEFAULT_BASE_URL,
    OurFreeModelProvider,
)
from providers.base import BaseProvider  # noqa: E402

try:  # The TUI is an optional extra; tests skip cleanly without it.
    from codelaboon.tui import CodelaboonTuiApp

    TEXTUAL_AVAILABLE = True
except ImportError:
    CodelaboonTuiApp = None
    TEXTUAL_AVAILABLE = False


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

        self.assertEqual(
            set(config),
            {"chatgpt", "nvidia", "openrouter", "luna", "ourfree", "kilo"},
        )
        self.assertTrue((config_dir / "providers.toml").is_file())
        if os.name == "posix":
            self.assertEqual(
                (config_dir / "providers.toml").stat().st_mode & 0o777, 0o600
            )

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
        for provider_class in (
            ChatGPTProvider, NVIDIAProvider, OpenRouterProvider, LunaProvider,
            OurFreeModelProvider, KiloProvider
        ):
            with self.subTest(provider=provider_class.__name__):
                provider = provider_class(api_key="", models=[])
                models = provider.list_models()
                if provider_class is ChatGPTProvider:
                    self.assertEqual(models, [])
                else:
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


class OurFreeModelTests(unittest.TestCase):
    """Tests for the dsh-our-free-model forward gateway provider."""

    def test_list_models_discovers_from_the_gateway(self):
        payload = {
            "object": "list",
            "data": [
                {"id": "deepseek-v4.1-flash-free", "object": "model", "owned_by": "our-free-model"},
                {"id": "kimi-k3", "object": "model", "owned_by": "our-free-model"},
            ],
        }
        with mock.patch("requests.get", return_value=FakeResponse(payload)) as get:
            provider = OurFreeModelProvider(api_key="ofm-test", models=["pinned"])
            models = provider.list_models()

        self.assertEqual(models, ["deepseek-v4.1-flash-free", "kimi-k3"])
        self.assertEqual(get.call_args.args[0], f"{DEFAULT_BASE_URL}/models")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer ofm-test")

    def test_list_models_falls_back_to_configured_when_gateway_is_down(self):
        with mock.patch(
            "requests.get", side_effect=requests.ConnectionError("connection refused")
        ):
            provider = OurFreeModelProvider(api_key="ofm-test", models=["pinned-model"])
            models = provider.list_models()

        self.assertEqual(models, ["pinned-model"])

    def test_list_models_falls_back_to_defaults_without_a_key(self):
        with mock.patch("requests.get") as get:
            provider = OurFreeModelProvider(api_key="", models=[])
            models = provider.list_models()

        get.assert_not_called()
        self.assertEqual(models, provider.default_models)

    def test_base_url_override_is_honored(self):
        provider = OurFreeModelProvider(api_key="ofm-test", base_url="http://127.0.0.1:18900/v1/")
        self.assertEqual(provider.base_url, "http://127.0.0.1:18900/v1")

    def test_chat_posts_to_the_gateway(self):
        payload = {"choices": [{"message": {"content": "hello from the gateway"}}]}
        with mock.patch("requests.post", return_value=FakeResponse(payload)) as request:
            provider = OurFreeModelProvider(api_key="ofm-test", models=["m"])
            answer = provider.chat("m", [{"role": "user", "content": "hi"}])

        self.assertEqual(answer, "hello from the gateway")
        self.assertEqual(
            request.call_args.args[0], f"{DEFAULT_BASE_URL}/chat/completions"
        )
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer ofm-test")
        self.assertEqual(request.call_args.kwargs["json"]["model"], "m")

    def test_chat_requires_a_key(self):
        provider = OurFreeModelProvider(api_key="", models=["m"])
        with self.assertRaises(ValueError):
            provider.chat("m", [{"role": "user", "content": "hi"}])

    def test_cli_passes_base_url_from_config_through(self):
        cli = CodelaboonCLI()
        with mock.patch(
            "config.providers.get_providers_config",
            return_value={
                "ourfree": {
                    "api_key": "ofm-test",
                    "base_url": "http://127.0.0.1:18900/v1",
                    "models": ["m"],
                }
            },
        ):
            cli.load_providers()

        provider = cli.providers["ourfree"]
        self.assertEqual(provider.base_url, "http://127.0.0.1:18900/v1")

    def test_cli_ignores_blank_base_url(self):
        cli = CodelaboonCLI()
        with mock.patch(
            "config.providers.get_providers_config",
            return_value={
                "ourfree": {"api_key": "ofm-test", "base_url": "  ", "models": ["m"]}
            },
        ):
            cli.load_providers()

        provider = cli.providers["ourfree"]
        self.assertEqual(provider.base_url, DEFAULT_BASE_URL)


class KiloTests(unittest.TestCase):
    """Tests for the keyless Kilo AI free-pool provider."""

    LISTING = {
        "data": [
            {"id": "kilo-auto/free", "name": "Kilo Auto (free)", "isFree": True},
            {"id": "nvidia/nemotron-3-ultra:free", "name": "NVIDIA: Nemotron 3 Ultra (free)", "isFree": True},
            {"id": "z-ai/glm-5.3", "name": "GLM 5.3", "isFree": False},
            {"id": "openrouter/free", "name": "OpenRouter Auto (free)", "isFree": True},
            {"isFree": True},  # A row without an id is not a model.
        ]
    }

    def test_is_keyless(self):
        provider = KiloProvider(api_key="", models=[])
        self.assertTrue(provider.keyless)
        self.assertTrue(provider.validate_api_key())

    def test_list_models_filters_the_free_slice(self):
        with mock.patch("requests.get", return_value=FakeResponse(self.LISTING)) as get:
            provider = KiloProvider(api_key="", models=[])
            models = provider.list_models()

        self.assertEqual(
            models, ["kilo-auto/free", "nvidia/nemotron-3-ultra:free", "openrouter/free"]
        )
        self.assertEqual(get.call_args.args[0], f"{DEFAULT_KILO_BASE_URL}/models")
        self.assertNotIn("Authorization", get.call_args.kwargs["headers"])

    def test_list_models_tolerates_bare_list_envelope(self):
        rows = [
            {"id": "cohere/x", "isFree": True},
            {"id": "paid/y", "isFree": False},
        ]
        with mock.patch("requests.get", return_value=FakeResponse(rows)):
            provider = KiloProvider(api_key="", models=["pinned"])
            models = provider.list_models()

        self.assertEqual(models, ["cohere/x"])

    def test_list_models_falls_back_when_the_gateway_is_down(self):
        with mock.patch(
            "requests.get", side_effect=requests.ConnectionError("no route")
        ):
            provider = KiloProvider(api_key="", models=["pinned-model"])
            models = provider.list_models()

        self.assertEqual(models, ["pinned-model"])

    def test_chat_requires_no_key(self):
        document = json.dumps({"choices": [{"message": {"content": "free answer"}}]})

        class JsonStreamResponse(FakeResponse):
            def __init__(self, text):
                self._text = text
                self.status_code = 200

            def iter_content(self, chunk_size=None, decode_unicode=False):
                yield self._text

        with mock.patch("requests.post", return_value=JsonStreamResponse(document)):
            provider = KiloProvider(api_key="", models=["kilo-auto/free"])
            answer = provider.chat("kilo-auto/free", [{"role": "user", "content": "hi"}])

        self.assertEqual(answer, "free answer")

    def test_chat_parses_an_sse_stream_with_keepalives(self):
        sse = (
            ': KILO PROCESSING\n\n'
            'data: {"choices": [{"delta": {"content": "Hel"}}]}\n\n'
            ': KILO PROCESSING\n\n'
            'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n'
            'data: {"choices": [{"delta": {}}]}\n\n'
            'data: [DONE]\n\n'
        )

        class StreamResponse(FakeResponse):
            def __init__(self, text):
                self._text = text
                self.status_code = 200

            def iter_content(self, chunk_size=None, decode_unicode=False):
                yield self._text

        with mock.patch("requests.post", return_value=StreamResponse(sse)) as request:
            provider = KiloProvider(api_key="", models=["m"])
            answer = provider.chat("m", [{"role": "user", "content": "hi"}])

        self.assertEqual(answer, "Hello")
        self.assertEqual(
            request.call_args.args[0], f"{DEFAULT_KILO_BASE_URL}/chat/completions"
        )
        self.assertTrue(request.call_args.kwargs["json"]["stream"])

    def test_chat_parses_a_single_json_document_over_a_stream_request(self):
        document = json.dumps(
            {"choices": [{"message": {"content": "one document"}}]}
        )

        class JsonStreamResponse(FakeResponse):
            def __init__(self, text):
                self._text = text
                self.status_code = 200

            def iter_content(self, chunk_size=None, decode_unicode=False):
                yield self._text

        with mock.patch("requests.post", return_value=JsonStreamResponse(document)):
            provider = KiloProvider(api_key="", models=["m"])
            answer = provider.chat("m", [{"role": "user", "content": "hi"}])

        self.assertEqual(answer, "one document")

    def test_chat_surfaces_an_error_frame_inside_the_stream(self):
        sse = 'data: {"error": {"message": "moderation: flagged"}}\n\n'

        class StreamResponse(FakeResponse):
            def __init__(self, text):
                self._text = text
                self.status_code = 200

            def iter_content(self, chunk_size=None, decode_unicode=False):
                yield self._text

        with mock.patch("requests.post", return_value=StreamResponse(sse)):
            provider = KiloProvider(api_key="", models=["m"])
            with self.assertRaises(Exception) as raised:
                provider.chat("m", [{"role": "user", "content": "hi"}])

        self.assertIn("flagged", str(raised.exception))

    def test_chat_shapes_the_reasoning_parameter(self):
        payloads = []

        class RecordingResponse(FakeResponse):
            def __init__(self):
                self.status_code = 200
                self.text = "{}"

            def iter_content(self, chunk_size=None, decode_unicode=False):
                yield json.dumps({"choices": [{"message": {"content": "ok"}}]})

        def record(url, **kwargs):
            payloads.append(kwargs["json"])
            return RecordingResponse()

        provider = KiloProvider(api_key="", models=["m"])
        with mock.patch("requests.post", side_effect=record):
            provider.chat("m", [{"role": "user", "content": "hi"}])
            provider.chat("m", [{"role": "user", "content": "hi"}], reasoning="high")
            provider.chat("m", [{"role": "user", "content": "hi"}], reasoning="off")
        with self.assertRaises(ValueError):
            provider.chat("m", [{"role": "user", "content": "hi"}], reasoning="ultra")

        self.assertNotIn("reasoning", payloads[0])
        self.assertEqual(payloads[1]["reasoning"], {"effort": "high"})
        self.assertEqual(payloads[2]["reasoning"], {"enabled": False})

    def test_base_url_override_is_honored(self):
        provider = KiloProvider(api_key="", base_url="https://kilo.example/api/gateway/")
        self.assertEqual(provider.base_url, "https://kilo.example/api/gateway")

    def test_cli_shows_keyless_status(self):
        cli = CodelaboonCLI()
        with mock.patch(
            "config.providers.get_providers_config",
            return_value={"kilo": {"api_key": "", "models": []}},
        ):
            cli.load_providers()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            cli.list_providers()
        self.assertIn("Free (no key needed)", out.getvalue())


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


class TuiTests(unittest.IsolatedAsyncioTestCase):
    """Headless tests for the Textual TUI."""

    def test_tui_command_without_the_extra_exits_with_a_hint(self):
        with mock.patch.dict("sys.modules", {"codelaboon.tui": None}):
            with mock.patch("sys.argv", ["codelaboon", "tui"]):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    with self.assertRaises(SystemExit) as exited:
                        CodelaboonCLI().run()
        self.assertEqual(exited.exception.code, 2)
        self.assertIn("textual", out.getvalue())

    @unittest.skipUnless(TEXTUAL_AVAILABLE, "textual is not installed")
    async def test_mount_lists_providers_and_models(self):
        app = CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(len(app._provider_names), 6)
            if app._models_worker is not None:
                await app._models_worker.wait()
            await pilot.pause()
            self.assertEqual(app._model_names, [])
            self.assertIn(app._selected_provider(), app.cli.providers)

    @unittest.skipUnless(TEXTUAL_AVAILABLE, "textual is not installed")
    async def test_send_without_configuration_warns(self):
        app = CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            if app._models_worker is not None:
                await app._models_worker.wait()
            await pilot.pause()
            lines: list = []
            app._log = lines.append
            app._send("hello")
            await pilot.pause()
        self.assertTrue(any("not configured" in line for line in lines))

    @unittest.skipUnless(TEXTUAL_AVAILABLE, "textual is not installed")
    async def test_chat_roundtrip_against_a_fake_provider(self):
        class FakeTuiProvider(BaseProvider):
            def __init__(self):
                super().__init__(api_key="test-key", models=["fake-1"])

            def list_models(self):
                return ["fake-1"]

            def chat(self, model, messages, **kwargs):
                return f"echo:{messages[-1]['content']}"

        app = CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.cli.providers["fake"] = FakeTuiProvider()
            app._provider_names.append("fake")
            app._select_provider("fake")
            if app._models_worker is not None:
                await app._models_worker.wait()
            await pilot.pause()
            self.assertEqual(app._selected_model(), "fake-1")

            app._send("hi")
            if app._chat_worker is not None:
                await app._chat_worker.wait()
            await pilot.pause()
        self.assertEqual(app.history[-1], {"role": "assistant", "content": "echo:hi"})


if __name__ == "__main__":
    unittest.main()
