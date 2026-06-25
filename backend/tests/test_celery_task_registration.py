def test_business_tasks_are_registered_before_worker_consumes():
    from core.celery import app

    app.loader.import_default_modules()

    assert "cloud_billing.tasks.submit_recharge_approval" in app.tasks
    assert "cloud_billing.tasks.collect_billing_data" in app.tasks
    assert "data_collector.tasks.run_collect" in app.tasks
    assert "sals.tasks.sync_incidents" in app.tasks
