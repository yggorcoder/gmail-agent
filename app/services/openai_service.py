from app.apis.openai_api import generate_text as call_openai_api

def generate_text(prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 300, temperature: float = 0.2) -> str:
    """
    Função de serviço que chama a API da OpenAI.
    """
    return call_openai_api(prompt, model, max_tokens, temperature)
