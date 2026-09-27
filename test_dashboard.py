import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.parse import parse_qs, urlparse

from flask import session as flask_session

import app as app_module
from app import app


def form_token(client):
    """Load the login form and return the CSRF token it embeds."""
    body = client.get('/auth/leetcode').get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    if match is None:
        raise AssertionError('login form is missing its CSRF token')
    return match.group(1)


def store_as(sid, provider, values):
    """Write credentials for a chosen session id, as a browser holding it would."""
    with app_module.app.test_request_context():
        flask_session[app_module.SID_SESSION_KEY] = sid
        app_module.store_credentials(provider, values)


def stored_by_sid(sid, provider):
    entry = app_module._CREDENTIAL_STORE.get(sid) or {}
    return dict(entry.get('providers', {}).get(provider) or {})


def client_sid(client):
    with client.session_transaction() as session:
        return session.get(app_module.SID_SESSION_KEY)


def stored_for(client, provider):
    """Read a provider's server-side credentials the way the app looks them up."""
    return stored_by_sid(client_sid(client), provider)


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()

    def test_dashboard_endpoint_returns_payload(self):
        # Credentials in .env would otherwise turn this into a live API test.
        with mock.patch.object(app_module, 'github_integration', return_value=None), \
                mock.patch.object(app_module, 'leetcode_integration', return_value=None):
            response = self.client.get('/api/dashboard')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('greeting', payload)
        self.assertIn('time', payload)
        self.assertIn('github', payload)
        self.assertIn('leetcode', payload)
        self.assertIn('daily_summary', payload)
        self.assertFalse(payload['github']['connected'])
        self.assertFalse(payload['leetcode']['connected'])


