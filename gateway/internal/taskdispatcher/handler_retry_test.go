package taskdispatcher

import (
	"encoding/json"
	"testing"
)

func batchTaskForRetry(t *testing.T, status TaskStatus, result string) *Task {
	t.Helper()
	payload, err := json.Marshal(BatchGeneratePayload{
		ProjectID: "novel-1", ChapterNumbers: []int{7, 8, 9}, UserID: 3,
		WritingNotes: "保持悬疑节奏",
	})
	if err != nil {
		t.Fatal(err)
	}
	return &Task{
		Type: TaskBatchGenerate, Status: status, Payload: payload, Result: json.RawMessage(result),
	}
}

func TestRetryPayloadKeepsOnlyFailedBatchChapters(t *testing.T) {
	task := batchTaskForRetry(t, StatusCompleted, `{
		"status":"partial","results":[
			{"chapter_number":7,"status":"success"},
			{"chapter_number":8,"status":"failed"},
			{"chapter_number":9,"status":"success"}
		]}`)

	retry, err := retryPayload(task)
	if err != nil {
		t.Fatal(err)
	}
	var payload BatchGeneratePayload
	if err := json.Unmarshal(retry, &payload); err != nil {
		t.Fatal(err)
	}
	if len(payload.ChapterNumbers) != 1 || payload.ChapterNumbers[0] != 8 {
		t.Fatalf("expected only chapter 8, got %#v", payload.ChapterNumbers)
	}
	if payload.WritingNotes != "保持悬疑节奏" {
		t.Fatalf("expected writing notes to survive retry, got %q", payload.WritingNotes)
	}
}

func TestRetryPayloadFallsBackToOriginalBatchAfterInterruption(t *testing.T) {
	task := batchTaskForRetry(t, StatusFailed, ``)
	retry, err := retryPayload(task)
	if err != nil {
		t.Fatal(err)
	}
	var payload BatchGeneratePayload
	if err := json.Unmarshal(retry, &payload); err != nil {
		t.Fatal(err)
	}
	if len(payload.ChapterNumbers) != 3 {
		t.Fatalf("expected original chapters for idempotent recovery, got %#v", payload.ChapterNumbers)
	}
}

func TestRetryPayloadRejectsSuccessfulBatch(t *testing.T) {
	task := batchTaskForRetry(t, StatusCompleted, `{
		"status":"completed","results":[{"chapter_number":7,"status":"success"}]
	}`)
	if _, err := retryPayload(task); err == nil {
		t.Fatal("expected completed batch without failures to be rejected")
	}
}
