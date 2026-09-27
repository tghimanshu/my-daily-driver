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


if __name__ == '__main__':
    unittest.main()
