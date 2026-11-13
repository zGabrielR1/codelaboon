import json
import unittest
from unittest.mock import MagicMock, patch

from codelaboon.local_router import choose


class RouterTests(unittest.TestCase):
    def test_only_valid_job_can_be_selected(self):
        candidates = [{'task': 'one', 'stage': 'plan', 'harness': 'cloud'}]
        for selected in (-1, 1, True, '0', None):
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps({
                'choices': [{'message': {'content': json.dumps({'job': selected})}}]}).encode()
            opener = MagicMock()
            opener.open.return_value = response
            with patch('urllib.request.build_opener', return_value=opener):
                with self.assertRaises(ValueError):
                    choose({'url': 'http://127.0.0.1:18765/v1/chat/completions',
                            'model': 'local'}, candidates)

    def test_remote_or_credentialed_endpoints_refused(self):
        for url in ('https://cloud.example/v1', 'http://localhost:80',
                    'http://127.0.0.1.attacker.example/', 'http://token@127.0.0.1/'):
            with self.assertRaises(ValueError):
                choose({'url': url, 'model': 'local'}, [{'task': 'one'}])


if __name__ == '__main__':
    unittest.main()
