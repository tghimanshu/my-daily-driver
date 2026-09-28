import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from urllib.parse import parse_qs, urlparse

from flask import session as flask_session

# Set before the app is imported, because importing it reads .env. Without this
# the suite picks up the developer's real credentials and makes live
# authenticated calls, so the result of a test run depends on what is in their
# .env and on having a network connection.
os.environ['DAILY_DRIVER_SKIP_DOTENV'] = '1'

import app as app_module
from app import app
from pomodoro import DEFAULTS, LIMITS, HISTORY_DAYS


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


def _accept_credentials(token):
    """An authenticate() stand-in that accepts a token without calling the API."""
    def fake(self, credentials):
        self._access_token = token
        self._is_authenticated = True
    return fake


def store_for(client, provider, values):
    """Store credentials for the session id this client is actually holding."""
    sid = client_sid(client)
    if sid is None:
        client.get('/api/auth/status')
        sid = client_sid(client)
    store_as(sid, provider, values)


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

        # This module sets the opt-out so the suite ignores the real .env, which
        # is the opposite of what this test is checking.
        previous_skip = os.environ.pop('DAILY_DRIVER_SKIP_DOTENV', None)
        previous = os.environ.get('EXISTING')
        os.environ['EXISTING'] = 'from-environment'
        try:
            self.assertTrue(app_module.load_env_file(path))
            self.assertEqual(os.environ['QUOTED'], 'quoted value')
            self.assertEqual(os.environ['EXPORTED'], 'exported')
            self.assertEqual(os.environ['SPACED'], 'spaced')
            self.assertEqual(os.environ['EXISTING'], 'from-environment')
        finally:
            if previous_skip is not None:
                os.environ['DAILY_DRIVER_SKIP_DOTENV'] = previous_skip
            if previous is None:
                os.environ.pop('EXISTING', None)
            else:
                os.environ['EXISTING'] = previous
            for key in ('QUOTED', 'EXPORTED', 'SPACED'):
                os.environ.pop(key, None)
            os.unlink(path)

    def test_opt_out_ignores_the_file_entirely(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as handle:
            handle.write('SHOULD_NOT_BE_LOADED=nope\n')
            path = handle.name

        try:
            with mock.patch.dict(os.environ, {'DAILY_DRIVER_SKIP_DOTENV': '1'}):
                self.assertFalse(app_module.load_env_file(path))
            self.assertNotIn('SHOULD_NOT_BE_LOADED', os.environ)
        finally:
            os.environ.pop('SHOULD_NOT_BE_LOADED', None)
            os.unlink(path)

    def test_suite_does_not_inherit_real_credentials(self):
        """
        Importing the app runs load_env_file, so without the opt-out above the
        suite would pick up the developer's own .env and make live
        authenticated calls, making the run depend on their accounts.
        """
        leaked = sorted(
            key for key, value in os.environ.items()
            if value and (key.startswith('GITHUB_') or key.startswith('LEETCODE_')
                          or key == 'SELF_HOSTED_SITES')
        )
        self.assertEqual(leaked, [], 'test process inherited real settings: ' + ', '.join(leaked))

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
        body = response.get_data(as_text=True)
        self.assertIn('could not be verified', body)
        # The failure is explained rather than left as a bare status code.
        self.assertIn('What to check', body)
        self.assertIn('redirect_uri', body)

    def test_callback_rejects_a_tampered_state(self):
        self.client.get('/auth/github')
        response = self.client.get('/oauth/github/callback?code=some-code&state=forged')
        self.assertEqual(response.status_code, 400)
        self.assertIn('could not be verified', response.get_data(as_text=True))

    def test_state_failure_names_the_host_mismatch(self):
        # A login started on 127.0.0.1 and returned to localhost loses the cookie.
        response = self.client.get(
            '/oauth/github/callback?code=some-code&state=forged',
            base_url='http://127.0.0.1:5000',
        )
        body = response.get_data(as_text=True)
        self.assertIn('127.0.0.1:5000', body)
        self.assertIn('localhost:5000', body)

    def test_no_host_hint_when_hosts_agree(self):
        response = self.client.get(
            '/oauth/github/callback?code=some-code&state=forged',
            base_url='http://localhost:5000',
        )
        self.assertNotIn('different host', response.get_data(as_text=True))

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
        body = response.get_data(as_text=True)
        self.assertIn('declined the request', body)
        self.assertIn('User said no', body)

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
        self.assertIn('rejected the login', response.get_data(as_text=True))

        self.assertEqual(stored_for(self.client, 'github'), {})


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
            app_module._integration_for('github', app_module.GitHubIntegration, 'token-one', None)
            app_module._integration_for('github', app_module.GitHubIntegration, 'token-two', None)

        first.authenticate.assert_called_once_with('token-one')
        second.authenticate.assert_called_once_with('token-two')

    def test_rejected_token_is_not_cached(self):
        integration = mock.Mock()
        integration.is_authenticated = False
        integration.authenticate.side_effect = ValueError('rejected')

        with mock.patch.object(app_module, 'GitHubIntegration', return_value=integration):
            self.assertIsNone(app_module._integration_for('github', app_module.GitHubIntegration, 'bad', None))
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
                        'github', app_module.GitHubIntegration, 'token-%d' % index, None
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


class DisconnectionReasonTests(unittest.TestCase):
    """
    A provider that cannot be used has to say why.

    Reporting a bare "not connected" is what made a rejected token impossible to
    diagnose from the dashboard.
    """

    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()

    def _reject_api_calls(self, status=401):
        response = mock.Mock()
        response.status_code = status
        response.content = b'{}'
        response.headers = {}
        response.raise_for_status.side_effect = app_module.requests.HTTPError(
            '%d error' % status, response=response
        )
        return mock.Mock(return_value=response)

    def test_rejected_token_is_explained_in_the_payload(self):
        store_for(self.client, 'github', {'token': 'stale-token', 'username': 'octocat'})

        with mock.patch.object(
            app_module.requests, 'request', side_effect=self._reject_api_calls(401)
        ):
            reason = self.client.get('/api/dashboard').get_json()['github']['reason']

        self.assertIn('rejected', reason.lower())
        self.assertIn('expired', reason.lower())

    def test_rate_limit_is_explained(self):
        store_for(self.client, 'github', {'token': 'a-token'})
        with mock.patch.object(
            app_module.requests, 'request', side_effect=self._reject_api_calls(403)
        ):
            reason = self.client.get('/api/dashboard').get_json()['github']['reason']
        self.assertIn('rate limit', reason.lower())

    def test_missing_credential_is_explained(self):
        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': '', 'LEETCODE_SESSION': ''}):
            payload = self.client.get('/api/dashboard').get_json()
        self.assertIn('No GitHub token', payload['github']['reason'])
        self.assertIn('No LeetCode session', payload['leetcode']['reason'])

    def test_explicit_disconnect_is_explained(self):
        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'a-token'}):
            self.client.get('/logout')
            reason = self.client.get('/api/dashboard').get_json()['github']['reason']
        self.assertIn('Disconnected in this browser', reason)


