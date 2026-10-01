from src.models import Base, OperationStatus, OperationTaskStatus


def test_operation_tables_and_lifecycle_statuses_are_declared() -> None:
    assert {"operations", "operation_tasks"} <= set(Base.metadata.tables)
    assert OperationStatus.PARTIAL_FAILURE.value == "partial_failure"
    assert OperationTaskStatus.CANCELLATION_REQUESTED.value == "cancellation_requested"
