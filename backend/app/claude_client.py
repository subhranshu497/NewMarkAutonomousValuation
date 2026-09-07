import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent_skills.loader import load_skill
from app.config import get_settings

_client: ChatAnthropic | None = None

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def get_client() -> ChatAnthropic:
    """LangChain's chat-model wrapper around the Anthropic API. This is the
    only LLM transport the orchestration hub's two agent nodes use — kept
    behind the same call_with_skill(name, content) contract so swapping the
    underlying SDK never touches app/agents or app/orchestrator."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = ChatAnthropic(model=settings.claude_model, api_key=settings.anthropic_api_key, max_retries=2)
    return _client


async def call_with_skill(skill_name: str, user_content: str, max_tokens: int = 2048) -> str:
    """Injects exactly one skill's instructions as the system prompt for this
    call, keeping each Claude call scoped to only what that step needs
    (DESIGN.md §5 context-assembly principle, applied to prompts)."""
    skill = load_skill(skill_name)
    response = await get_client().ainvoke(
        [SystemMessage(content=skill.instructions), HumanMessage(content=user_content)],
        max_tokens=max_tokens,
    )
    return _content_to_text(response.content)


def _content_to_text(content: str | list) -> str:
    """AIMessage.content is a plain string for simple text replies, but the
    LangChain interface allows a list of content blocks — normalize both
    shapes so callers always get a plain string to run extract_json on."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def extract_json(text: str) -> dict:
    """Claude is instructed to return bare JSON, but strip a ```json fence
    if it adds one anyway."""
    fenced = _JSON_FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Expected JSON from Claude, got: {text!r}") from exc
