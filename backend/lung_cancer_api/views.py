from django.http import JsonResponse


def root(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "biogenix-backend",
            "api": "/api/",
            "admin": "/admin/",
        }
    )