class EnvFileTests(unittest.TestCase):
    def test_values_are_loaded_without_overriding_real_env(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as handle:
            handle.write(
                '# comment\n'
                'QUOTED="quoted value"\n'
                'export EXPORTED=exported\n'
                'SPACED = spaced \n'
                'EXISTING=from-file\n'
            )
            path = handle.name

        previous = os.environ.get('EXISTING')
        os.environ['EXISTING'] = 'from-environment'
        try:
            self.assertTrue(app_module.load_env_file(path))
            self.assertEqual(os.environ['QUOTED'], 'quoted value')
            self.assertEqual(os.environ['EXPORTED'], 'exported')
            self.assertEqual(os.environ['SPACED'], 'spaced')
            self.assertEqual(os.environ['EXISTING'], 'from-environment')
        finally:
            if previous is None:
                os.environ.pop('EXISTING', None)
            else:
                os.environ['EXISTING'] = previous
            for key in ('QUOTED', 'EXPORTED', 'SPACED'):
                os.environ.pop(key, None)
            os.unlink(path)

    def test_missing_file_is_not_an_error(self):
        self.assertFalse(app_module.load_env_file('/nonexistent/path/.env'))


class GitHubAuthTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        self.client = app_module.app.test_client()
        self.env = mock.patch.dict('os.environ', {
            'GITHUB_CLIENT_ID': 'client-id',
            'GITHUB_CLIENT_SECRET': 'client-secret',
            'GITHUB_REDIRECT_URI': 'http://localhost:5000/oauth/github/callback',
            'GITHUB_TOKEN': '',
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()

    def test_authorize_redirect_carries_credentials_and_state(self):
        response = self.client.get('/auth/github')
        self.assertEqual(response.status_code, 302)
        location = response.headers['Location']
        self.assertTrue(location.startswith('https://github.com/login/oauth/authorize?'))

        query = parse_qs(urlparse(location).query)
        self.assertEqual(query['client_id'], ['client-id'])
        self.assertEqual(query['scope'], ['read:user'])
        self.assertEqual(
            query['redirect_uri'], ['http://localhost:5000/oauth/github/callback']
        )

        with self.client.session_transaction() as session:
            state = session[app_module.OAUTH_STATE_KEY]
        self.assertEqual(query['state'], [state])
        self.assertGreaterEqual(len(state), 32)

    def test_authorize_without_credentials_reports_the_misconfiguration(self):
        with mock.patch.dict('os.environ', {'GITHUB_CLIENT_ID': '', 'GITHUB_CLIENT_SECRET': ''}):
            response = self.client.get('/auth/github')
        self.assertEqual(response.status_code, 400)
        self.assertIn('GITHUB_CLIENT_ID', response.get_json()['error'])

    def test_callback_rejects_a_callback_that_did_not_start_here(self):
        response = self.client.get('/oauth/github/callback?code=some-code')
        self.assertEqual(response.status_code, 400)
        self.assertIn('state mismatch', response.get_json()['error'])

    def test_callback_rejects_a_tampered_state(self):
        self.client.get('/auth/github')
        response = self.client.get('/oauth/github/callback?code=some-code&state=forged')
        self.assertEqual(response.status_code, 400)
        self.assertIn('state mismatch', response.get_json()['error'])

    def test_state_cannot_be_replayed(self):
        self.client.get('/auth/github')
        with self.client.session_transaction() as session:
            state = session[app_module.OAUTH_STATE_KEY]

        first = self.client.get('/oauth/github/callback?code=some-code&state=%s' % state)
        self.assertEqual(first.status_code, 400)

        # The one-shot nonce is spent, so a second attempt cannot ride along.
        with self.client.session_transaction() as session:
            self.assertNotIn(app_module.OAUTH_STATE_KEY, session)

    def test_callback_reports_a_denied_authorization(self):
        response = self.client.get(
            '/oauth/github/callback?error=access_denied&error_description=User+said+no'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['details'], 'User said no')

    @mock.patch.object(app_module, 'GitHubIntegration')
    def test_successful_callback_stores_the_token(self, integration_factory):
        integration = integration_factory.return_value
        integration.authenticate.return_value = {'login': 'octocat'}
        integration.get_access_token.return_value = 'gho_token'

        self.client.get('/auth/github')
        with self.client.session_transaction() as session:
            state = session[app_module.OAUTH_STATE_KEY]

        response = self.client.get('/oauth/github/callback?code=valid-code&state=%s' % state)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')

        stored = stored_for(self.client, 'github')
        self.assertEqual(stored['token'], 'gho_token')
        self.assertEqual(stored['username'], 'octocat')

        # The token must not travel back to the browser at all: the cookie holds
        # only the store id and non-secret UI state.
        with self.client.session_transaction() as session:
            self.assertNotIn('github_token', session)
            self.assertNotIn('github_username', session)
            sid = session[app_module.SID_SESSION_KEY]
        # The cookie value is only a lookup handle into the server-side store.
        self.assertIn(sid, app_module._CREDENTIAL_STORE)

        # redirect_uri has to match the authorize request or GitHub rejects the exchange.
        credentials = integration.authenticate.call_args[0][0]
        self.assertEqual(credentials['code'], 'valid-code')
        self.assertEqual(
            credentials['redirect_uri'], 'http://localhost:5000/oauth/github/callback'
        )

    @mock.patch.object(app_module, 'GitHubIntegration')
    def test_rejected_credentials_do_not_become_a_server_error(self, integration_factory):
        integration_factory.return_value.authenticate.side_effect = ValueError(
            'GitHub OAuth error: bad_verification_code'
        )

        self.client.get('/auth/github')
        with self.client.session_transaction() as session:
            state = session[app_module.OAUTH_STATE_KEY]

        response = self.client.get('/oauth/github/callback?code=stale&state=%s' % state)
        self.assertEqual(response.status_code, 400)

        with self.client.session_transaction() as session:
            self.assertNotIn('github_token', session)


class LeetCodeAuthTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        self.client = app_module.app.test_client()
        self.env = mock.patch.dict('os.environ', {
            'LEETCODE_SESSION': '',
            'LEETCODE_CSRF_TOKEN': '',
            'LEETCODE_USERNAME': '',
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()

    def test_login_page_asks_for_the_session_cookie(self):
        body = self.client.get('/auth/leetcode').get_data(as_text=True)
        self.assertIn('name="session_token"', body)
        self.assertIn('name="csrftoken"', body)

    def test_post_without_the_form_token_is_rejected(self):
        response = self.client.post('/auth/leetcode', data={'session_token': 'attacker-session'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('form expired', response.get_data(as_text=True))

    def test_post_with_a_forged_form_token_is_rejected(self):
        response = self.client.post(
            '/auth/leetcode', data={'session_token': 'attacker-session', 'csrf_token': 'forged'}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('form expired', response.get_data(as_text=True))

    def test_empty_cookie_is_rejected(self):
        response = self.client.post(
            '/auth/leetcode', data={'session_token': '  ', 'csrf_token': form_token(self.client)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Paste the LEETCODE_SESSION', response.get_data(as_text=True))

    @mock.patch.object(app_module, 'LeetCodeIntegration')
    def test_valid_cookie_is_stored(self, integration_factory):
        integration_factory.return_value.authenticate.return_value = 'octocat'

        response = self.client.post(
            '/auth/leetcode',
            data={
                'session_token': 'session-value',
                'csrftoken': 'csrf-value',
                'csrf_token': form_token(self.client),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')

        stored = stored_for(self.client, 'leetcode')
        self.assertEqual(stored['token'], 'session-value')
        self.assertEqual(stored['csrftoken'], 'csrf-value')
        self.assertEqual(stored['username'], 'octocat')

        with self.client.session_transaction() as session:
            self.assertNotIn('leetcode_token', session)

        credentials = integration_factory.return_value.authenticate.call_args[0][0]
        self.assertEqual(credentials['session_token'], 'session-value')
        self.assertEqual(credentials['csrftoken'], 'csrf-value')

    @mock.patch.object(app_module, 'LeetCodeIntegration')
    def test_expired_cookie_shows_the_error_on_the_form(self, integration_factory):
        integration_factory.return_value.authenticate.side_effect = ValueError(
            'LeetCode rejected the session cookie.'
        )

        response = self.client.post(
            '/auth/leetcode',
            data={'session_token': 'expired', 'csrf_token': form_token(self.client)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('LeetCode rejected the session cookie.', response.get_data(as_text=True))

        with self.client.session_transaction() as session:
            self.assertNotIn('leetcode_token', session)


class SessionIsolationTests(unittest.TestCase):
    """A shared integration instance must never leak data between sessions."""

    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()

    def test_logout_disconnects_even_when_env_has_credentials(self):
        env = mock.patch.dict('os.environ', {
            'LEETCODE_SESSION': 'env-session',
            'GITHUB_TOKEN': '',
        })
        env.start()
        try:
            integration = mock.Mock()
            integration.is_authenticated = True
            client = app_module.app.test_client()

            with mock.patch.object(
                app_module, 'LeetCodeIntegration', return_value=integration
            ), mock.patch.object(
                app_module, 'github_integration', return_value=None
            ):
                self.assertTrue(client.get('/api/auth/status').get_json()['leetcode_connected'])
                client.get('/logout')
                self.assertFalse(client.get('/api/auth/status').get_json()['leetcode_connected'])
        finally:
            env.stop()

    def test_instance_cache_is_keyed_per_token(self):
        first = mock.Mock()
        first.is_authenticated = False
        second = mock.Mock()
        second.is_authenticated = False
        first.authenticate.return_value = 'user-one'
        second.authenticate.return_value = 'user-two'

        with mock.patch.object(app_module, 'GitHubIntegration', side_effect=[first, second]):
            app_module._integration_for(app_module.GitHubIntegration, 'token-one', None)
            app_module._integration_for(app_module.GitHubIntegration, 'token-two', None)

        first.authenticate.assert_called_once_with('token-one')
        second.authenticate.assert_called_once_with('token-two')

    def test_rejected_token_is_not_cached(self):
        integration = mock.Mock()
        integration.is_authenticated = False
        integration.authenticate.side_effect = ValueError('rejected')

        with mock.patch.object(app_module, 'GitHubIntegration', return_value=integration):
            self.assertIsNone(app_module._integration_for(app_module.GitHubIntegration, 'bad', None))
        self.assertEqual(app_module._INTEGRATIONS, {})


class SecretKeyTests(unittest.TestCase):
    def test_strong_key_is_used_as_is(self):
        key = 'k' * 40
        with mock.patch.dict('os.environ', {'SECRET_KEY': key}):
            self.assertEqual(app_module.resolve_secret_key(), (key, None))

    def test_placeholder_key_is_replaced_and_reported(self):
        with mock.patch.dict('os.environ', {'SECRET_KEY': 'change_me'}):
            resolved, warning = app_module.resolve_secret_key()
        self.assertNotEqual(resolved, 'change_me')
        self.assertGreaterEqual(len(resolved), 32)
        self.assertIn('placeholder', warning)

    def test_short_key_is_replaced_and_reported(self):
        with mock.patch.dict('os.environ', {'SECRET_KEY': 'abc'}):
            resolved, warning = app_module.resolve_secret_key()
        self.assertNotEqual(resolved, 'abc')
        self.assertIn('too short', warning)

    def test_missing_key_is_replaced_and_reported(self):
        with mock.patch.dict('os.environ', {'SECRET_KEY': ''}):
            resolved, warning = app_module.resolve_secret_key()
        self.assertGreaterEqual(len(resolved), 32)
        self.assertIn('not set', warning)

    def test_replacement_keys_differ_between_runs(self):
        with mock.patch.dict('os.environ', {'SECRET_KEY': 'change_me'}):
            first, _ = app_module.resolve_secret_key()
        with mock.patch.dict('os.environ', {'SECRET_KEY': 'change_me'}):
            second, _ = app_module.resolve_secret_key()
        self.assertNotEqual(first, second)


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        app_module._CREDENTIAL_STORE.clear()
        app_module.app.config['TESTING'] = True

    def tearDown(self):
        app_module._CREDENTIAL_STORE.clear()

    def test_credentials_are_scoped_to_one_browser(self):
        store_as('session-a', 'github', {'token': 'first-token'})
        store_as('session-b', 'github', {'token': 'second-token'})

        self.assertEqual(stored_by_sid('session-a', 'github')['token'], 'first-token')
        self.assertEqual(stored_by_sid('session-b', 'github')['token'], 'second-token')

    def test_logout_removes_the_stored_token(self):
        client = app_module.app.test_client()
        # The login form is what allocates a session id for this browser.
        client.get('/auth/leetcode')
        sid = client_sid(client)
        self.assertIsNotNone(sid)
        store_as(sid, 'github', {'token': 'a-token'})
        store_as(sid, 'leetcode', {'token': 'b-token'})

        client.get('/logout')
        self.assertEqual(app_module._CREDENTIAL_STORE, {})

    def test_reconnecting_replaces_the_old_token(self):
        store_as('session-a', 'github', {'token': 'old-token'})
        store_as('session-a', 'github', {'token': 'new-token'})
        self.assertEqual(stored_by_sid('session-a', 'github')['token'], 'new-token')

    def test_quiet_sessions_are_evicted(self):
        store_as('session-a', 'github', {'token': 'a-token'})
        stale = app_module._CREDENTIAL_STORE['session-a']
        stale['touched'] = datetime.now(timezone.utc) - timedelta(
            seconds=app_module.CREDENTIAL_TTL_SECONDS + 1
        )

        store_as('session-b', 'leetcode', {'token': 'b-token'})
        self.assertNotIn('session-a', app_module._CREDENTIAL_STORE)
        self.assertIn('session-b', app_module._CREDENTIAL_STORE)

    def test_store_is_capped(self):
        original = app_module.MAX_CREDENTIAL_SESSIONS
        app_module.MAX_CREDENTIAL_SESSIONS = 2
        try:
            for index in range(5):
                store_as('session-%d' % index, 'github', {'token': 'a-token'})
            self.assertLessEqual(len(app_module._CREDENTIAL_STORE), 2)
        finally:
            app_module.MAX_CREDENTIAL_SESSIONS = original
            app_module._CREDENTIAL_STORE.clear()

    def test_integration_cache_is_capped(self):
        original = app_module.MAX_INTEGRATION_INSTANCES
        app_module.MAX_INTEGRATION_INSTANCES = 2
        try:
            for index in range(6):
                integration = mock.Mock()
                integration.is_authenticated = False
                with mock.patch.object(
                    app_module, 'GitHubIntegration', return_value=integration
                ):
                    app_module._integration_for(
                        app_module.GitHubIntegration, 'token-%d' % index, None
                    )
            self.assertLessEqual(len(app_module._INTEGRATIONS), 2)
        finally:
            app_module.MAX_INTEGRATION_INSTANCES = original
            app_module._INTEGRATIONS.clear()


class ProviderIsolationTests(unittest.TestCase):
    """One provider failing must not take the rest of the dashboard down."""

    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()

    def _leetcode_failing_with(self, error):
        integration = mock.Mock()
        integration.is_authenticated = True
        integration.core_functionality.side_effect = error
        return integration

    def test_graphql_error_does_not_fail_the_dashboard(self):
        integration = self._leetcode_failing_with(
            RuntimeError("LeetCode GraphQL error: Cannot query field 'nope'")
        )
        with mock.patch.object(app_module, 'LeetCodeIntegration', return_value=integration):
            response = self.client.get('/api/dashboard')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['leetcode']['connected'])

    def test_github_still_reports_when_leetcode_fails(self):
        good = mock.Mock()
        good.is_authenticated = True
        good.core_functionality.return_value = {
            'user': {'login': 'octocat', 'public_repos': 3},
            'contributions': {'total': 7, 'current_streak': 2,
                              'days': [{'date': 'x', 'count': 4}]},
            'repositories': [{'name': 'my-daily-driver'}],
        }
        broken = self._leetcode_failing_with(RuntimeError('schema changed'))

        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'a-token'}), \
                mock.patch.object(app_module, 'GitHubIntegration', return_value=good), \
                mock.patch.object(app_module, 'LeetCodeIntegration', return_value=broken):
            payload = self.client.get('/api/dashboard').get_json()

        self.assertTrue(payload['github']['connected'])
        self.assertEqual(payload['github']['username'], 'octocat')
        self.assertEqual(payload['github']['current_streak'], 2)
        self.assertEqual(payload['github']['top_repo'], 'my-daily-driver')
        self.assertTrue(payload['github']['commit_today'])

    def test_login_reports_a_graphql_error_instead_of_crashing(self):
        integration = mock.Mock()
        integration.authenticate.side_effect = RuntimeError('LeetCode GraphQL error: bad field')

        with mock.patch.object(app_module, 'LeetCodeIntegration', return_value=integration):
            token = form_token(self.client)
            response = self.client.post(
                '/auth/leetcode', data={'session_token': 'a-token', 'csrf_token': token}
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn('GraphQL error', response.get_data(as_text=True))


class EnvFlagTests(unittest.TestCase):
    def test_recognised_true_values(self):
        for raw in ('1', 'true', 'TRUE', 'yes', 'on'):
            with mock.patch.dict('os.environ', {'FLASK_DEBUG': raw}):
                self.assertTrue(app_module.env_flag('FLASK_DEBUG'), raw)

    def test_unset_and_false_values(self):
        with mock.patch.dict('os.environ', {'FLASK_DEBUG': ''}):
            self.assertFalse(app_module.env_flag('FLASK_DEBUG'))
        with mock.patch.dict('os.environ', {'FLASK_DEBUG': '0'}):
            self.assertFalse(app_module.env_flag('FLASK_DEBUG'))

    def test_default_is_used_when_unset(self):
        with mock.patch.dict('os.environ', {'SOME_FLAG': ''}):
            self.assertTrue(app_module.env_flag('SOME_FLAG', default=True))

    def test_server_binds_to_loopback_without_configuration(self):
        with mock.patch.object(app_module.app, 'run') as run:
            with mock.patch.dict('os.environ', {'HOST': '', 'PORT': '', 'FLASK_DEBUG': ''}):
                app_module.main()
        run.assert_called_once_with(host='127.0.0.1', port=5000, debug=False)

    def test_debug_on_a_public_host_warns(self):
        with mock.patch.object(app_module.app, 'run'):
            with mock.patch.dict(
                'os.environ', {'HOST': '0.0.0.0', 'FLASK_DEBUG': '1', 'PORT': '5000'}
            ), mock.patch('sys.stderr') as stderr:
                app_module.main()
        self.assertIn('Werkzeug debugger', ''.join(call.args[0] for call in stderr.write.call_args_list))


if __name__ == '__main__':
    unittest.main()
