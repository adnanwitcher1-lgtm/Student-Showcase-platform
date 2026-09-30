from django.db import models

# Create your models here.
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