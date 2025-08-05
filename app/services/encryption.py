import os
from cryptography.fernet import Fernet

def get_cipher_suite():
    encryption_key = os.getenv("SECRET_KEY_ENCRYPTION")
    if encryption_key is None:
        raise ValueError("SECRET_KEY_ENCRYPTION environment variable not set.")
    return Fernet(encryption_key.encode()) # Converts the string back to bytes