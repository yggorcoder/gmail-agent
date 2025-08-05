from app.apis.gmail_api import get_gmail_service, send_email, mark_email_as_read
from fastapi import HTTPException, status
import re 
import base64



# Scopes required to interact with Gmail (must be consistent with what has been authorized)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

def fetch_recent_emails(client_id: str, client_secret: str, refresh_token: str, max_results: int = 5):
    """
    Fetches the most recent emails from the Gmail inbox, ignoring promotions, spam,
    and other categories, and specific senders.
    Returns a list of dictionaries with sender, subject, body, and labels.
    """
    service = get_gmail_service(client_id, client_secret, refresh_token)
    
    try:
        # Removed labelIds=['INBOX'] to fetch emails from all categories and filter later
        results = service.users().messages().list(userId='me', maxResults=max_results).execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar e-mails: {e}"
        )

    messages = results.get('messages', [])
    emails = []
    
    # Set email categories to ignore
    IGNORED_CATEGORIES = [
        'CATEGORY_PROMOTIONS',
        'CATEGORY_SOCIAL',
        'CATEGORY_UPDATES', # Meta emails often land here
        'CATEGORY_FORUMS',
        'SPAM'
    ]

    # Define specific senders to ignore (case-insensitive)
    # Add the email addresses or domains you want to ignore here
    IGNORED_SENDERS = [
        'security@facebookmail.com',
        'noreply@mail.instagram.com',
        'facebookmail.com', # Domains to grab multiple emails from the same source
        'instagram.com',
        'meta.com',
        'mail.meta.com',
        # Add other senders or domains as needed
    ]

    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            label_ids = msg_data.get('labelIds', [])
            
            should_ignore = False

            # Filter by category (if the email has any of the ignored categories)
            for label in label_ids:
                if label in IGNORED_CATEGORIES:
                    should_ignore = True
                    break

            # Filter by sender (if not already ignored by category)
            if not should_ignore:
                # Extract only the sender's email address (if name is present, e.g. "Name <email@example.com>")
                sender_email_match = re.search(r'<([^>]+)>', sender)
                sender_address = sender_email_match.group(1).lower() if sender_email_match else sender.lower()

                for ignored_sender in IGNORED_SENDERS:
                    # Checks if the ignored sender is contained in the sender's email address
                    if ignored_sender.lower() in sender_address:
                        should_ignore = True
                        break

            if should_ignore:
                print(f"Ignorando e-mail indesejado: '{subject}' de '{sender}' (Labels: {label_ids})")
                # Mark as read to not process again in future runs
                mark_email_as_read(service, msg['id'])
                continue # Skip to the next email
            
            # Extract email body (plain text only)
            body = ''
            if 'parts' in msg_data['payload']:
                for part in msg_data['payload']['parts']:
                    if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            else:
                if 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
                    body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8')
            
            emails.append({
                'id': msg['id'],
                'threadId': msg['threadId'],
                'subject': subject,
                'from': sender,
                'body': body,
                'labelIds': label_ids
            })
        except Exception as e:
            print(f"Erro ao processar mensagem {msg.get('id', 'N/A')}: {e}")
            continue
    return emails


