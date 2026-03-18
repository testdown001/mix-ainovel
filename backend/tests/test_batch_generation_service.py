from app.services.batch_generation_service import BatchGenerationService


def test_batch_generation_service_build_dependency_map():
    chapter_numbers = [3, 4, 6, 7]
    existing_generated = {1, 2, 5}

    dependencies = BatchGenerationService._build_dependency_map(chapter_numbers, existing_generated)

    assert dependencies[3] is None
    assert dependencies[4] == 3
    assert dependencies[6] is None
    assert dependencies[7] == 6


def test_batch_generation_service_empty_input_returns_empty_map():
    dependencies = BatchGenerationService._build_dependency_map([], {1, 2})
    assert dependencies == {}
