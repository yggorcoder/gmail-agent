from app.openai_service import generate_text

def generate_email_summary(email_body: str, language: str = "pt") -> str:
    prompt = (
        f"Please summarize the following email very accurately., "
        f"keeping only the essential information, in a maximum of 5 lines. "
        f"Answer in the language: {language}.\n\nE-mail:\n{email_body}"
    )
    return generate_text(prompt)