class ConnectedAfterLoginTests(unittest.TestCase):
    """
    The dashboard must stay connected once a login has succeeded.

    A stored username used to be handed to GitHubIntegration in place of the
    token, which read as an OAuth code exchange and left the widget reporting
    "not connected" immediately after a successful login.
    """

    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()

    @staticmethod
    def _response(payload):
        response = mock.Mock()
        response.status_code = 200
        response.content = b'{}'
        response.headers = {}
        response.json.return_value = payload
        return response

    def _api(self, method, url, **kwargs):
        if 'leetcode' in url:
            return self._response({'data': None})
        if url.endswith('/user'):
            return self._response({'login': 'octocat', 'name': 'The Octocat'})
        if '/repos' in url:
            return self._response([{'name': 'hello-world', 'stargazers_count': 7}])
        return self._response([])

    def test_stored_username_does_not_displace_the_token(self):
        store_for(self.client, 'github', {'token': 'gho_valid', 'username': 'octocat'})

        with mock.patch.object(app_module.requests, 'request', side_effect=self._api):
            github = self.client.get('/api/dashboard').get_json()['github']

        self.assertTrue(github['connected'], github.get('reason'))
        self.assertEqual(github['username'], 'octocat')
        self.assertIsNone(github.get('reason'))

    def test_connected_status_survives_a_second_request(self):
        store_for(self.client, 'github', {'token': 'gho_valid', 'username': 'octocat'})

        with mock.patch.object(app_module.requests, 'request', side_effect=self._api):
            first = self.client.get('/api/dashboard').get_json()['github']
            second = self.client.get('/api/dashboard').get_json()['github']

        self.assertTrue(first['connected'], first.get('reason'))
        self.assertTrue(second['connected'], second.get('reason'))


