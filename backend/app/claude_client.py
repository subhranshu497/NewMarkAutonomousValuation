from anthropic import Anthropic

from app.agent_skills.loader import load_skill
from app.config import get_settings

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


def call_with_skill(skill_name: str, user_content: str, max_tokens: int = 2048) -> str:
    """Injects exactly one skill's instructions as the system prompt for this
    call, keeping each Claude call scoped to only what that step needs
    (DESIGN.md §5 context-assembly principle, applied to prompts)."""
    skill = load_skill(skill_name)
    settings = get_settings()
    response = get_client().messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=skill.instructions,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text
