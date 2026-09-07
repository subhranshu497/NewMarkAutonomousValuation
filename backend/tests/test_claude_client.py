from types import SimpleNamespace

import pytest

from app import claude_client


class FakeChatModel:
    """Stands in for the LangChain ChatAnthropic client so tests never make
    real network calls."""

    def __init__(self, content):
        self._content = content
        self.calls = []

    async def ainvoke(self, messages, max_tokens=None):
        self.calls.append((messages, max_tokens))
        return SimpleNamespace(content=self._content)


@pytest.mark.anyio
async def test_call_with_skill_sends_system_and_human_messages(monkeypatch):
    fake = FakeChatModel("plain text response")
    monkeypatch.setattr(claude_client, "get_client", lambda: fake)

    result = await claude_client.call_with_skill("query-formulation", "hello")

    assert result == "plain text response"
    messages, max_tokens = fake.calls[0]
    assert max_tokens == 2048
    assert "Query Formulation" in messages[0].content or len(messages[0].content) > 0
    assert messages[1].content == "hello"


@pytest.mark.anyio
async def test_call_with_skill_passes_through_max_tokens(monkeypatch):
    fake = FakeChatModel("ok")
    monkeypatch.setattr(claude_client, "get_client", lambda: fake)

    await claude_client.call_with_skill("valuation-synthesis", "content", max_tokens=512)

    _, max_tokens = fake.calls[0]
    assert max_tokens == 512


def test_content_to_text_handles_plain_string():
    assert claude_client._content_to_text("hello") == "hello"


def test_content_to_text_handles_block_list():
    blocks = [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]
    assert claude_client._content_to_text(blocks) == "hello world"


def test_content_to_text_ignores_non_text_blocks():
    blocks = [{"type": "tool_use", "id": "x"}, {"type": "text", "text": "answer"}]
    assert claude_client._content_to_text(blocks) == "answer"


def test_extract_json_strips_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert claude_client.extract_json(text) == {"a": 1}


def test_extract_json_handles_bare_json():
    assert claude_client.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_raises_on_invalid_json():
    with pytest.raises(ValueError):
        claude_client.extract_json("not json")
