package taskdispatcher

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

// taskIdentity describes the work, not an individual execution attempt.
func taskIdentity(task *Task) string {
	if task.TaskKey != "" {
		return task.TaskKey
	}
	var scope struct {
		ChapterNumber  int   `json:"chapter_number"`
		ChapterNumbers []int `json:"chapter_numbers"`
	}
	if json.Unmarshal(task.Payload, &scope) != nil {
		return task.ID
	}
	prefix := fmt.Sprintf("%d:%s:%s", task.UserID, task.ProjectID, task.Type)
	switch task.Type {
	case TaskGenerateChapter:
		if scope.ChapterNumber <= 0 {
			return task.ID
		}
		return fmt.Sprintf("%s:%d", prefix, scope.ChapterNumber)
	case TaskBatchGenerate:
		if len(scope.ChapterNumbers) == 0 {
			return task.ID
		}
		sort.Ints(scope.ChapterNumbers)
		return fmt.Sprintf("%s:%v", prefix, scope.ChapterNumbers)
	case TaskBlueprintGenerate:
		return prefix
	default:
		return task.ID
	}
}

func taskActive(task *Task) bool {
	return task.Status == StatusPending || task.Status == StatusQueued || task.Status == StatusRunning || task.Status == StatusRetrying
}

func taskChapterNumber(task *Task) int {
	var payload struct {
		ChapterNumber int `json:"chapter_number"`
	}
	_ = json.Unmarshal(task.Payload, &payload)
	return payload.ChapterNumber
}

// Keep old attempts for diagnostics, but expose only one current record per work item.
func currentTasks(tasks []*Task) []*Task {
	result := make([]*Task, 0, len(tasks))
	positions := map[string]int{}
	for _, task := range tasks {
		key := taskIdentity(task)
		if i, found := positions[key]; found {
			if taskActive(task) && !taskActive(result[i]) {
				result[i] = task
			}
			continue
		}
		positions[key] = len(result)
		result = append(result, task)
	}
	return result
}

// Atomic across gateway replicas: an active task is returned, never enqueued twice.
// A terminal task may restart only after its previous worker has released its lease.
var submitCurrentTaskScript = redis.NewScript(`
local old = redis.call('GET', KEYS[1])
if old then
 local task = cjson.decode(old)
 if task.status == 'pending' or task.status == 'queued' or task.status == 'running' or task.status == 'retrying' then
  return old
 end
end
if redis.call('EXISTS', KEYS[4]) == 1 then return redis.error_reply('上一轮任务正在结束，请稍后重试') end
for i = 6, 9 do redis.call('LREM', KEYS[i], 0, ARGV[2]) end
redis.call('ZREM', KEYS[5], ARGV[2])
redis.call('DEL', KEYS[3])
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SADD', KEYS[2], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
redis.call('LPUSH', KEYS[10], ARGV[2])
return ARGV[1]
`)

func (d *Dispatcher) SubmitCurrent(ctx context.Context, task *Task) error {
	task.TaskKey = taskIdentity(task)
	// Adopt an existing legacy record, including an active execution from before upgrade.
	tasks, err := d.GetUserTasks(ctx, task.UserID)
	if err != nil {
		return err
	}
	task.ID = uuid.NewSHA1(uuid.NameSpaceOID, []byte(task.TaskKey)).String()
	active := false
	for _, existing := range currentTasks(tasks) {
		if taskIdentity(existing) == task.TaskKey {
			task.ID = existing.ID
			active = taskActive(existing)
			break
		}
	}
	if !active && !d.checkUserConcurrency(task.UserID) {
		return fmt.Errorf("用户并发达到上限 (%d)", d.config.MaxPerUser)
	}
	task.Status = StatusPending
	task.ParentTaskID = ""
	task.CreatedAt = time.Now()
	task.Progress, task.RetryCount = 0, 0
	task.Stage, task.Message, task.Error = "queued", "任务已提交，等待执行", ""
	task.StartedAt, task.CompletedAt = nil, nil
	task.Result, task.Checkpoint = nil, nil
	if task.MaxRetries == 0 {
		task.MaxRetries = d.config.MaxRetries
	}
	if task.Timeout == 0 {
		task.Timeout = d.config.DefaultTimeout
	}
	if task.Metadata == nil {
		task.Metadata = map[string]string{}
	}
	data, err := json.Marshal(task)
	if err != nil {
		return err
	}
	keys := []string{fmt.Sprintf("arboris:task:%s", task.ID), fmt.Sprintf("arboris:user_tasks:%d", task.UserID),
		d.taskCancelKey(task.ID), d.taskLeaseKey(task.ID), "arboris:tasks:retry",
		PriorityCritical.QueueName(), PriorityHigh.QueueName(), PriorityDefault.QueueName(), PriorityLow.QueueName(), task.Priority.QueueName()}
	result, err := submitCurrentTaskScript.Run(ctx, d.redis, keys, string(data), task.ID, int(taskRetention.Seconds())).Text()
	if err != nil {
		return err
	}
	if err := json.Unmarshal([]byte(result), task); err != nil {
		return err
	}
	if result == string(data) {
		d.publishEvent(ctx, task, "task_created", "任务已提交")
	}
	return nil
}
