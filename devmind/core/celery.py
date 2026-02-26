import logging
import os
import signal
import threading
import time

from celery import Celery
from celery.signals import worker_process_init, worker_shutting_down

# Configure logging for the application
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set the Django project's settings module. This ensures Django can load
# the appropriate configuration. The 'DJANGO_SETTINGS_MODULE' environment
# variable specifies the configuration file. Here it is set to 'core.settings',
# indicating the Django configuration file is at 'core/settings.py'.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Create a Celery application instance. The name of the Celery application is
# 'core', which usually matches the Django project name for better association
# of tasks with the project.
logger.debug("Creating Celery application instance with name: core")
app = Celery("core")

# Load Celery configuration from Django's settings file.
# The 'namespace="CELERY"' option restricts loading to settings that
# start with 'CELERY_'. Therefore, all Celery-related settings in
# 'core/settings.py' must begin with 'CELERY_'.
logger.info("Loading Celery configuration from Django settings")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Update the result backend to use Django database
# Explicitly set the beat scheduler to use database
app.conf.update(
    result_backend='django-db',
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler'
)

# Automatically discover all task modules registered in the Django project.
# Celery will search for 'tasks.py' in each app and load any tasks
# defined there.
logger.info("Discovering tasks in registered Django applications")
app.autodiscover_tasks()


def reap_zombies():
    """
    Reap zombie processes (non-blocking).

    Best practice: Call this periodically, not via signal handler.
    Signal handlers can interfere with Celery's own signal handling.
    """
    try:
        reaped_count = 0
        while True:
            try:
                # Wait for any child process to exit (non-blocking)
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    # No more zombie processes
                    break
                reaped_count += 1
                logger.debug(
                    f"Reaped zombie process {pid} (status: {status})"
                )
            except ChildProcessError:
                # No child processes
                break
            except OSError:
                # No more processes to wait for
                break

        if reaped_count > 0:
            logger.info(f"Reaped {reaped_count} zombie process(es)")
    except Exception as e:
        logger.debug(f"Error reaping zombies: {e}")


def setup_periodic_zombie_reaper():
    """
    Setup periodic zombie process reaper.

    Best practice: Use a background thread instead of signal handler
    to avoid interfering with Celery's signal handling.
    """
    def periodic_reap():
        """
        Periodically reap zombie processes.

        Check every 30 seconds.
        """
        while True:
            time.sleep(30)
            reap_zombies()

    try:
        thread = threading.Thread(
            target=periodic_reap,
            daemon=True,
            name="zombie-reaper"
        )
        thread.start()
        logger.info("Periodic zombie process reaper started")
    except Exception as e:
        logger.warning(f"Could not start zombie reaper thread: {e}")


@worker_process_init.connect
def on_worker_process_init(sender=None, **kwargs):
    """
    Called when each worker process is initialized.

    Best practice: Use worker_process_init instead of worker_ready
    to ensure each process sets up its own reaper.
    """
    logger.info(
        "Worker process initialized, setting up zombie process reaper"
    )

    # Worker startup cleanup can be added here if needed
    # Example: cleanup stale locks, reset states, etc.

    # Setup SIGCHLD handler for this process
    # Note: This only works in the worker process, not the main process
    def sigchld_handler(signum, frame):
        """
        Handle SIGCHLD signal to reap zombies.
        """
        reap_zombies()

    try:
        # Only set up signal handler if we're in a worker process
        # (not the main process)
        if hasattr(os, 'getpid'):
            signal.signal(signal.SIGCHLD, sigchld_handler)
            logger.info("SIGCHLD handler configured for worker process")
    except (ValueError, OSError, AttributeError) as e:
        # Signal handling may not be available in all environments
        # Fallback to periodic reaping
        logger.debug(f"Could not setup SIGCHLD handler: {e}")
        setup_periodic_zombie_reaper()


@worker_shutting_down.connect
def on_worker_shutting_down(sender=None, **kwargs):
    """
    Called when worker is shutting down.
    """
    logger.info(
        "Worker shutting down, performing final zombie cleanup"
    )
    reap_zombies()
