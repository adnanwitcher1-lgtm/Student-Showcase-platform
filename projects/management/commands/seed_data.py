from django.core.management.base import BaseCommand
from projects.models import Category, Tag

CATEGORIES = [
    'Web Development', 'Mobile App', 'AI / Machine Learning', 'Data Science',
    'Game Development', 'Desktop App', 'API / Backend', 'Other',
]

# (name, slug): slug explicitly diya hai kyunke slugify('C++') aur slugify('C#') dono 'c' ban jate hain
TAGS = [
    ('Python', 'python'), ('Django', 'django'), ('Flask', 'flask'), ('FastAPI', 'fastapi'),
    ('JavaScript', 'javascript'), ('TypeScript', 'typescript'), ('React', 'react'),
    ('Next.js', 'nextjs'), ('Vue.js', 'vuejs'), ('Node.js', 'nodejs'),
    ('HTML/CSS', 'html-css'), ('Tailwind CSS', 'tailwind-css'), ('Bootstrap', 'bootstrap'),
    ('PostgreSQL', 'postgresql'), ('MySQL', 'mysql'), ('MongoDB', 'mongodb'),
    ('SQLite', 'sqlite'), ('Redis', 'redis'), ('REST API', 'rest-api'), ('Docker', 'docker'),
    ('Git', 'git'), ('Flutter', 'flutter'), ('React Native', 'react-native'),
    ('Java', 'java'), ('C++', 'cpp'), ('C#', 'csharp'), ('PHP', 'php'), ('Laravel', 'laravel'),
    ('TensorFlow', 'tensorflow'), ('PyTorch', 'pytorch'), ('Pandas', 'pandas'),
]


class Command(BaseCommand):
    help = "Default categories aur tech stack tags banata hai (baar baar chalane se duplicate nahi bante)."

    def handle(self, *args, **options):
        new_c = sum(Category.objects.get_or_create(name=n)[1] for n in CATEGORIES)
        new_t = 0
        for name, slug in TAGS:
            if Tag.objects.filter(name=name).exists() or Tag.objects.filter(slug=slug).exists():
                continue
            Tag.objects.create(name=name, slug=slug)
            new_t += 1
        self.stdout.write(f"Seed done: {new_c} new categories, {new_t} new tags.")
