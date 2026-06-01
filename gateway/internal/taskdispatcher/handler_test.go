package taskdispatcher

import "testing"

func TestGetExtraConfigPreservesGenerationOverrides(t *testing.T) {
	config := map[string]interface{}{
		"preset":           "fast",
		"use_agent_system": true,
		"rag_mode":         "two_stage",
		"writing_notes":    "提高张力",
		"use_agentic_loop": true,
		"selected_skills": []interface{}{
			map[string]interface{}{"skill_id": "dialogue"},
		},
	}

	extra := getExtraConfig(config)

	if _, ok := extra["preset"]; ok {
		t.Fatal("preset should not be copied into extra")
	}
	if extra["use_agentic_loop"] != true {
		t.Fatalf("use_agentic_loop was not preserved: %#v", extra["use_agentic_loop"])
	}
	skills, ok := extra["selected_skills"].([]interface{})
	if !ok || len(skills) != 1 {
		t.Fatalf("selected_skills was not preserved: %#v", extra["selected_skills"])
	}
}

func TestGetExtraConfigReturnsNilForKnownFieldsOnly(t *testing.T) {
	extra := getExtraConfig(map[string]interface{}{
		"preset":           "fast",
		"use_agent_system": false,
		"rag_mode":         "simple",
	})

	if extra != nil {
		t.Fatalf("expected nil extra, got %#v", extra)
	}
}
