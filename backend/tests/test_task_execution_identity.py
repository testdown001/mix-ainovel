from app.api.routers.task_worker import WorkerTaskRequest


def test_execution_billing_identity_separate_from_stable_task_id():
    first = WorkerTaskRequest(task_id="stable-task", execution_id="attempt-one",
                              task_type="chapter:generate", project_id="book", user_id=1)
    retry = first.model_copy(update={"execution_id": "attempt-two"})
    assert first.task_id == retry.task_id
    assert first.billing_ref_key == "attempt-one"
    assert retry.billing_ref_key == "attempt-two"
    assert first.model_copy(update={"execution_id": None}).billing_ref_key == "stable-task"


def test_all_generation_billing_calls_use_execution_reference():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app/api/routers/task_worker.py").read_text(encoding="utf-8")
    assert "ref_key=req.task_id" not in source
    assert source.count("ref_key=req.billing_ref_key") == 6
