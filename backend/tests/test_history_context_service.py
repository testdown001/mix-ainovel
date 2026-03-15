from types import SimpleNamespace

from app.services.history_context_service import HistoryContextService


def test_history_context_service_build_story_skeleton_samples_far_and_near():
    completed_chapters = [
        {"chapter_number": 1, "title": "起点", "summary": "第一章的关键事件。"},
        {"chapter_number": 3, "title": "试探", "summary": "第三章的关键事件。"},
        {"chapter_number": 6, "title": "升级", "summary": "第六章的关键事件。"},
        {"chapter_number": 9, "title": "反转", "summary": "第九章的关键事件。"},
        {"chapter_number": 11, "title": "逼近", "summary": "第十一章的关键事件。"},
    ]

    skeleton = HistoryContextService.build_story_skeleton(completed_chapters, current_chapter=13)

    assert skeleton is not None
    assert "第1章 起点" in skeleton
    assert "第11章 逼近" in skeleton


def test_history_context_service_compress_to_key_event_prefers_first_sentence():
    text = "林玄终于确认了幕后黑手。随后他决定独自赴约，准备反杀。"
    compressed = HistoryContextService.compress_to_key_event(text, max_len=20)
    assert compressed == "林玄终于确认了幕后黑手。"


def test_history_context_service_extract_mission_patterns():
    version = SimpleNamespace(
        metadata_={
            "chapter_mission": {
                "opening_hook_type": "sudden_crisis",
                "chapter_end_style": "cliffhanger",
                "satisfaction_design": {"type": "revenge_payoff"},
            }
        }
    )

    patterns = HistoryContextService.extract_mission_patterns(version)

    assert patterns["opening_hook_type"] == "sudden_crisis"
    assert patterns["chapter_end_style"] == "cliffhanger"
    assert patterns["satisfaction_type"] == "revenge_payoff"
