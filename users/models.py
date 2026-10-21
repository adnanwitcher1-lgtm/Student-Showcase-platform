from django.db import models

# Create your models here.
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student'
        INSTRUCTOR = 'instructor'
        ADMIN = 'admin'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    batch = models.CharField(max_length=50, blank=True)
    github_username = models.CharField(max_length=100, blank=True)
    

    def __str__(self):
        return self.username

def generate_client_id():
    return uuid.uuid4().hex


class DesktopClient(models.Model):
    """
    Registered desktop app build. Desktop app login ke waqt X-Client-ID header bhejta hai.
    Is client ke login se bana token sirf usi header ke saath chalta hai (device-bound token).
    Client disable karne par us ke saare tokens band ho jate hain.
    """
    name = models.CharField(max_length=100, help_text="e.g. Windows app v1.0")
    client_id = models.CharField(max_length=64, unique=True, default=generate_client_id, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'disabled'})"
