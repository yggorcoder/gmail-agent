from app.openai_service import generate_text

def generate_email_response(email_body: str, context: str = "", language: str = "pt") -> str:
    """
    Generates a polite, clear, objective, and coherent email response based on the provided email body
and optional context.

    Args:
        email_body (str): The content of the received email that requires a response.
        context (str, optional): Additional information or context relevant to the response.
    Default is an empty string.
    language (str, optional): The desired language for the response (e.g., "pt" for Portuguese,
    "en" for English). Default is "pt".

    Returns:
        str: The AI generated email response.
    """
    # Construct the context part separately to avoid the nested f-string error with '\n'
    context_part = ""
    if context:
        context_part = f'Contexto adicional: {context}\n'

    prompt = f"""Você recebeu o seguinte e-mail:

{email_body}

{context_part}
Responda de forma educada, clara, objetiva e coerente, como se fosse o destinatário original.
A resposta deve ser apropriada para enviar ao remetente do e-mail.
Responda no idioma: {language}."""

    return generate_text(prompt, max_tokens=400, temperature=0.3)
