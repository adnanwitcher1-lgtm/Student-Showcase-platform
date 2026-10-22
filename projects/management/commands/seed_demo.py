import io
import random

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from projects.models import (
    Bookmark, Category, Comment, Like, Project, ProjectScreenshot, SourceSnippet, Tag,
)

User = get_user_model()
PASSWORD = 'Demo@12345'

USERS = [
    ('demo_ayesha', 'Ayesha Khan', 'Batch 5', 'Full-stack developer who loves clean APIs.'),
    ('demo_bilal', 'Bilal Ahmed', 'Batch 5', 'Backend engineer, Django and PostgreSQL.'),
    ('demo_hira', 'Hira Malik', 'Batch 6', 'Frontend and UI/UX enthusiast.'),
    ('demo_usman', 'Usman Tariq', 'Batch 6', 'Machine learning and data science student.'),
]

PALETTES = [
    ((124, 58, 237), (217, 70, 239)), ((6, 182, 212), (59, 130, 246)),
    ((244, 63, 94), (251, 146, 60)), ((16, 185, 129), (6, 182, 212)),
    ((99, 102, 241), (236, 72, 153)), ((245, 158, 11), (239, 68, 68)),
]

PROJECTS = [
    {
        'title': 'Smart Task Manager', 'owner': 'demo_ayesha', 'category': 'Web Development',
        'tags': ['Django', 'React', 'PostgreSQL', 'Redis'], 'featured': True,
        'github': 'https://github.com/pallets/flask', 'live': 'https://example.com',
        'desc': "## Smart Task Manager\n\nA full-stack task manager where teams create projects, assign tasks and track progress.\n\n### Features\n- JWT login with Google and GitHub\n- Drag and drop task board\n- Email reminders with Celery\n- Dark mode\n\n### What I learned\nBuilding REST APIs with Django REST Framework and connecting them to a React frontend.",
        'code': ('views.py', 'python', "from rest_framework import viewsets\n\n\nclass TaskViewSet(viewsets.ModelViewSet):\n    serializer_class = TaskSerializer\n\n    def get_queryset(self):\n        return Task.objects.filter(owner=self.request.user)\n"),
    },
    {
        'title': 'Weather Hub', 'owner': 'demo_hira', 'category': 'Web Development',
        'tags': ['JavaScript', 'HTML/CSS', 'REST API'], 'featured': False,
        'github': 'https://github.com/pallets/click', 'live': 'https://example.com',
        'desc': "## Weather Hub\n\nA clean weather dashboard with a 7-day forecast, search by city and automatic dark mode.\n\n- Uses a public weather API\n- Responsive layout\n- Saves your favourite cities in the browser",
        'code': ('app.js', 'javascript', "async function getWeather(city) {\n  const res = await fetch(`/api/weather?city=${encodeURIComponent(city)}`)\n  if (!res.ok) throw new Error('City not found')\n  return res.json()\n}\n"),
    },
    {
        'title': 'Student Result Portal', 'owner': 'demo_bilal', 'category': 'API / Backend',
        'tags': ['Django', 'PostgreSQL', 'Docker', 'REST API'], 'featured': True,
        'github': 'https://github.com/pallets/jinja', 'live': '',
        'desc': "## Student Result Portal\n\nTeachers upload marks, students see grades and download a PDF report card.\n\n### Highlights\n- Role based permissions (teacher / student / admin)\n- Celery task generates PDF reports\n- Fully dockerised",
        'code': ('models.py', 'python', "from django.db import models\n\n\nclass Result(models.Model):\n    student = models.ForeignKey('auth.User', on_delete=models.CASCADE)\n    subject = models.CharField(max_length=100)\n    marks = models.PositiveIntegerField()\n"),
    },
    {
        'title': 'Spam Mail Detector', 'owner': 'demo_usman', 'category': 'AI / Machine Learning',
        'tags': ['Python', 'Pandas', 'TensorFlow'], 'featured': False,
        'github': 'https://github.com/pallets/werkzeug', 'live': '',
        'desc': "## Spam Mail Detector\n\nA text classifier that detects spam emails with 97% accuracy on the test set.\n\n- TF-IDF features + logistic regression\n- Small FastAPI endpoint to try it live",
        'code': ('train.py', 'python', "from sklearn.feature_extraction.text import TfidfVectorizer\nfrom sklearn.linear_model import LogisticRegression\n\nvec = TfidfVectorizer(stop_words='english')\nX = vec.fit_transform(texts)\nmodel = LogisticRegression().fit(X, labels)\n"),
    },
    {
        'title': 'Pixel Runner Game', 'owner': 'demo_hira', 'category': 'Game Development',
        'tags': ['JavaScript', 'HTML/CSS'], 'featured': False,
        'github': 'https://github.com/pallets/itsdangerous', 'live': 'https://example.com',
        'desc': "## Pixel Runner\n\nAn endless runner game in the browser. Jump over obstacles and beat your high score.\n\n- Plain JavaScript and canvas\n- Keyboard and touch controls",
        'code': ('game.js', 'javascript', "function update(dt) {\n  player.vy += GRAVITY * dt\n  player.y += player.vy * dt\n  if (player.y > GROUND) { player.y = GROUND; player.vy = 0 }\n}\n"),
    },
    {
        'title': 'Expense Tracker App', 'owner': 'demo_ayesha', 'category': 'Mobile App',
        'tags': ['Flutter', 'MongoDB'], 'featured': False,
        'github': 'https://github.com/pallets/markupsafe', 'live': '',
        'desc': "## Expense Tracker\n\nTrack daily spending, set monthly budgets and see charts by category.\n\n- Offline first\n- Export to CSV",
        'code': ('main.dart', 'dart', "void main() {\n  runApp(const ExpenseApp());\n}\n\nclass ExpenseApp extends StatelessWidget {\n  const ExpenseApp({super.key});\n}\n"),
    },
]

