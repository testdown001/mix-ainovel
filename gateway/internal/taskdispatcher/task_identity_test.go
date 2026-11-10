package taskdispatcher

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestExecutionSeparatesProgressFromStableTaskIdentity(t *testing.T) {
	task := identityTask("stable", 2, StatusRunning)
	if !matchesTaskExecution(task, "") {
		t.Fatal("legacy progress must still work")
	}
	task.Metadata = map[string]string{"execution_id": "new-attempt"}
	if matchesTaskExecution(task, "") || matchesTaskExecution(task, "old-attempt") {
		t.Fatal("stale progress accepted")
	}
	if !matchesTaskExecution(task, "new-attempt") {
		t.Fatal("current progress rejected")
	}
	if !strings.Contains(taskProgressURL(task), "/stable/progress?execution_id=new-attempt") {
		t.Fatal(taskProgressURL(task))
	}
}

func identityTask(id string, chapter int, status TaskStatus) *Task {
	payload, _ := json.Marshal(ChapterGeneratePayload{ChapterNumber: chapter})
	return &Task{ID: id, UserID: 1, ProjectID: "book", Type: TaskGenerateChapter, Payload: payload, Status: status}
}

func TestTaskIdentitySeparatesWorkNotAttempts(t *testing.T) {
	a, b := identityTask("old", 2, StatusFailed), identityTask("new", 2, StatusRunning)
	if taskIdentity(a) != taskIdentity(b) {
		t.Fatal("same chapter must share identity")
	}
	b.Payload = json.RawMessage(`{"chapter_number":3}`)
	if taskIdentity(a) == taskIdentity(b) {
		t.Fatal("different chapters merged")
	}
	b = identityTask("other-user", 2, StatusFailed)
	b.UserID = 2
	if taskIdentity(a) == taskIdentity(b) {
		t.Fatal("different users merged")
	}
	b = identityTask("other-book", 2, StatusFailed)
	b.ProjectID = "other"
	if taskIdentity(a) == taskIdentity(b) {
		t.Fatal("different books merged")
	}
}

func TestCurrentTasksPrefersRunningAndKeepsOtherChapters(t *testing.T) {
	tasks := []*Task{identityTask("latest-failed", 2, StatusFailed), identityTask("running", 2, StatusRunning), identityTask("old", 2, StatusFailed), identityTask("chapter3", 3, StatusCompleted)}
	current := currentTasks(tasks)
	if len(current) != 2 || current[0].ID != "running" || current[1].ID != "chapter3" {
		t.Fatalf("unexpected tasks: %+v", current)
	}
	tasks[1].Status = StatusCompleted
	if currentTasks(tasks)[0].ID != "latest-failed" {
		t.Fatal("latest terminal record must win")
	}
}

func TestBatchRetryKeepsOriginalWorkIdentity(t *testing.T) {
	task := &Task{ID: "batch", UserID: 1, ProjectID: "book", Type: TaskBatchGenerate, Payload: json.RawMessage(`{"chapter_numbers":[3,2]}`)}
	key := taskIdentity(task)
	task.Payload = json.RawMessage(`{"chapter_numbers":[2,3]}`)
	if taskIdentity(task) != key {
		t.Fatal("order changed identity")
	}
	task.TaskKey = key
	task.Payload = json.RawMessage(`{"chapter_numbers":[3]}`)
	if taskIdentity(task) != key {
		t.Fatal("failed-only retry changed identity")
	}
}
