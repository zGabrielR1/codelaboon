"""The free (Auto) ranking and failover contract."""

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from codelaboon import free_auto


class FakeProvider:
    keyless = True

    def __init__(self, models, reply="ok", error=None):
        self.models = list(models)
        self.default_models = list(models)
        self.reply = reply
        self.error = error
        self.calls = []

    def validate_api_key(self):
        return True

    def chat(self, model, messages, **kwargs):
        self.calls.append(model)
        if self.error:
            raise ValueError(self.error)
        return self.reply


class UnconfiguredProvider(FakeProvider):
    def validate_api_key(self):
        return False


class FreeAutoTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.dict("os.environ", CODELABOON_CONFIG_DIR=directory))

    def test_ranks_available_smart_models_first(self):
        ourfree = FakeProvider(["deepseek-v4.1-flash-free", "space-bunny-free"])
        providers = {"ourfree": ourfree}
        entries = free_auto.ranked(providers)
        self.assertTrue(entries)
        self.assertEqual(entries[0].provider, "ourfree")
        self.assertEqual(entries[0].model, "deepseek-v4.1-flash-free")

    def test_unconfigured_providers_are_excluded(self):
        providers = {"ourfree": UnconfiguredProvider(["deepseek-v4.1-flash-free"])}
        self.assertEqual(free_auto.ranked(providers), [])
        self.assertIsNone(free_auto.select(providers))

    def test_chat_uses_first_working_candidate_and_fails_over(self):
        class FailFirst(FakeProvider):
            def chat(self, model, messages, **kwargs):
                self.calls.append(model)
                if model == "deepseek-v4.1-flash-free":
                    raise ValueError("rate limited")
                return "ok"

        provider = FailFirst(["deepseek-v4.1-flash-free", "glm-5.3-flash-free"])
        providers = {"ourfree": provider}
        chosen, reply = free_auto.chat(providers, [{"role": "user", "content": "hi"}])
        self.assertEqual(reply, "ok")
        self.assertNotEqual(chosen.model, "deepseek-v4.1-flash-free")
        self.assertEqual(provider.calls[0], "deepseek-v4.1-flash-free")
        # Transient failures get one quick retry before failover.
        self.assertEqual(provider.calls[1], "deepseek-v4.1-flash-free")
        self.assertEqual(
            provider.calls[2],
            next(entry.model for entry in free_auto.ranked(providers) if entry.model != "deepseek-v4.1-flash-free"),
        )

    def test_rate_limit_tries_another_provider_before_retrying(self):
        limited = FakeProvider(["deepseek-v4.1-flash-free", "glm-5.3-flash-free"], error="429")
        fallback = FakeProvider(["kilo-auto/free"])
        with (
            patch.dict("os.environ", CODELABOON_MODEL_CHECKS="0", CODELABOON_METRICS="0"),
            patch("time.sleep") as sleep,
        ):
            chosen, _ = free_auto.chat({"ourfree": limited, "kilo": fallback}, [])
        self.assertEqual(chosen.provider, "kilo")
        self.assertEqual(limited.calls, ["deepseek-v4.1-flash-free"])
        sleep.assert_not_called()

    def test_chat_reports_every_failure(self):
        provider = FakeProvider(["deepseek-v4.1-flash-free"], error="boom")
        providers = {"ourfree": provider}
        with self.assertRaises(ValueError) as caught:
            free_auto.chat(providers, [])
        self.assertIn("boom", str(caught.exception))

    def test_no_free_lane_is_a_clear_error(self):
        with self.assertRaises(ValueError):
            free_auto.chat({}, [])


if __name__ == "__main__":
    unittest.main()
