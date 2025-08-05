import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agents.db")
# It is strongly recommended to load keys from environment variables
# instead of hardcoding them in the source code.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RECIPIENT_URL = os.getenv("RECIPIENT_URL", "https://webhook.site/1ae1e971-df02-4165-b3b4-762afddfbffc")
REPLY_URL = os.getenv("REPLY_URL", "https://webhook.site/1ae1e971-df02-4165-b3b4-762afddfbffc")