"""Current-user endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.v1.serializers import UserSerializer
from apps.common.response import CustomResponse


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return CustomResponse(UserSerializer(request.user).data)