class DashboardPayloadContractTests(unittest.TestCase):
    """
    The dashboard renders from fixed field names.

    These are the fields the page reads, so removing or renaming one silently
    blanks a widget instead of failing loudly.
    """

    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module._INTEGRATIONS.clear()
        app_module._CREDENTIAL_STORE.clear()
        app_module._LAST_ERROR.clear()

    def test_disconnected_payloads_still_carry_every_field(self):
        # No credentials and no network: this asserts the shape, not the data.
        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': '', 'LEETCODE_SESSION': ''}):
            payload = self.client.get('/api/dashboard').get_json()

        self.assertFalse(payload['github']['connected'])
        self.assertFalse(payload['leetcode']['connected'])

        for key in ('connected', 'username', 'reason'):
            self.assertIn(key, payload['github'])
            self.assertIn(key, payload['leetcode'])

        for key in ('activity_count', 'commit_today', 'today_commit_count',
                    'current_streak', 'longest_streak', 'days', 'top_repo',
                    'public_repos', 'avatar', 'url', 'name'):
            self.assertIn(key, payload['github'], 'github is missing ' + key)

        for key in ('today_solved_count', 'solved_today', 'current_streak',
                    'acceptance_rate', 'total_solved', 'easy', 'medium',
                    'hard', 'ranking', 'avatar', 'name'):
            self.assertIn(key, payload['leetcode'], 'leetcode is missing ' + key)

    def test_connected_github_exposes_the_activity_series(self):
        days = [{'date': '2026-09-%02d' % (day + 1), 'count': day}
                for day in range(30)]
        user = {
            'login': 'octocat',
            'name': 'The Octocat',
            'avatar_url': 'https://example.invalid/a.png',
            'html_url': 'https://github.com/octocat',
            'public_repos': 42,
        }
        repos = [{'name': 'my-daily-driver'}]

        with mock.patch.object(
            app_module.GitHubIntegration, 'authenticate',
            _accept_credentials('gho_valid')), mock.patch.object(
            app_module.GitHubIntegration, 'core_functionality',
            return_value={
                'user': user,
                'repositories': repos,
                'contributions': {
                    'days': days,
                    'total': sum(day['count'] for day in days),
                    'current_streak': 5,
                    'longest_streak': 19,
                },
            },
        ):
            store_for(self.client, 'github', {'token': 'gho_valid', 'username': 'octocat'})
            github = self.client.get('/api/dashboard').get_json()['github']

        self.assertTrue(github['connected'])
        self.assertEqual(len(github['days']), 30)
        self.assertEqual(github['current_streak'], 5)
        self.assertEqual(github['longest_streak'], 19)
        self.assertEqual(github['public_repos'], 42)
        self.assertEqual(github['top_repo'], 'my-daily-driver')
        self.assertEqual(github['url'], 'https://github.com/octocat')
        self.assertEqual(github['avatar'], 'https://example.invalid/a.png')

    def test_connected_leetcode_exposes_the_difficulty_split(self):
        user = {
            'username': 'someone',
            'name': 'Someone',
            'acceptance_rate': 63.71,
            'ranking': 216438,
            'solved': {'all': 496, 'easy': 409, 'medium': 75, 'hard': 12},
        }
        with mock.patch.object(
            app_module.LeetCodeIntegration, 'authenticate',
            _accept_credentials('session')), mock.patch.object(
            app_module.LeetCodeIntegration, 'core_functionality',
            return_value={'user': user, 'streak': {'available': True, 'current_streak': 4}},
        ):
            store_for(self.client, 'leetcode', {'token': 'session', 'username': 'someone'})
            leetcode = self.client.get('/api/dashboard').get_json()['leetcode']

        self.assertTrue(leetcode['connected'])
        self.assertEqual(leetcode['total_solved'], 496)
        self.assertEqual(leetcode['easy'], 409)
        self.assertEqual(leetcode['medium'], 75)
        self.assertEqual(leetcode['hard'], 12)
        self.assertEqual(leetcode['ranking'], 216438)
        self.assertEqual(leetcode['current_streak'], 4)


class SiteConfigTests(unittest.TestCase):
    """SELF_HOSTED_SITES is hand written, so it has to survive typos."""

    def setUp(self):
        self.checker = app_module.SiteStatus()

    def test_named_pairs(self):
        sites = self.checker.parse('blog=https://blog.example.com,immich=http://10.0.0.4:2283')
        self.assertEqual([s['name'] for s in sites], ['blog', 'immich'])
        self.assertEqual(sites[0]['url'], 'https://blog.example.com')
        self.assertEqual(sites[1]['url'], 'http://10.0.0.4:2283')

    def test_bare_url_uses_the_host_as_the_label(self):
        sites = self.checker.parse('https://photos.example.com/index.html')
        self.assertEqual(sites[0]['name'], 'photos.example.com')
        self.assertEqual(sites[0]['url'], 'https://photos.example.com/index.html')

    def test_missing_scheme_is_added(self):
        self.assertEqual(self.checker.parse('vault=home.example.com')[0]['url'],
                         'https://home.example.com')

    def test_keyword_is_kept_separate_from_the_url(self):
        site = self.checker.parse('immich=http://10.0.0.4:2283|Immich')[0]
        self.assertEqual(site['keyword'], 'Immich')
        self.assertEqual(site['url'], 'http://10.0.0.4:2283')

    def test_port_in_the_url_survives(self):
        self.assertEqual(self.checker.parse('immich=http://10.0.0.4:2283')[0]['name'], 'immich')

    def test_junk_entries_are_skipped_not_fatal(self):
        sites = self.checker.parse('blog=https://a.example.com, ,=,=,nonsense=,ok=https://b.example.com')
        self.assertEqual([s['name'] for s in sites], ['blog', 'ok'])

    def test_empty_configuration(self):
        self.assertEqual(self.checker.parse(''), [])
        self.assertEqual(self.checker.parse('   '), [])


