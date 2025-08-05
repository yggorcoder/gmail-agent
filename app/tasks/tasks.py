from app.apis.database_connection import SessionLocal
from app.models.gmail_agents import GmailAgent
from app.services.encryption import get_cipher_suite
from app.services.gmail_service import fetch_recent_emails, get_gmail_service, mark_email_as_read, send_email
from app.apis.gmail_api import fetch_thread_history
from app.services.summary_gen import generate_email_summary
from app.services.response_gen import generate_email_response

def build_conversation_context(history, max_messages=6):
    """
    Builds a textual context of the conversation for the AI, using the latest messages in the thread.
    """
    context = "Conversa até agora:\n"
    for msg in history[-max_messages:]:
        sender = msg['from']
        body = msg['body'].strip().replace('\n', ' ')
        context += f"{sender}: {body}\n"
    context += "---\n"
    return context

def process_emails_task(agent_id: int):
    db = SessionLocal()
    try:
        agent = db.query(GmailAgent).filter(GmailAgent.id == agent_id).first()
        if not agent:
            print(f"Agent with ID {agent_id} not found.")
            return

        cipher = get_cipher_suite()
        # Descriptografe client_id, client_secret e refresh_token
        # Make sure these fields are encrypted bytes in the DB
        try:
            client_id = cipher.decrypt(agent.client_id).decode()
            client_secret = cipher.decrypt(agent.client_secret).decode()
            refresh_token = cipher.decrypt(agent.refresh_token).decode()
        except Exception as e:
            print(f"Error decrypting credentials for agent {agent_id}: {e}")
            print("Verify that the credentials were saved correctly and that the SECRET_KEY_ENCRYPTION is correct.")
            return # Exit the function if decryption fails
        service = get_gmail_service(client_id, client_secret, refresh_token)

        # Search for recent emails (the unwanted category and sender filter is already in gmail_service)
        # max_results here defines how many emails will be searched per task run.
        # If you want the consolidated summary to always be 5 emails, even if there are more,
        # you can keep max_results=5. If you want to process more emails in a single run
        # and generate multiple consolidated summaries of 5, increase this value.
        emails = fetch_recent_emails(client_id, client_secret, refresh_token, max_results=10) # Aumentado para 10 para ter mais chance de pegar 5
        
        if not emails:
            print(f"Nenhum e-mail recente para processar para o agente {agent_id}.")
            return # Exit if there are no emails to process

        # Variables for the consolidated summary
        consolidated_summaries_content = []
        processed_email_count = 0

        for email in emails:
            # Promotions and spam/category/unwanted senders filtering is already in fetch_recent_emails,
            # and ignored emails are already marked as read there.
            # So, if an email reached this point, it should be processed.
            
            print(f"Processando e-mail: {email['subject']}")

            # --- Generate Individual Summary and Add to Consolidated List ---
            individual_summary = generate_email_summary(email['body'])
            consolidated_summaries_content.append(
                f"Assunto: {email['subject']}\nRemetente: {email['from']}\nSumário: {individual_summary}\n---"
            )
            processed_email_count += 1

            # --- Generate and Send Reply (individual to original sender) ---
            thread_id = email.get('threadId')
            context = ""
            if thread_id:
                history = fetch_thread_history(service, thread_id)
                context = build_conversation_context(history)
            
            reply_body = generate_email_response(email['body'], context=context)
            reply_subject = f"Re: {email['subject']}" # Add "Re:" to indicate reply

            try:
                # Send the reply to the original sender of the email
                send_email(service, 
                           to_email=email["from"], 
                           from_email=agent.email_gmail, # The agent is the sender
                           subject=reply_subject, 
                           message_body=reply_body,
                           thread_id=thread_id) # Ensures the reply is in the same thread

                print(f"Response sent to {email['from']}! Subject: {reply_subject}")
            except Exception as e:
                print(f"Error sending response: {e}")

            # Mark email as read after processing (individually)
            mark_email_as_read(service, email['id'])
            
            # --- Verify that 5 emails were processed for the consolidated summary ---
            if processed_email_count >= 5: # Use >= to ensure the summary is sent even if more than 5 are processed in a single call
                print(f"Generating consolidated summary for the last {processed_email_count} e-mails...")
                full_summary_text_for_consolidation = "\n\n".join(consolidated_summaries_content)
                
                # Use generate_email_summary to consolidate individual summaries
                consolidated_summary_final = generate_email_summary(
                    f"Consolidate the following email summaries into a single coherent summary:\n\n{full_summary_text_for_consolidation}"
                )
                
                consolidated_subject = f"Consolidated Email Summary ({processed_email_count} e-mails)"
                
                try:
                    # Send the consolidated summary to the agent owner
                    send_email(service, 
                               to_email=agent.email_gmail, 
                               from_email=agent.email_gmail,
                               subject=consolidated_subject, 
                               message_body=consolidated_summary_final)
                    print(f"Consolidated summary sent to{agent.email_gmail}!")
                except Exception as e:
                    print(f"Error sending consolidated summary: {e}")
                
                # Reset counters for the next batch of 5 emails
                consolidated_summaries_content = []
                processed_email_count = 0

    except Exception as e:
        print(f"General error processing emails for the agent {agent_id}: {e}")
    finally:
        db.close()




