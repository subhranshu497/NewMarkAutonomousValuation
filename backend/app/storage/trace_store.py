from app.schemas.result import ValuationResponse

# In-memory, process-local store — an intentional MVP gap (DESIGN.md FR9
# calls for durable, retained audit trace; this proves the loop end-to-end
# first). Swapping to real persistence later only touches this module.
_responses: dict[str, ValuationResponse] = {}


def save_result(response: ValuationResponse) -> None:
    _responses[response.request_id] = response


def get_result(request_id: str) -> ValuationResponse | None:
    return _responses.get(request_id)
