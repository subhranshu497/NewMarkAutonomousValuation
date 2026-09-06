import json
import re

from anthropic import AsyncAnthropic

from app.agent_skills.loader import load_skill
from app.config import get_settings

_client: AsyncAnthropic | None = None

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def call_with_skill(skill_name: str, user_content: str, max_tokens: int = 2048) -> str:
    """Injects exactly one skill's instructions as the system prompt for this
    call, keeping each Claude call scoped to only what that step needs
    (DESIGN.md §5 context-assembly principle, applied to prompts)."""
    skill = load_skill(skill_name)
    settings = get_settings()
    response = await get_client().messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=skill.instructions,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def extract_json(text: str) -> dict:
    """Claude is instructed to return bare JSON, but strip a ```json fence
    if it adds one anyway."""
    fenced = _JSON_FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Expected JSON from Claude, got: {text!r}") from exc
