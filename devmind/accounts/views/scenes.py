"""
Scene-related views.

Handles retrieval of available usage scenes for user registration.

Note: This view depends on threadline's PromptConfigManager.
If you don't have threadline, you can return a default scene list
or remove this view entirely.
"""

import logging

from django.utils.translation import gettext_lazy as _

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# Note: PromptConfigManager is from threadline
# If you have similar functionality, import it here:
# from threadline.utils.prompt_config_manager import PromptConfigManager

from ..serializers import SceneSerializer

logger = logging.getLogger(__name__)


class GetAvailableScenesView(APIView):
    """
    Get available usage scenes.

    Returns list of available scenes with names and descriptions
    in the requested language.

    Note: This view requires threadline's PromptConfigManager.
    If you don't have threadline, you can return a default scene list.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['auth'],
        summary=_("Get available scenes"),
        parameters=[
            OpenApiParameter(
                name='language',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=_("Language code (e.g., 'zh-CN', 'en-US', 'es')"),
                required=False
            )
        ],
        responses={200: SceneSerializer(many=True)}
    )
    def get(self, request):
        """
        Get list of available scenes.

        Note: If you don't have threadline, you can return a default list:
        return Response([
            {
                'key': 'default',
                'name': 'Default',
                'description': 'Default usage scene'
            }
        ])
        """
        # language = request.query_params.get('language', 'en-US')

        try:
            # Note: Uncomment if you have PromptConfigManager:
            #
            # config_manager = PromptConfigManager()
            # available_scenes = config_manager.get_available_scenes()
            #
            # scenes = []
            # for scene_key in available_scenes:
            #     try:
            #         scene_info = config_manager.get_scene_config(
            #             scene_key,
            #             language
            #         )
            #         scenes.append({
            #             'key': scene_key,
            #             'name': scene_info.get('name', scene_key),
            #             'description': scene_info.get('description', '')
            #         })
            #     except KeyError as e:
            #         logger.warning(
            #             f"Scene {scene_key} not available "
            #             f"for language {language}: {e}"
            #         )
            #         continue
            #
            # if not scenes:
            #     return Response(
            #         {
            #             'success': False,
            #             'error': _(
            #                 'No scenes available for the requested language'
            #             )
            #         },
            #         status=status.HTTP_404_NOT_FOUND
            #     )
            #
            # serializer = SceneSerializer(scenes, many=True)
            # return Response(serializer.data, status=status.HTTP_200_OK)

            # Default implementation: return a simple default scene
            scenes = [{
                'key': 'default',
                'name': 'Default',
                'description': 'Default usage scene'
            }]

            serializer = SceneSerializer(scenes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Failed to get available scenes: {e}",
                exc_info=True
            )
            return Response(
                {
                    'success': False,
                    'error': _('Failed to retrieve available scenes')
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