class SiteCheckTests(unittest.TestCase):
    def setUp(self):
        self.checker = app_module.SiteStatus(timeout=0.5)

    def _response(self, status_code=200, body=b'ok'):
        response = mock.Mock()
        response.status_code = status_code
        response.raw.read.return_value = body
        return response

    def test_2xx_is_up(self):
        with mock.patch.object(app_module.requests, 'get', return_value=self._response()):
            result = self.checker.check({'name': 'blog', 'url': 'https://blog.example.com'})
        self.assertTrue(result['up'])
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['detail'], 'HTTP 200')
        self.assertIsNotNone(result['latency_ms'])
        self.assertIn('checked_at', result)

    def test_redirect_to_a_healthy_page_is_up(self):
        with mock.patch.object(app_module.requests, 'get', return_value=self._response(200)):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertTrue(result['up'])

    def test_500_is_down_and_says_so(self):
        with mock.patch.object(app_module.requests, 'get', return_value=self._response(502)):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertFalse(result['up'])
        self.assertEqual(result['detail'], 'HTTP 502')

    def test_404_is_down(self):
        with mock.patch.object(app_module.requests, 'get', return_value=self._response(404)):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertFalse(result['up'])
        self.assertEqual(result['status_code'], 404)

    def test_keyword_present_is_up(self):
        with mock.patch.object(
            app_module.requests, 'get', return_value=self._response(body=b'<title>Immich</title>')
        ):
            result = self.checker.check(
                {'name': 'immich', 'url': 'https://photos.example.com', 'keyword': 'immich'}
            )
        self.assertTrue(result['up'])

    def test_keyword_missing_fails_despite_a_200(self):
        with mock.patch.object(
            app_module.requests, 'get', return_value=self._response(body=b'<h1>Gateway</h1>')
        ):
            result = self.checker.check(
                {'name': 'immich', 'url': 'https://photos.example.com', 'keyword': 'immich'}
            )
        self.assertFalse(result['up'])
        self.assertIn('immich', result['detail'])

    def test_timeout_is_reported_not_raised(self):
        with mock.patch.object(
            app_module.requests, 'get', side_effect=app_module.requests.exceptions.Timeout()
        ):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertFalse(result['up'])
        self.assertIn('timed out', result['detail'])

    def test_refused_connection_is_named(self):
        error = app_module.requests.exceptions.ConnectionError('Connection refused')
        with mock.patch.object(app_module.requests, 'get', side_effect=error):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertEqual(result['detail'], 'connection refused')

    def test_dns_failure_is_named(self):
        error = app_module.requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='x'): Max retries exceeded (Name or service not known)"
        )
        with mock.patch.object(app_module.requests, 'get', side_effect=error):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertEqual(result['detail'], 'host not found')

    def test_tls_failure_is_named(self):
        error = app_module.requests.exceptions.SSLError('certificate verify failed')
        with mock.patch.object(app_module.requests, 'get', side_effect=error):
            result = self.checker.check({'name': 'app', 'url': 'https://app.example.com'})
        self.assertIn('TLS', result['detail'])

    def test_check_all_keeps_every_site(self):
        sites = [{'name': 'a', 'url': 'https://a.example.com'},
                 {'name': 'b', 'url': 'https://b.example.com'}]

        def fake_get(url, **kwargs):
            if 'a.example' in url:
                return self._response(200)
            raise app_module.requests.exceptions.ConnectionError('Connection refused')

        with mock.patch.object(app_module.requests, 'get', side_effect=fake_get):
            results = self.checker.check_all(sites)

        self.assertEqual([r['name'] for r in results], ['a', 'b'])
        self.assertTrue(results[0]['up'])
        self.assertFalse(results[1]['up'])

    def test_check_all_on_nothing(self):
        self.assertEqual(self.checker.check_all([]), [])


class SitesEndpointTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()
        app_module._SITES_CACHE.update({'payload': None, 'at': 0.0})

    def tearDown(self):
        app_module._SITES_CACHE.update({'payload': None, 'at': 0.0})

    def _stub_checks(self, results):
        return mock.patch.object(
            app_module.SiteStatus, 'check_all', return_value=results
        )

    def test_unconfigured_returns_an_empty_but_complete_payload(self):
        with mock.patch.dict('os.environ', {'SELF_HOSTED_SITES': ''}):
            payload = self.client.get('/api/sites').get_json()
        self.assertEqual(payload['configured'], 0)
        self.assertEqual(payload['sites'], [])
        self.assertIn('checked_at', payload)

    def test_counts_are_reported(self):
        sites = [
            {'name': 'blog', 'url': 'https://blog.example.com', 'up': True,
             'status_code': 200, 'latency_ms': 40, 'detail': 'HTTP 200', 'checked_at': 'now'},
            {'name': 'immich', 'url': 'http://10.0.0.4:2283', 'up': False,
             'status_code': None, 'latency_ms': 8000, 'detail': 'timed out after 8.0s',
             'checked_at': 'now'},
        ]
        with mock.patch.dict('os.environ', {'SELF_HOSTED_SITES': 'blog=https://b.example.com,immich=http://10.0.0.4:2283'}):
            with self._stub_checks(sites):
                payload = self.client.get('/api/sites').get_json()
        self.assertEqual(payload['configured'], 2)
        self.assertEqual(payload['up'], 1)
        self.assertEqual(payload['down'], 1)
        self.assertEqual(payload['sites'][1]['detail'], 'timed out after 8.0s')

    def test_results_are_cached_between_requests(self):
        sites = [{'name': 'blog', 'url': 'https://blog.example.com', 'up': True,
                  'status_code': 200, 'latency_ms': 12, 'detail': 'HTTP 200',
                  'checked_at': 'now'}]
        with mock.patch.dict('os.environ', {'SELF_HOSTED_SITES': 'blog=https://b.example.com'}):
            with self._stub_checks(sites) as checks:
                self.client.get('/api/sites')
                self.client.get('/api/sites')
                self.assertEqual(checks.call_count, 1)

    def test_refresh_bypasses_the_cache(self):
        sites = []
        with mock.patch.dict('os.environ', {'SELF_HOSTED_SITES': 'blog=https://b.example.com'}):
            with self._stub_checks(sites) as checks:
                self.client.get('/api/sites')
                self.client.get('/api/sites?refresh=1')
                self.assertEqual(checks.call_count, 2)


