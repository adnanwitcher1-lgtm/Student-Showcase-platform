from django.test import TestCase

# Create your tests here.
import base64
import hashlib
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from .models import DesktopClient

CHALLENGE_URL = '/api/auth/social/desktop-complete/'
EXCHANGE_URL = '/api/auth/social/desktop-exchange/'


def make_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    SECURE_SSL_REDIRECT=False,
    RATELIMIT_ENABLE=False,
)
class DesktopSocialLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='student1', password='pw12345!')
        self.client_row = DesktopClient.objects.create(name='Test app')
        self.verifier = 'v' * 43
        self.challenge = make_challenge(self.verifier)

    def _get_code(self):
        self.client.force_login(self.user)
        res = self.client.get(CHALLENGE_URL, {'challenge': self.challenge})
        self.assertEqual(res.status_code, 200)
        match = re.search(r'studentshowcase://auth\?code=([A-Za-z0-9_-]+)', res.content.decode())
        self.assertIsNotNone(match, 'app link page mein nahi mila')
        return match.group(1)

    def _exchange(self, code, verifier=None, client_id=None):
        headers = {}
        cid = self.client_row.client_id if client_id is None else client_id
        if cid:
            headers['HTTP_X_CLIENT_ID'] = cid
        return self.client.post(
            EXCHANGE_URL,
            {'code': code, 'verifier': verifier or self.verifier},
            content_type='application/json',
            **headers,
        )

    def test_full_flow_gives_device_bound_token(self):
        code = self._get_code()
        res = self._exchange(code)
        self.assertEqual(res.status_code, 200)
        token = AccessToken(res.json()['access'])
        self.assertEqual(token['client_id'], self.client_row.client_id)
        self.assertEqual(str(token['user_id']), str(self.user.pk))

    def test_token_works_only_with_client_header(self):
        access = self._exchange(self._get_code()).json()['access']
        auth = {'HTTP_AUTHORIZATION': f'Bearer {access}'}
        self.client.logout()
        self.assertEqual(self.client.get('/api/users/me/', **auth).status_code, 401)
        ok = self.client.get('/api/users/me/', HTTP_X_CLIENT_ID=self.client_row.client_id, **auth)
        self.assertEqual(ok.status_code, 200)

    def test_code_is_single_use(self):
        code = self._get_code()
        self.assertEqual(self._exchange(code).status_code, 200)
        self.assertEqual(self._exchange(code).status_code, 400)

    def test_wrong_verifier_rejected_and_burns_code(self):
        code = self._get_code()
        self.assertEqual(self._exchange(code, verifier='x' * 43).status_code, 400)
        self.assertEqual(self._exchange(code).status_code, 400)

    def test_missing_or_unknown_client_id_rejected(self):
        code = self._get_code()
        self.assertEqual(self._exchange(code, client_id='').status_code, 403)
        self.assertEqual(self._exchange(code, client_id='f' * 32).status_code, 403)

    def test_disabled_client_rejected(self):
        self.client_row.is_active = False
        self.client_row.save()
        cache.clear()
        self.assertEqual(self._exchange(self._get_code()).status_code, 403)

    def test_complete_requires_login_and_valid_challenge(self):
        res = self.client.get(CHALLENGE_URL, {'challenge': self.challenge})
        self.assertEqual(res.status_code, 400)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(CHALLENGE_URL, {'challenge': 'short'}).status_code, 400)
        self.assertEqual(self.client.get(CHALLENGE_URL).status_code, 400)

    def test_session_is_cleared_after_complete(self):
        self._get_code()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_garbage_code_rejected(self):
        self.assertEqual(self._exchange('nope').status_code, 400)
        self.assertEqual(self._exchange('').status_code, 400)
