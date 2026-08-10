"""Regression tests for SALS ETL request handling."""

from unittest.mock import Mock, patch

import requests

from sals.services import etl


def _build_user_record(index: int) -> dict:
    """Build a minimal user payload from the remote API."""
    return {
        "record_data_map": {
            "sys_id": f"user-{index}",
            "name": f"User {index}",
        }
    }


def _build_response(records: list[dict], status_code: int = 200) -> Mock:
    """Build a mocked requests response."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = {"data": records}
    response.text = "mocked"
    return response


def _expected_user(index: int) -> dict:
    """Build the expected normalized user payload."""
    return {
        "sys_id": f"user-{index}",
        "name": f"User {index}",
        "email": None,
        "user_name": None,
        "department": None,
        "phone": None,
        "mobile_phone": None,
        "title": None,
        "active": None,
    }


@patch.object(etl, "API_REQUEST_MAX_ATTEMPTS", 2)
def test_fetch_users_retries_transient_request_before_success():
    """Transient user API failures should retry before succeeding."""
    first_page = [_build_user_record(1)]
    transient_error = requests.ConnectionError(
        "temporary failure in name resolution"
    )

    with (
        patch(
            "sals.services.etl.requests.get",
            side_effect=[
                transient_error,
                _build_response(first_page),
            ],
        ) as mock_get,
        patch("sals.services.etl.logger") as mock_logger,
    ):
        records = etl.fetch_users_from_api("token", limit=1)

    assert records == [_expected_user(1)]
    assert mock_get.call_count == 2
    mock_logger.warning.assert_called()
    mock_logger.error.assert_not_called()


@patch.object(etl, "API_REQUEST_MAX_ATTEMPTS", 2)
def test_fetch_users_warns_on_partial_follow_up_failure():
    """Handled follow-up page failures should not be logged as errors."""
    first_page = [_build_user_record(index) for index in range(200)]
    transient_error = requests.ConnectionError(
        "temporary failure in name resolution"
    )

    with (
        patch(
            "sals.services.etl.requests.get",
            side_effect=[
                _build_response(first_page),
                transient_error,
                transient_error,
            ],
        ),
        patch("sals.services.etl.logger") as mock_logger,
    ):
        records = etl.fetch_users_from_api("token", limit=500)

    assert len(records) == 200
    mock_logger.warning.assert_called()
    mock_logger.error.assert_not_called()


@patch.object(etl, "API_REQUEST_MAX_ATTEMPTS", 2)
def test_fetch_users_logs_error_when_initial_page_fails():
    """Initial user API failures should remain errors."""
    transient_error = requests.ConnectionError(
        "temporary failure in name resolution"
    )

    with (
        patch(
            "sals.services.etl.requests.get",
            side_effect=[transient_error, transient_error],
        ),
        patch("sals.services.etl.logger") as mock_logger,
    ):
        records = etl.fetch_users_from_api("token", limit=1)

    assert records == []
    mock_logger.error.assert_called_once()


def test_incomplete_read_is_a_transient_request_error():
    """Incomplete response bodies should be eligible for retry."""
    error = requests.exceptions.ChunkedEncodingError(
        "Connection broken: IncompleteRead"
    )

    assert etl._is_transient_request_error(error)


@patch.object(etl, "API_REQUEST_MAX_ATTEMPTS", 2)
def test_incident_sync_retries_transient_first_page_failure():
    """Incident sync should retry a transient initial page failure."""
    request_counts: dict[int, int] = {}

    def get_incident_page(*args, **kwargs):
        first_row = kwargs["params"]["sysparm_first_row"]
        request_counts[first_row] = request_counts.get(first_row, 0) + 1
        if first_row == 1 and request_counts[first_row] == 1:
            raise requests.ReadTimeout("read timed out")
        return _build_response([])

    with (
        patch("sals.services.etl.login_api", return_value="token"),
        patch(
            "sals.services.etl.sync_companies_from_api",
            return_value={"status": "ok"},
        ),
        patch(
            "sals.services.etl._get_excluded_company_sys_ids",
            return_value=[],
        ),
        patch.object(etl.Company.objects, "all", return_value=[]),
        patch.object(etl.Incident.objects, "count", return_value=0),
        patch(
            "sals.services.etl.sync_users_from_api",
            return_value={"status": "ok"},
        ),
        patch("sals.services.etl.requests.get", side_effect=get_incident_page),
        patch("sals.services.etl.logger") as mock_logger,
    ):
        result = etl.sync_from_api(full_sync=False)

    assert result["status"] == "ok"
    assert request_counts[1] == 2
    mock_logger.warning.assert_called()
    mock_logger.error.assert_not_called()
