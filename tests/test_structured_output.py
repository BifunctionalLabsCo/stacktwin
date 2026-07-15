from stacktwin.llm.structured import parse_json_value, response_content


def test_parse_json_value_accepts_plain_json_and_markdown_fences():
    assert parse_json_value('{"overall": 0.9}') == {"overall": 0.9}
    assert parse_json_value('```json\n{"overall": 0.9}\n```') == {"overall": 0.9}


def test_parse_json_value_recovers_json_after_model_prose():
    assert parse_json_value('Here is the result: {"items": ["fastapi"]}') == {
        "items": ["fastapi"]
    }


def test_response_content_handles_empty_reasoning_response():
    assert response_content({"choices": [{"message": {"content": None}}]}) == ""
