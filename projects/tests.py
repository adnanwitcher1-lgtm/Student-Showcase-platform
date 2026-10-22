from django.test import TestCase

# Create your tests here.
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from .models import Project, SourceSnippet

User = get_user_model()


def fake_redis():
    m = mock.MagicMock()
    m.incr.return_value = 0
    m.decr.return_value = 0
    m.get.return_value = 0
    return mock.patch('projects.views.redis_client', m)


class VisibilityTests(APITestCase):
    def setUp(self):
        p = fake_redis(); p.start(); self.addCleanup(p.stop)
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.admin = User.objects.create_user('boss', password='pw12345678', role='admin')
        self.pending = Project.objects.create(
            owner=self.owner, title='Pending One', description='x', status='submitted',
            github_url='https://github.com/a/b',
        )
        self.live = Project.objects.create(owner=self.owner, title='Live One', description='x', status='approved')
        SourceSnippet.objects.create(project=self.pending, filename='a.py', language='python', content='print(1)')
        SourceSnippet.objects.create(project=self.live, filename='b.py', language='python', content='print(2)')

    def urls(self, p):
        s = p.slug
        return [
            f'/api/projects/{s}/', f'/api/projects/{s}/source-preview/', f'/api/projects/{s}/comment/',
            f'/api/projects/{s}/github-meta/', f'/api/projects/{s}/demo-url/', f'/api/projects/{s}/static-site-url/',
        ]

    def test_unapproved_hidden_from_guest_and_others(self):
        for u in self.urls(self.pending):
            self.assertEqual(self.client.get(u).status_code, 404, u)
        self.client.force_authenticate(self.other)
        for u in self.urls(self.pending):
            self.assertEqual(self.client.get(u).status_code, 404, u)

    def test_owner_and_staff_can_see_unapproved(self):
        for who in (self.owner, self.admin):
            self.client.force_authenticate(who)
            self.assertEqual(self.client.get(f'/api/projects/{self.pending.slug}/source-preview/').status_code, 200)
            self.assertEqual(self.client.get(f'/api/projects/{self.pending.slug}/').status_code, 200)

    def test_list_excludes_unapproved(self):
        res = self.client.get('/api/projects/')
        slugs = [p['slug'] for p in res.data['results']]
        self.assertIn(self.live.slug, slugs)
        self.assertNotIn(self.pending.slug, slugs)

    def test_guest_cannot_comment_on_unapproved(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(f'/api/projects/{self.pending.slug}/comment/', {'text': 'hi'})
        self.assertEqual(res.status_code, 404)

    def test_source_public_for_approved(self):
        res = self.client.get(f'/api/projects/{self.live.slug}/source-preview/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)


class SourceTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.p = Project.objects.create(
            owner=self.owner, title='Src', description='x', status='approved',
            github_url='https://github.com/a/b',
        )
        self.url = f'/api/projects/{self.p.slug}/source-preview/'

    def test_owner_adds_and_deletes(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self.url, {'filename': 'main.py', 'language': 'python', 'content': 'print(1)'})
        self.assertEqual(res.status_code, 201)
        res = self.client.delete(f'{self.url}{res.data["id"]}/')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(SourceSnippet.objects.count(), 0)

    def test_other_cannot_add(self):
        self.client.force_authenticate(self.other)
        res = self.client.post(self.url, {'filename': 'x.py', 'content': 'x'})
        self.assertEqual(res.status_code, 403)

    def test_empty_content_rejected(self):
        self.client.force_authenticate(self.owner)
        res = self.client.post(self.url, {'filename': 'x.py', 'content': '   '})
        self.assertEqual(res.status_code, 400)

    @mock.patch('projects.views.fetch_repo_source')
    def test_import_from_github(self, fetch):
        fetch.return_value = [('app.py', 'python', 'print(1)'), ('src/x.js', 'javascript', 'let a=1')]
        self.client.force_authenticate(self.owner)
        res = self.client.post(f'/api/projects/{self.p.slug}/source-import/')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data), 2)

    @mock.patch('projects.views.fetch_repo_source', side_effect=RuntimeError('boom'))
    def test_import_failure_is_friendly(self, fetch):
        self.client.force_authenticate(self.owner)
        res = self.client.post(f'/api/projects/{self.p.slug}/source-import/')
        self.assertEqual(res.status_code, 502)

    def test_import_needs_github_url(self):
        self.p.github_url = ''
        self.p.save()
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(f'/api/projects/{self.p.slug}/source-import/').status_code, 400)


class VideoTests(APITestCase):
    def setUp(self):
        p = fake_redis(); p.start(); self.addCleanup(p.stop)
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.client.force_authenticate(self.owner)

    def _create(self):
        return self.client.post('/api/projects/', {'title': 'Vid Project', 'description': 'd'}, format='multipart')

    @mock.patch('django.core.files.storage.FileSystemStorage.save', return_value='project_videos/a.mp4')
    def test_video_upload_and_type_check(self, _save):
        slug = self._create().data['slug']
        bad = SimpleUploadedFile('a.exe', b'xx', content_type='application/octet-stream')
        res = self.client.patch(f'/api/projects/{slug}/', {'demo_video': bad}, format='multipart')
        self.assertEqual(res.status_code, 400)
        ok = SimpleUploadedFile('a.mp4', b'xx', content_type='video/mp4')
        res = self.client.patch(f'/api/projects/{slug}/', {'demo_video': ok}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)

    def test_detail_exposes_owner_avatar_field(self):
        slug = self._create().data['slug']
        res = self.client.get(f'/api/projects/{slug}/')
        self.assertIn('owner_avatar', res.data)
        self.assertIn('demo_video', res.data)


class ExtrasTests(APITestCase):
    def setUp(self):
        self.u = User.objects.create_user('amy', password='pw12345678')
        Project.objects.create(owner=self.u, title='A1', description='x', status='approved', likes_count=5, is_featured=True)
        Project.objects.create(owner=self.u, title='A2', description='x', status='draft')

    def test_my_stats(self):
        self.client.force_authenticate(self.u)
        res = self.client.get('/api/users/me/stats/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['projects'], 2)
        self.assertEqual(res.data['by_status']['approved'], 1)
        self.assertEqual(res.data['total_likes'], 5)

    def test_my_stats_requires_login(self):
        self.assertIn(self.client.get('/api/users/me/stats/').status_code, (401, 403))

    def test_leaderboard_counts_only_approved(self):
        res = self.client.get('/api/leaderboard/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]['username'], 'amy')
        self.assertEqual(res.data[0]['projects'], 1)

    def test_featured_filter(self):
        res = self.client.get('/api/projects/?featured=true')
        self.assertEqual(res.data['count'], 1)
