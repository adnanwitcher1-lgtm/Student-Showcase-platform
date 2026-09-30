from django_ratelimit.exceptions import Ratelimited
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    if isinstance(exc, Ratelimited):
        return Response(
            {"detail": "Too many requests. Please slow down and try again shortly."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return exception_handler(exc, context)