def dashboard_token(client):
    """Load the dashboard and return the form token it hands to the timer."""
    body = client.get('/').get_data(as_text=True)
    match = re.search(r'window\.POMODORO_CSRF = "([^"]+)"', body)
    if match is None:
        raise AssertionError('the dashboard is missing the pomodoro form token')
    return match.group(1)


def session_cookie(client):
    """The signed session cookie a browser is holding, to hand to a second tab."""
    return client.get_cookie(app_module.app.config['SESSION_COOKIE_NAME']).value


# A fixed clock, so a 25 minute round can be run to its end without waiting for
# one. 2026-03-14T09:00:00Z, a Saturday.
POMODORO_NOW = 1773478800.0
POMODORO_DAY = 86400.0


class PomodoroSettingsTests(unittest.TestCase):
    """The lengths are hand written in .env, so they have to survive typos."""

    def test_defaults_come_from_the_environment(self):
        with mock.patch.dict('os.environ', {
            'POMODORO_WORK_MINUTES': '50',
            'POMODORO_SHORT_BREAK_MINUTES': '10',
            'POMODORO_LONG_BREAK_MINUTES': '30',
            'POMODORO_ROUNDS': '3',
            'POMODORO_GOAL': '6',
        }):
            settings = app_module.settings_from_env()
        self.assertEqual(settings, {
            'work_minutes': 50,
            'short_break_minutes': 10,
            'long_break_minutes': 30,
            'rounds': 3,
            'daily_goal': 6,
        })

    def test_an_unset_value_falls_back_to_the_default(self):
        with mock.patch.dict('os.environ', {'POMODORO_WORK_MINUTES': '50'}, clear=False):
            os.environ.pop('POMODORO_SHORT_BREAK_MINUTES', None)
            settings = app_module.settings_from_env()
        self.assertEqual(settings['work_minutes'], 50)
        self.assertEqual(settings['short_break_minutes'], DEFAULTS['short_break_minutes'])

    def test_a_blank_or_broken_value_does_not_discard_the_rest(self):
        with mock.patch.dict('os.environ', {
            'POMODORO_WORK_MINUTES': 'not a number',
            'POMODORO_SHORT_BREAK_MINUTES': '',
            'POMODORO_LONG_BREAK_MINUTES': '20',
        }):
            settings = app_module.settings_from_env()
        self.assertEqual(settings['work_minutes'], DEFAULTS['work_minutes'])
        self.assertEqual(settings['short_break_minutes'], DEFAULTS['short_break_minutes'])
        self.assertEqual(settings['long_break_minutes'], 20)

    def test_a_value_beyond_the_range_is_clamped(self):
        settings = app_module.clean_settings({'work_minutes': 900, 'rounds': 99})
        self.assertEqual(settings['work_minutes'], LIMITS['work_minutes'][1])
        self.assertEqual(settings['rounds'], LIMITS['rounds'][1])

    def test_a_focus_round_cannot_be_set_to_nothing(self):
        self.assertEqual(app_module.clean_settings({'work_minutes': 0})['work_minutes'], 1)

    def test_a_break_can_be_set_to_nothing(self):
        # A skip straight into the next focus round is a legitimate choice.
        cleaned = app_module.clean_settings({'short_break_minutes': 0})
        self.assertEqual(cleaned['short_break_minutes'], 0)

    def test_a_partial_update_keeps_the_other_settings(self):
        cleaned = app_module.clean_settings({'work_minutes': 45})
        self.assertEqual(cleaned['work_minutes'], 45)
        self.assertEqual(cleaned['rounds'], DEFAULTS['rounds'])

    def test_an_unknown_setting_is_dropped(self):
        self.assertNotIn('coffee', app_module.clean_settings({'coffee': 3}))