COMMENTS = [
    'Great work! The UI looks really clean.',
    'Love the idea. Can you share how you handled authentication?',
    'The source code is easy to read, nice job.',
    'Would be great to see a mobile version of this.',
]


def make_image(title, palette, size=(1200, 675)):
    w, h = size
    img = Image.new('RGB', size)
    px = img.load()
    (r1, g1, b1), (r2, g2, b2) = palette
    for x in range(w):
        t = x / (w - 1)
        col = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
        for y in range(h):
            px[x, y] = col
    d = ImageDraw.Draw(img)
    d.ellipse((w - 420, -120, w + 120, 420), fill=None, outline=(255, 255, 255), width=6)
    d.text((60, h - 110), title, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Demo/testing ke liye sample users aur approved projects banata hai. --clear se sab hat jata hai."

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Demo users aur unke projects delete karo')

    def handle(self, *args, **options):
        if options['clear']:
            n, _ = User.objects.filter(username__startswith='demo_').delete()
            self.stdout.write(f'Removed demo data ({n} rows).')
            return

        rng = random.Random(42)
        users = {}
        for username, full, batch, bio in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@example.com', 'first_name': full.split()[0],
                          'batch': batch, 'bio': bio, 'github_username': username.replace('demo_', '')},
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
                user.avatar.save(f'{username}.jpg', make_image(full, PALETTES[len(users) % len(PALETTES)], (400, 400)), save=True)
            users[username] = user

        made = 0
        for i, p in enumerate(PROJECTS):
            if Project.objects.filter(title=p['title'], owner=users[p['owner']]).exists():
                continue
            cat, _ = Category.objects.get_or_create(name=p['category'])
            proj = Project.objects.create(
                owner=users[p['owner']], title=p['title'], description=p['desc'], category=cat,
                github_url=p['github'], live_demo_url=p['live'], status=Project.Status.APPROVED,
                is_featured=p['featured'], views_count=rng.randint(40, 900),
            )
            tags = []
            for name in p['tags']:
                tag = Tag.objects.filter(name=name).first() or Tag.objects.create(name=name)
                tags.append(tag)
            proj.tech_stack.set(tags)

            palette = PALETTES[i % len(PALETTES)]
            proj.cover_image.save(f'{proj.slug}.jpg', make_image(p['title'], palette), save=True)
            for k in range(2):
                shot = ProjectScreenshot(project=proj)
                shot.image.save(f'{proj.slug}-{k}.jpg', make_image(f"{p['title']} #{k + 1}", PALETTES[(i + k + 1) % len(PALETTES)]), save=True)

            fn, lang, code = p['code']
            SourceSnippet.objects.create(project=proj, filename=fn, language=lang, content=code)

            likers = [u for name, u in users.items() if name != p['owner']]
            rng.shuffle(likers)
            for u in likers[: rng.randint(1, len(likers))]:
                Like.objects.get_or_create(project=proj, user=u)
            Bookmark.objects.get_or_create(project=proj, user=likers[0])
            for u in likers[:2]:
                Comment.objects.create(project=proj, author=u, text=rng.choice(COMMENTS))
            proj.likes_count = proj.likes.count()
            proj.save(update_fields=['likes_count'])
            made += 1

        self.stdout.write(self.style.SUCCESS(
            f'Demo data ready: {made} new project(s). Demo users: demo_ayesha, demo_bilal, demo_hira, demo_usman (password: {PASSWORD})'
        ))
