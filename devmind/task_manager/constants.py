"""
Constants for task management.
"""


class TaskStatus:
    """
    Task execution status constants.
    """
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    RETRY = 'RETRY'
    REVOKED = 'REVOKED'

    @classmethod
    def get_all_statuses(cls):
        """
        Get all available task statuses.
        
        Returns:
            List of all status values
        """
        return [
            cls.PENDING,
            cls.STARTED,
            cls.SUCCESS,
            cls.FAILURE,
            cls.RETRY,
            cls.REVOKED,
        ]

    @classmethod
    def get_completed_statuses(cls):
        """
        Get all completed statuses.
        
        Returns:
            List of completed status values
        """
        return [
            cls.SUCCESS,
            cls.FAILURE,
            cls.REVOKED,
        ]

    @classmethod
    def get_running_statuses(cls):
        """
        Get all running statuses.
        
        Returns:
            List of running status values
        """
        return [
            cls.STARTED,
            cls.RETRY,
        ]