class PomodoroTimerTests(unittest.TestCase):
    def setUp(self):
        self.now = POMODORO_NOW
        self.timer = app_module.Pomodoro(now=self.now)

    def later(self, seconds):
        self.now += seconds
        return self.now

    def test_a_fresh_timer_waits_on_a_full_focus_round(self):
        state = self.timer.snapshot(self.now)
        self.assertEqual(state['mode'], 'focus')
        self.assertFalse(state['running'])
        self.assertEqual(state['remaining'], 25 * 60)
        self.assertEqual(state['total'], 25 * 60)
        self.assertEqual(state['rounds_today'], 0)
        self.assertFalse(state['goal_met'])

    def test_the_remaining_time_comes_from_the_clock(self):
        self.timer.start(self.now)
        self.assertEqual(self.timer.snapshot(self.now)['remaining'], 1500)
        self.assertEqual(self.timer.snapshot(self.later(90))['remaining'], 1410)
        self.assertEqual(self.timer.snapshot(self.later(10))['remaining'], 1400)

    def test_a_round_that_ran_out_is_credited_on_the_next_read(self):
        self.timer.start(self.now)
        state = self.timer.snapshot(self.later(25 * 60 + 1))
        self.assertEqual(state['mode'], 'short_break')
        self.assertFalse(state['running'])
        self.assertEqual(state['remaining'], 5 * 60)
        self.assertEqual(state['rounds_today'], 1)
        self.assertEqual(state['focused_minutes_today'], 25)
        self.assertEqual(state['round'], 1)
        self.assertIn('short break', state['notice'])

    def test_a_read_after_a_long_gap_advances_only_one_round(self):
        # Otherwise a laptop that slept through the afternoon would come back to a
        # queue of breaks, and the day's count would be a guess.
        self.timer.start(self.now)
        state = self.timer.snapshot(self.later(6 * 3600))
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['rounds_today'], 1)

    def test_pausing_keeps_what_is_left(self):
        self.timer.start(self.now)
        state = self.timer.pause(self.later(300))
        self.assertFalse(state['running'])
        self.assertEqual(state['remaining'], 1500 - 300)

    def test_resuming_continues_from_the_remainder(self):
        self.timer.start(self.now)
        self.timer.pause(self.later(300))
        state = self.timer.start(self.later(60))
        self.assertTrue(state['running'])
        self.assertEqual(state['remaining'], 1200)
        self.assertEqual(state['total'], 1500)

    def test_a_paused_round_keeps_its_remainder_however_long_you_wait(self):
        self.timer.start(self.now)
        self.timer.pause(self.later(300))
        # Pausing stops the clock: the round does not quietly run out from under
        # a closed tab, so nothing is credited.
        state = self.timer.snapshot(self.later(3600))
        self.assertEqual(state['remaining'], 1200)
        self.assertEqual(state['rounds_today'], 0)
        self.assertEqual(state['mode'], 'focus')

    def test_resetting_restarts_the_current_round(self):
        self.timer.start(self.now)
        self.timer.skip(self.later(100))
        state = self.timer.reset(self.later(100))
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['remaining'], 5 * 60)
        self.assertFalse(state['running'])

    def test_resetting_a_round_that_ran_out_moves_the_cycle_on(self):
        self.timer.start(self.now)
        state = self.timer.reset(self.later(25 * 60 + 1))
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['rounds_today'], 1)

    def test_skipping_a_focus_round_credits_it(self):
        self.timer.start(self.now)
        state = self.timer.skip(self.later(10))
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['rounds_today'], 1)
        self.assertEqual(state['focus_seconds_today'], 25 * 60)
        self.assertFalse(state['running'])

    def test_skipping_a_break_returns_to_focus(self):
        self.timer.start(self.now)
        self.timer.skip(self.later(10))
        state = self.timer.skip(self.later(10))
        self.assertEqual(state['mode'], 'focus')
        self.assertEqual(state['remaining'], 25 * 60)
        self.assertEqual(state['rounds_today'], 1)

    def test_the_last_round_of_a_group_earns_a_long_break(self):
        timer = app_module.Pomodoro(settings={'rounds': 2}, now=self.now)
        timer.start(self.now)
        self.assertEqual(timer.skip(self.now)['mode'], 'short_break')
        self.assertEqual(timer.skip(self.now)['mode'], 'focus')
        self.assertEqual(timer.skip(self.now)['mode'], 'long_break')
        self.assertEqual(timer.skip(self.now)['mode'], 'focus')
        self.assertEqual(timer.snapshot(self.now)['rounds_today'], 2)

    def test_the_group_length_is_its_own_setting(self):
        timer = app_module.Pomodoro(settings={'rounds': 1}, now=self.now)
        timer.start(self.now)
        state = timer.skip(self.now)
        self.assertEqual(state['mode'], 'long_break')

    def test_new_settings_stop_the_round_in_progress(self):
        self.timer.start(self.now)
        state = self.timer.update_settings({'work_minutes': 50}, self.later(600))
        self.assertFalse(state['running'])
        self.assertEqual(state['remaining'], 50 * 60)
        self.assertEqual(state['settings']['work_minutes'], 50)

    def test_new_settings_leave_the_day_alone(self):
        self.timer.start(self.now)
        self.timer.skip(self.later(10))
        state = self.timer.update_settings({'short_break_minutes': 1}, self.later(10))
        self.assertEqual(state['rounds_today'], 1)
        self.assertEqual(state['remaining'], 60)

    def test_a_zero_length_break_does_not_stick(self):
        timer = app_module.Pomodoro(settings={'short_break_minutes': 0}, now=self.now)
        timer.start(self.now)
        state = timer.skip(self.now)
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['remaining'], 0)
        self.assertEqual(timer.start(self.now)['mode'], 'focus')

    def test_the_day_rolls_over_and_the_finished_one_is_kept(self):
        self.timer.start(self.now)
        state = self.timer.snapshot(self.later(2 * POMODORO_DAY))
        self.assertEqual(state['rounds_today'], 0)
        self.assertEqual(state['focused_minutes_today'], 0)
        self.assertEqual([day['rounds'] for day in state['history']], [1])

    def test_a_round_that_ends_after_midnight_belongs_to_the_day_it_was_worked(self):
        self.timer.start(self.now)
        # 12 minutes before midnight, then read two minutes after it.
        state = self.timer.snapshot(self.later(12 * 3600 + 8 * 3600))
        self.assertEqual([day['rounds'] for day in state['history']], [1])
        self.assertEqual(state['rounds_today'], 0)
        self.assertNotEqual(state['date'], state['history'][0]['date'])

    def test_the_history_keeps_a_week(self):
        timer = app_module.Pomodoro(now=self.now)
        for _ in range(HISTORY_DAYS + 2):
            timer.snapshot(self.later(POMODORO_DAY))
        self.assertEqual(len(timer.snapshot(self.now)['history']), HISTORY_DAYS)

    def test_a_clock_that_steps_backwards_does_not_repeat_a_day(self):
        tomorrow = self.now + POMODORO_DAY
        for moment in (tomorrow, self.now, tomorrow, tomorrow + POMODORO_DAY):
            self.timer.snapshot(moment)
        history = self.timer.snapshot(tomorrow + POMODORO_DAY)['history']
        self.assertEqual([day['date'] for day in history], ['2026-03-14', '2026-03-15'])

    def test_the_goal_is_met_when_the_count_reaches_it(self):
        timer = app_module.Pomodoro(settings={'daily_goal': 2}, now=self.now)
        timer.start(self.now)
        self.assertFalse(timer.skip(self.now)['goal_met'])
        timer.skip(self.now)
        self.assertTrue(timer.skip(self.now)['goal_met'])

    def test_a_goal_of_zero_is_never_met(self):
        timer = app_module.Pomodoro(settings={'daily_goal': 0}, now=self.now)
        self.assertFalse(timer.snapshot(self.now)['goal_met'])

    def test_clearing_today_keeps_the_cycle(self):
        self.timer.start(self.now)
        self.timer.skip(self.later(10))
        state = self.timer.clear_today(self.later(10))
        self.assertEqual(state['rounds_today'], 0)
        self.assertEqual(state['focused_minutes_today'], 0)
        self.assertEqual(state['mode'], 'short_break')
        self.assertEqual(state['round'], 1)

    def test_the_payload_is_json_shaped(self):
        state = self.timer.snapshot(self.now)
        self.assertEqual(state['label'], 'Focus')
        self.assertFalse(state['is_break'])
        self.assertEqual(state['cycle_length'], 4)
        self.assertEqual(state['remaining_at'], self.now)
        self.assertEqual(state['history'], [])
        self.assertEqual(state['settings'], DEFAULTS)


class PomodoroEndpointTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        app_module._POMODORO_STORE.clear()
        self.client = app_module.app.test_client()
        self.token = dashboard_token(self.client)

    def tearDown(self):
        app_module._POMODORO_STORE.clear()

    def post(self, client=None, **body):
        # The token is the default, so a test that wants a bad one can pass its own.
        return (client or self.client).post(
            '/api/pomodoro', json=dict({'csrf_token': self.token}, **body)
        )

    def test_the_timer_is_created_on_the_first_read(self):
        payload = self.client.get('/api/pomodoro').get_json()
        self.assertEqual(payload['mode'], 'focus')
        self.assertEqual(payload['remaining'], 1500)
        self.assertEqual(payload['settings']['work_minutes'], 25)
        self.assertEqual(len(app_module._POMODORO_STORE), 1)

    def test_the_page_hands_the_widget_a_working_token(self):
        response = self.post(action='start')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['running'])

    def test_a_post_without_the_form_token_is_rejected(self):
        response = self.client.post('/api/pomodoro', json={'action': 'start'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.client.get('/api/pomodoro').get_json()['running'])

    def test_a_post_with_a_forged_form_token_is_rejected(self):
        response = self.post(csrf_token='not-the-token', action='start')
        self.assertEqual(response.status_code, 400)

    def test_a_form_post_is_refused_rather_than_guessed_at(self):
        response = self.client.post('/api/pomodoro', data={'action': 'start'})
        self.assertEqual(response.status_code, 415)

    def test_an_unknown_action_is_rejected(self):
        response = self.post(action='rewind')
        self.assertEqual(response.status_code, 400)
        self.assertIn('rewind', response.get_json()['error'])

    def test_the_environment_sets_the_defaults_for_a_new_timer(self):
        with mock.patch.dict('os.environ', {'POMODORO_WORK_MINUTES': '50'}):
            payload = self.client.get('/api/pomodoro').get_json()
        self.assertEqual(payload['total'], 50 * 60)

    def test_each_action_reports_the_new_state(self):
        self.post(action='start')
        paused = self.post(action='pause').get_json()
        self.assertFalse(paused['running'])
        self.assertEqual(paused['remaining'], 1500)

        self.post(action='start')
        skipped = self.post(action='skip').get_json()
        self.assertEqual(skipped['mode'], 'short_break')
        self.assertEqual(skipped['rounds_today'], 1)

    def test_settings_are_kept_for_the_next_read(self):
        self.post(action='settings', work_minutes='45', short_break_minutes='8',
                  long_break_minutes='20', rounds='3', daily_goal='5')
        payload = self.client.get('/api/pomodoro').get_json()
        self.assertEqual(payload['settings'], {
            'work_minutes': 45,
            'short_break_minutes': 8,
            'long_break_minutes': 20,
            'rounds': 3,
            'daily_goal': 5,
        })
        self.assertEqual(payload['total'], 45 * 60)

    def test_a_partial_settings_post_keeps_the_other_lengths(self):
        self.post(action='settings', work_minutes='45', short_break_minutes='8')
        settings = self.post(action='settings', work_minutes='30').get_json()['settings']
        self.assertEqual(settings['work_minutes'], 30)
        self.assertEqual(settings['short_break_minutes'], 8)

    def test_an_empty_field_does_not_zero_a_length(self):
        self.post(action='settings', work_minutes='45')
        settings = self.post(action='settings', work_minutes='').get_json()['settings']
        self.assertEqual(settings['work_minutes'], 45)

    def test_junk_in_a_settings_post_is_clamped_not_obeyed(self):
        settings = self.post(action='settings', work_minutes='soon',
                             daily_goal='999').get_json()['settings']
        self.assertEqual(settings['work_minutes'], DEFAULTS['work_minutes'])
        self.assertEqual(settings['daily_goal'], LIMITS['daily_goal'][1])

    def test_clearing_today_zeroes_the_count(self):
        self.post(action='start')
        self.post(action='skip')
        payload = self.post(action='clear_today').get_json()
        self.assertEqual(payload['rounds_today'], 0)
        self.assertEqual(payload['focused_minutes_today'], 0)

    def test_each_browser_keeps_its_own_timer(self):
        other = app_module.app.test_client()
        other_token = dashboard_token(other)
        self.post(action='settings', work_minutes='45')
        other.post('/api/pomodoro', json={'action': 'settings', 'work_minutes': 15,
                                          'csrf_token': other_token})
        self.assertEqual(self.client.get('/api/pomodoro').get_json()['total'], 45 * 60)
        self.assertEqual(other.get('/api/pomodoro').get_json()['total'], 15 * 60)

    def test_a_second_tab_of_the_same_browser_shares_the_timer(self):
        self.client.get('/api/pomodoro')
        other = app_module.app.test_client()
        other.set_cookie(app_module.app.config['SESSION_COOKIE_NAME'], session_cookie(self.client))
        self.post(action='start')
        self.assertTrue(other.get('/api/pomodoro').get_json()['running'])

    def test_another_browser_gets_its_own_timer(self):
        self.client.get('/api/pomodoro')
        other = app_module.app.test_client()
        self.assertEqual(other.get('/api/pomodoro').get_json()['rounds_today'], 0)

    def test_signing_out_drops_the_timer(self):
        self.post(action='start')
        self.assertEqual(len(app_module._POMODORO_STORE), 1)
        self.client.get('/logout')
        self.assertEqual(len(app_module._POMODORO_STORE), 0)

    def test_the_store_is_capped(self):
        cap = app_module.MAX_POMODORO_SESSIONS
        for _ in range(cap + 5):
            client = app_module.app.test_client()
            client.get('/api/pomodoro')
        self.assertEqual(len(app_module._POMODORO_STORE), cap)

    def test_the_least_recently_used_timer_is_the_one_dropped(self):
        clients = [app_module.app.test_client() for _ in range(app_module.MAX_POMODORO_SESSIONS)]
        for client in clients:
            client.get('/api/pomodoro')
        first = client_sid(clients[0])
        # Reading the timer again is what makes this one the newest.
        clients[0].get('/api/pomodoro')

        app_module.app.test_client().get('/api/pomodoro')
        self.assertNotIn(first, app_module._POMODORO_STORE)

    def test_the_timer_does_not_need_a_provider(self):
        # No GitHub, no LeetCode, no sites: the widget is its own thing.
        with mock.patch.object(app_module, 'github_integration', return_value=None), \
                mock.patch.object(app_module, 'leetcode_integration', return_value=None):
            payload = self.client.get('/api/pomodoro').get_json()
        self.assertEqual(payload['mode'], 'focus')


if __name__ == '__main__':
    unittest.main()
