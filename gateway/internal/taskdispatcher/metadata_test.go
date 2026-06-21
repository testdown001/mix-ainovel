package taskdispatcher

import (
	"encoding/json"
	"testing"
)

// TestEnsureMetadataInitializesNilMap：ensureMetadata 必须把 nil map 重建为可写空 map，
// 且对已有 map 幂等（不清空已有内容）。
func TestEnsureMetadataInitializesNilMap(t *testing.T) {
	task := &Task{} // Metadata 为 nil
	task.ensureMetadata()
	if task.Metadata == nil {
		t.Fatal("ensureMetadata 后 Metadata 仍为 nil")
	}
	task.Metadata["duration_ms"] = "123" // 修复前此处 panic: assignment to entry in nil map
	if task.Metadata["duration_ms"] != "123" {
		t.Fatalf("写入失败: %v", task.Metadata)
	}

	// 幂等：已有内容不被清空
	task.ensureMetadata()
	if task.Metadata["duration_ms"] != "123" {
		t.Fatal("ensureMetadata 清空了已有内容")
	}
}

// TestTaskMetadataNilAfterRedisRoundTrip：复现根因——空 Metadata + json:omitempty 经
// JSON(Redis) 往返后变 nil；收尾写 Metadata 前若不 ensureMetadata 会 panic。
func TestTaskMetadataNilAfterRedisRoundTrip(t *testing.T) {
	// 提交时的状态：初始化为空 map（见 Dispatcher.Submit）
	task := &Task{ID: "t1", Metadata: make(map[string]string)}

	data, err := json.Marshal(task)
	if err != nil {
		t.Fatalf("marshal 失败: %v", err)
	}

	// omitempty：空 map 被省略，序列化结果不含 metadata 字段
	var loaded Task
	if err := json.Unmarshal(data, &loaded); err != nil {
		t.Fatalf("unmarshal 失败: %v", err)
	}
	if loaded.Metadata != nil {
		t.Fatalf("预期往返后 Metadata 为 nil（omitempty 省略空 map），实际: %v", loaded.Metadata)
	}

	// 修复：写前 ensureMetadata，不再 panic
	loaded.ensureMetadata()
	loaded.Metadata["duration_ms"] = "456"
	if loaded.Metadata["duration_ms"] != "456" {
		t.Fatal("ensureMetadata 后写入失败")
	}
}
