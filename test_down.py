import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import requests
from down import (
    clean_name,
    main,
    build_session,
    fetch_challenges,
    fetch_challenge_data,
    save_description,
    download_files,
)


class TestDown(unittest.TestCase):
    def test_clean_name_basic(self):
        self.assertEqual(clean_name("My Challenge"), "my-challenge")
        self.assertEqual(clean_name("Hello World!"), "hello-world")
        self.assertEqual(clean_name("123 ABC"), "123-abc")

    def test_clean_name_invalid_chars(self):
        self.assertEqual(clean_name("C@T$F&D!"), "ctfd")
        self.assertEqual(clean_name("A_B+C"), "abc")

    def test_clean_name_leading_hyphens(self):
        self.assertEqual(clean_name("  Test"), "test")
        self.assertEqual(clean_name("   -Test"), "test")

    def test_clean_name_multiple_hyphens(self):
        self.assertEqual(clean_name("A  B  C"), "a-b-c")
        self.assertEqual(clean_name("A--B--C"), "a-b-c")

    def test_clean_name_empty(self):
        name = ""
        result = clean_name(name)
        self.assertTrue(result.startswith("unnamed-"))
        self.assertEqual(len(result), len("unnamed-") + 8)

    def test_clean_name_only_invalid(self):
        name = "@@@"
        result = clean_name(name)
        self.assertTrue(result.startswith("unnamed-"))
        self.assertEqual(len(result), len("unnamed-") + 8)

    def test_clean_name_unicode(self):
        self.assertEqual(clean_name("Café — Test"), "caf-test")

    def test_clean_name_md5_fallback_deterministic(self):
        name = "@@@"
        result = clean_name(name)
        expected = 'unnamed-' + \
            __import__('hashlib').md5(name.encode()).hexdigest()[:8]
        self.assertEqual(result, expected)

    @patch("down.requests.Session")
    @patch("down.os.makedirs")
    @patch("down.os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_main_downloads_challenge(self, mock_file, mock_exists, mock_makedirs, mock_session):
        mock_exists.return_value = False
        mock_makedirs.return_value = None

        mock_s = MagicMock()
        mock_session.return_value = mock_s

        challenges_response = MagicMock()
        challenges_response.status_code = 200
        challenges_response.json.return_value = {
            "data": [
                {"id": 1, "name": "Test Challenge", "category": "Misc"}
            ]
        }
        challenges_response.__enter__.return_value = challenges_response

        challenge_detail_response = MagicMock()
        challenge_detail_response.status_code = 200
        challenge_detail_response.json.return_value = {
            "data": {
                "description": "Test description",
                "files": ["/files/test.txt"]
            }
        }
        challenge_detail_response.__enter__.return_value = challenge_detail_response

        file_response = MagicMock()
        file_response.__enter__.return_value = file_response
        file_response.iter_content.return_value = [b"data"]
        file_response.status_code = 200

        mock_s.get.side_effect = [
            challenges_response,
            challenge_detail_response,
            file_response
        ]

        main("http://ctfd", "token", None, "output_dir")

        self.assertGreaterEqual(mock_makedirs.call_count, 2)
        mock_file.assert_any_call(
            "output_dir/misc/test-challenge/description.md", "w"
        )
        mock_file.assert_any_call(
            "output_dir/misc/test-challenge/test.txt", "wb"
        )

    @patch("down.requests.Session")
    @patch("down.os.makedirs")
    @patch("down.os.path.exists")
    def test_main_skips_download_if_exists(self, mock_exists, mock_makedirs, mock_session):
        mock_exists.return_value = True
        mock_makedirs.return_value = None
        mock_s = MagicMock()
        mock_session.return_value = mock_s

        challenges_response = MagicMock()
        challenges_response.status_code = 200
        challenges_response.json.return_value = {
            "data": [
                {"id": 1, "name": "Test Challenge", "category": "Misc"}
            ]
        }
        mock_s.get.return_value = challenges_response

        main("http://ctfd", "token", None, "output_dir")
        self.assertEqual(mock_s.get.call_count, 1)

    def test_main_sets_auth_and_cookie(self):
        fake_session = MagicMock()
        fake_session.headers = {}
        fake_session.cookies = {}

        challenges_response = MagicMock()
        challenges_response.status_code = 200
        challenges_response.json.return_value = {"data": []}
        challenges_response.__enter__.return_value = challenges_response

        fake_session.get.return_value = challenges_response

        with patch('down.requests.Session', return_value=fake_session):
            main('http://ctfd', 'mytoken', 'mycookie', 'out')

        self.assertIn('Authorization', fake_session.headers)
        self.assertEqual(
            fake_session.headers['Authorization'], 'Token mytoken')
        self.assertIn('session', fake_session.cookies)
        self.assertEqual(fake_session.cookies['session'], 'mycookie')

    def test_build_session_sets_headers_and_cookies(self):
        s = build_session('tkn', 'cookieval')
        self.assertEqual(s.headers.get('Authorization'), 'Token tkn')
        self.assertEqual(s.cookies.get('session'), 'cookieval')
        self.assertEqual(s.headers.get('Content-Type'), 'application/json')

    def test_fetch_challenges_success_and_failure(self):
        mock_s = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'data': [{'id': 1}]}
        resp.__enter__.return_value = resp
        mock_s.get.return_value = resp

        result = fetch_challenges(mock_s, 'http://ctfd')
        self.assertEqual(result, [{'id': 1}])

        resp2 = MagicMock()
        resp2.status_code = 500
        resp2.__enter__.return_value = resp2
        mock_s.get.return_value = resp2
        result2 = fetch_challenges(mock_s, 'http://ctfd')
        self.assertIsNone(result2)

    def test_fetch_challenge_data_success_and_failure(self):
        mock_s = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'data': {'description': 'd', 'files': []}}
        resp.__enter__.return_value = resp
        mock_s.get.return_value = resp

        data = fetch_challenge_data(mock_s, 'http://ctfd', 1)
        self.assertEqual(data, {'description': 'd', 'files': []})

        resp2 = MagicMock()
        resp2.status_code = 404
        resp2.__enter__.return_value = resp2
        mock_s.get.return_value = resp2
        data2 = fetch_challenge_data(mock_s, 'http://ctfd', 1)
        self.assertIsNone(data2)

    @patch('builtins.open', new_callable=mock_open)
    def test_save_description_writes_file(self, m_open):
        save_description('outdir', 'hello')
        m_open.assert_called_with(os.path.join(
            'outdir', 'description.md'), 'w')
        handle = m_open()
        handle.write.assert_called_with('hello')

    @patch('builtins.open', new_callable=mock_open)
    def test_download_files_writes_files(self, m_open):
        mock_s = MagicMock()
        file_resp = MagicMock()
        file_resp.__enter__.return_value = file_resp
        file_resp.iter_content.return_value = [b'data']
        file_resp.status_code = 200

        mock_s.get.return_value = file_resp

        files = ['/files/test.txt']
        download_files(mock_s, 'http://ctfd', files, 'outdir',
                       max_workers=1, show_spinner=False)

        m_open.assert_called_with(os.path.join('outdir', 'test.txt'), 'wb')

    def test_fetch_challenges_handles_request_exception(self):
        mock_s = MagicMock()
        mock_s.get.side_effect = requests.exceptions.ConnectionError('conn')
        result = fetch_challenges(mock_s, 'http://ctfd')
        self.assertIsNone(result)

    def test_fetch_challenge_data_handles_request_exception(self):
        mock_s = MagicMock()
        mock_s.get.side_effect = requests.exceptions.Timeout('timeout')
        result = fetch_challenge_data(mock_s, 'http://ctfd', 1)
        self.assertIsNone(result)

    @patch('builtins.open', new_callable=mock_open)
    def test_download_files_handles_request_exception(self, m_open):
        mock_s = MagicMock()
        mock_s.get.side_effect = requests.exceptions.RequestException('fail')
        files = ['/files/test.txt']
        download_files(mock_s, 'http://ctfd', files, 'outdir',
                       max_workers=1, show_spinner=False)
        m_open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
