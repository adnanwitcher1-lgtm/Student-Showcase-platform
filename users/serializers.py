from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
from django.core.validators import FileExtensionValidator


class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )
    bio = serializers.CharField(required=False, max_length=500, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'avatar', 'bio', 'batch', 'github_username']
        read_only_fields = ['id', 'username', 'email', 'role']

    def validate_avatar(self, value):
        max_size_mb = 2
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"Avatar file size cannot exceed {max_size_mb}MB.")
        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', User.Role.STUDENT),
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'avatar', 'bio', 'batch', 'github_username']