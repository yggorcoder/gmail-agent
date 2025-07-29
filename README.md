# Gmail Agent API

This project provides a secure API to store Gmail agent credentials (name, email, client_id, client_secret, refresh_token) with encrypted storage using FastAPI, SQLAlchemy, and Fernet symmetric encryption.

## Features

- Store Gmail agent credentials securely via POST request.
- Credentials are encrypted before being saved to the database.
- Uses SQLite for persistence.
- Easy setup and environment management.
- **Automated email pipeline:**
  - Reads Gmail inbox.
  - Summarizes emails using OpenAI.
  - Generates AI-powered replies with full conversation context.
  - Sends summaries and replies via POST request to external endpoints.
  - Ignores spam and promotional emails automatically.

## Requirements

- Python 3.8+
- pip

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd gmail_agent
    ```

2.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv env
    # On Windows:
    env\Scripts\activate
    # On Linux/Mac:
    source env/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Environment Variables

The API uses a Fernet key for encryption. This key must be set as an environment variable named `FERNET_KEY`.

You must also set your OpenAI API key as `OPENAI_API_KEY` in your environment or `.env` file.

### How to set the Fernet key

1.  You must generate a Fernet key and set it as an environment variable. You can use the following Python code to generate a key:

    ```python
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    print(key.decode())
    ```

2.  Copy the generated key and create a `.env` file in the project root:

    ```
    FERNET_KEY=<your-key>
    OPENAI_API_KEY=<your-openai-key>
    ```

3. The project uses `python-dotenv` to load these variables automatically.

## Usage

1.  **Start the API server:**
    ```bash
    uvicorn main:app --reload
    ```

2.  **Access the interactive API docs** at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

3.  **Use the `POST /agents/` endpoint** to store a new agent. Example payload:

    ```json
    {
      "name": "Agent Name",
      "email_gmail": "agent@gmail.com",
      "client_id": "your-client-id",
      "client_secret": "your-client-secret",
      "refresh_token": "your-refresh-token"
    }
    ```

## Automated Email Pipeline

This project includes a complete pipeline for intelligent email automation. The pipeline:

- Reads recent emails from the Gmail inbox of the configured agent.
- **Filters out promotional and spam emails** automatically (using Gmail labels).
- **Summarizes** each email using OpenAI (GPT-3.5/4).
- **Generates a coherent AI-powered reply** for each email, using the full conversation context (thread history).
- **Sends the summary and the reply** via POST request to external endpoints (configurable).
- **Marks emails as read** after processing to avoid duplicates.

### How it works

- The email processing pipeline is now triggered by a POST request to the `/api/tasks/process-emails/{agent_id}` endpoint.
- This will start a background task that will process up to 5 recent emails (configurable).
- For each email, it will:
  1.  Ignore if labeled as spam or promotion.
  2.  Summarize the email and send the summary to the configured endpoint.
  3.  Fetch the full conversation history (thread) for context.
  4.  Generate a reply using OpenAI, considering the entire conversation.
  5.  Send the reply to the original sender via POST to the configured endpoint.
  6.  Mark the email as read.

### Configuration

- Set the endpoints for summaries and replies in the `.env` file:

  ```
  RECIPIENT_URL="https://your-endpoint.com/receive-summary"
  REPLY_URL="https://your-endpoint.com/receive-reply"
  ```

- You can adjust the number of emails processed by changing `max_results` in the `app/tasks.py` file.

### Customization

- The pipeline can be extended to support multiple agents, advanced filtering, or custom reply logic.
- The context window for conversation history can be adjusted in the `build_conversation_context` function.

## Security Notes

- The Fernet key is **never stored automatically**. You must save it securely and set it in your environment.
- If you lose the Fernet key, you will not be able to decrypt the stored credentials.
- Never share your Fernet key or store it in public repositories.
- Your OpenAI API key should also be kept secret.

## Database

- The database file `agents.db` is created automatically in the project root.
- You can inspect it using [DB Browser for SQLite](https://sqlitebrowser.org/).
- Credentials are stored encrypted (not human-readable).

## Listing Agents (Example)

To list all agents (for debugging), you can use the provided `list_agents.py` script:

```bash
python list_agents.py
```

## License

Yggor Ramos Arruda Herculano
