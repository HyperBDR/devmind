"""
Admin-only REST API for LLM usage and token statistics.

Any project that uses llm_tracker can expose these views by including
llm_tracker.urls (e.g. under an admin API prefix). All views require
IsAdminUser (staff or superuser).
"""
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from llm_tracker.llm_usage import get_llm_usage_list_from_query
from llm_tracker.llm_usage_stats import get_token_stats_from_query


class AdminTokenStatsView(APIView):
    """
    GET: LLM token consumption statistics (summary, by_model, time series).
    Query params: start_date, end_date, user_id, granularity (day|month|year).
    Admin only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            data = get_token_stats_from_query(request.query_params)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(data)


class AdminLLMUsageListView(APIView):
    """
    GET: Paginated list of LLM usage records with filters.
    Query params: page, page_size, user_id, model, success, start_date,
    end_date. Read-only. Admin only.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        data = get_llm_usage_list_from_query(request.query_params)
        return Response(data)
