"""
Tests for LLMTracker: _save_usage_to_db metadata and call_and_track flow.

Mocks get_llm_service and chat() to avoid real LLM calls.
"""
import pytest
from unittest.mock import Mock, patch

from llm_tracker.llm_tracker import LLMTracker
from llm_tracker.models import LLMUsage


@pytest.mark.unit
@pytest.mark.django_db
class TestSaveUsageToDb:
    """
    Test _save_usage_to_db: metadata built from state and record created.
    """

    def test_creates_usage_with_node_name_in_metadata(self):
        """
        Node name is stored in metadata when not "unknown".
        """
        LLMTracker._save_usage_to_db(
            state=None,
            node_name="interpret",
            model="gpt-4",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        rec = LLMUsage.objects.get(model="gpt-4")
        assert rec.metadata.get("node_name") == "interpret"
        assert rec.total_tokens == 30
        assert rec.success is True

    def test_omits_node_name_when_unknown(self):
        """
        metadata has no node_name when node_name is "unknown".
        """
        LLMTracker._save_usage_to_db(
            state=None,
            node_name="unknown",
            model="gpt-4",
            total_tokens=1,
        )
        rec = LLMUsage.objects.get(model="gpt-4")
        assert rec.metadata.get("node_name") != "unknown"

    def test_stores_source_type_and_source_task_id_from_state(self):
        """
        source_type and source_task_id from state go into metadata.
        """
        state = {
            "source_type": "task",
            "celery_task_id": "abc-123",
        }
        LLMTracker._save_usage_to_db(
            state=state,
            node_name="node_a",
            model="gpt-4",
            total_tokens=5,
        )
        rec = LLMUsage.objects.get(model="gpt-4")
        assert rec.metadata.get("source_type") == "task"
        assert rec.metadata.get("source_task_id") == "abc-123"

    def test_prefers_source_task_id_over_celery_task_id(self):
        """
        source_task_id in state takes precedence over celery_task_id.
        """
        state = {
            "source_type": "task",
            "source_task_id": "primary-id",
            "celery_task_id": "celery-id",
        }
        LLMTracker._save_usage_to_db(
            state=state,
            node_name="n",
            model="m1",
            total_tokens=1,
        )
        rec = LLMUsage.objects.get(model="m1")
        assert rec.metadata.get("source_task_id") == "primary-id"

    def test_stores_source_path_when_given(self):
        """
        source_path from state is stored in metadata.
        """
        state = {"source_type": "api", "source_path": "/api/v1/iching/records"}
        LLMTracker._save_usage_to_db(
            state=state,
            node_name="api_node",
            model="gpt-4",
            total_tokens=1,
        )
        rec = LLMUsage.objects.get(model="gpt-4")
        assert rec.metadata.get("source_path") == "/api/v1/iching/records"

    def test_merges_extra_metadata_from_state(self):
        """
        state["metadata"] dict is merged into usage metadata.
        """
        state = {"metadata": {"workflow": "iching", "step": 2}}
        LLMTracker._save_usage_to_db(
            state=state,
            node_name="n",
            model="m2",
            total_tokens=1,
        )
        rec = LLMUsage.objects.get(model="m2")
        assert rec.metadata.get("workflow") == "iching"
        assert rec.metadata.get("step") == 2

    def test_stores_user_id_from_state(self, django_user_model):
        """
        user_id from state is set on LLMUsage.
        """
        user = django_user_model.objects.create_user(
            username="u1", password="p", email="u1@example.com"
        )
        state = {"user_id": user.id}
        LLMTracker._save_usage_to_db(
            state=state,
            node_name="n",
            model="m3",
            total_tokens=1,
        )
        rec = LLMUsage.objects.get(model="m3")
        assert rec.user_id == user.id

    def test_success_false_and_error_stored_on_failure(self):
        """
        success=False and error message are persisted.
        """
        LLMTracker._save_usage_to_db(
            state=None,
            node_name="n",
            model="m4",
            total_tokens=0,
            success=False,
            error="Connection timeout",
        )
        rec = LLMUsage.objects.get(model="m4")
        assert rec.success is False
        assert rec.error == "Connection timeout"


@pytest.mark.unit
@pytest.mark.django_db
class TestCallAndTrack:
    """
    Test call_and_track: integration with mocked LLM service.
    """

    def test_raises_when_messages_empty(self):
        """
        ValueError when messages list is empty.
        """
        with pytest.raises(ValueError, match="Messages cannot be empty"):
            LLMTracker.call_and_track(messages=[])

    @patch("llm_tracker.llm_tracker.get_llm_service")
    def test_returns_content_and_usage_on_success(self, mock_get_service):
        """
        On successful chat(), returns (content, usage) and saves LLMUsage.
        """
        mock_response = Mock()
        mock_response.content = "Hello"
        mock_response.response_metadata = {"model_name": "gpt-4"}
        mock_response.usage_metadata = {
            "input_tokens": 5,
            "output_tokens": 10,
            "total_tokens": 15,
        }
        mock_svc = Mock()
        mock_svc.chat.return_value = mock_response
        mock_get_service.return_value = mock_svc

        content, usage = LLMTracker.call_and_track(
            messages=[{"role": "user", "content": "Hi"}],
            node_name="test_node",
        )

        assert content == "Hello"
        assert usage["model"] == "gpt-4"
        assert usage["total_tokens"] == 15
        assert LLMUsage.objects.filter(model="gpt-4").exists()
        rec = LLMUsage.objects.get(model="gpt-4")
        assert rec.metadata.get("node_name") == "test_node"

    @patch("llm_tracker.llm_tracker.get_llm_service")
    def test_appends_to_state_llm_calls_on_success(self, mock_get_service):
        """
        state["llm_calls"] is appended with tracking data on success.
        """
        mock_response = Mock()
        mock_response.content = "Ok"
        mock_response.response_metadata = {}
        mock_response.usage_metadata = {"total_tokens": 1}
        mock_get_service.return_value.chat.return_value = mock_response

        state = {}
        LLMTracker.call_and_track(
            messages=[{"role": "user", "content": "x"}],
            state=state,
        )

        assert "llm_calls" in state
        assert len(state["llm_calls"]) == 1
        assert state["llm_calls"][0]["node"] == "unknown"
        assert state["llm_calls"][0]["success"] is True

    @patch("llm_tracker.llm_tracker.get_llm_service")
    def test_saves_failed_usage_and_reraises(self, mock_get_service):
        """
        On chat() exception, saves failed LLMUsage and re-raises.
        """
        mock_get_service.return_value.chat.side_effect = RuntimeError("API down")

        with pytest.raises(RuntimeError, match="API down"):
            LLMTracker.call_and_track(
                messages=[{"role": "user", "content": "x"}],
                node_name="fail_node",
            )

        rec = LLMUsage.objects.get(model="unknown")
        assert rec.success is False
        assert "API down" in (rec.error or "")

    @patch("llm_tracker.llm_tracker.get_llm_service")
    def test_raises_when_response_empty(self, mock_get_service):
        """
        ValueError when LLM returns empty content.
        """
        mock_response = Mock()
        mock_response.content = "   \n  "
        mock_response.response_metadata = {}
        mock_response.usage_metadata = {}
        mock_get_service.return_value.chat.return_value = mock_response

        with pytest.raises(ValueError, match="LLM returned empty response"):
            LLMTracker.call_and_track(
                messages=[{"role": "user", "content": "q"}],
            )
