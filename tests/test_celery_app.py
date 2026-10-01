from src.celery_app import celery_app


def test_celery_uses_json_and_does_not_store_results() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.task_ignore_result is True
