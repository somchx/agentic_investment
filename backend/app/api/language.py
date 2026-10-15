from fastapi import Request


def ui_language(request: Request) -> str | None:
    """The language the frontend is showing (it sends Accept-Language from its
    own language toggle), so paid LLM runs write their free text in it."""
    header = request.headers.get("accept-language", "").strip().lower()
    return "th" if header.startswith("th") else None
