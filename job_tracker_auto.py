# Final Version v4.0: job_tracker_auto.py (Intelligent History)

import os
import re
import csv
from datetime import date, datetime
import time
import json
import google.generativeai as genai

# --- 1. SET UP YOUR API KEY ---
# IMPORTANT: Paste your API key you got from Google AI Studio here.
API_KEY = 'AIzaSyBCpLFDbmskBw0T3ahkkr9lpqNRbGcPgHE' 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-pro-latest')

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
FILENAME = 'job_applications_auto.csv'
HEADERS = ['Company Name', 'Application Date', 'Role', 'Status', 'Notes']
PROCESSED_LABEL_NAME = 'JobTracker-Processed'

# (get_gmail_service is unchanged)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# --- NEW: update_csv can now handle past dates ---
def update_csv(company_name, role, new_status, notes="", application_date=None):
    status_order = {"Applied": 1, "Interviewing": 2, "Offer": 3, "Rejected": 4}
    applications = []
    file_exists = os.path.exists(FILENAME)
    if file_exists:
        with open(FILENAME, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader: applications.append(row)

    company_found = False
    for app in applications:
        if app['Company Name'].lower() == company_name.lower() and app['Role'].lower() == role.lower():
            current_status_value = status_order.get(app['Status'], 0)
            new_status_value = status_order.get(new_status, 0)
            if new_status_value >= current_status_value:
                app['Status'] = new_status
            if notes: app['Notes'] = notes
            company_found = True
            break
            
    if not company_found:
        new_app = {
            'Company Name': company_name, 
            'Application Date': application_date if application_date else date.today().strftime('%Y-%m-%d'), 
            'Role': role,
            'Status': new_status, 
            'Notes': notes
        }
        applications.append(new_app)
        print(f"✅ Discovered application for: {company_name} ({role})")

    # Sort data by date before writing
    sorted_applications = sorted(applications, key=lambda x: x['Application Date'], reverse=True)

    with open(FILENAME, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(sorted_applications)
    print(f"✅ CSV Updated: '{company_name} ({role})' status set to '{new_status}'")

# (analyze_email_with_ai is unchanged)
def analyze_email_with_ai(email_content):
    prompt = f"""
    Analyze the following email text from a job seeker's email account.
    Your task is to extract three pieces of information:
    1. The name of the company involved.
    2. The specific job role or title (e.g., "Software Engineer", "Data Scientist").
    3. The status of the application.
    The status can only be one of these five options: "Applied", "Interviewing", "Rejected", "Offer", "Unknown".
    Return your answer in a strict JSON format. If a value cannot be found, use "Unknown".
    Example: {{"company_name": "Google", "role": "Software Engineer", "status": "Interviewing"}}
    Here is the email text:
    ---
    {email_content}
    ---
    """
    try:
        response = model.generate_content(prompt)
        json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(json_text)
        return data.get("company_name"), data.get("role"), data.get("status")
    except Exception as e:
        print(f"Error analyzing with AI: {e}")
        return None, None, None

# --- NEW: More flexible function to find the original application ---
def find_original_application(service, label_id, company_name, role):
    print(f"-> Searching history for original application to '{company_name}' for role '{role}'...")
    
    # --- KEY CHANGE HERE: A much more flexible search query ---
    # This now searches for any sent email that simply mentions the company name.
    query = f'from:me "{company_name}"'
    
    response = service.users().threads().list(userId='me', q=query).execute()
    threads = response.get('threads', [])

    if threads:
        # Assume the first result is the most relevant thread
        thread = service.users().threads().get(userId='me', id=threads[0]['id']).execute()
        # Assume the first message in the thread is the original application
        original_message = thread['messages'][0]
        
        timestamp_ms = int(original_message.get('internalDate', 0))
        application_date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
        
        # Add this historical application to the CSV with "Applied" status and the correct past date
        update_csv(company_name, role, "Applied", application_date=application_date)
        
        # Label all messages in the thread as processed to avoid re-scanning
        for message in thread['messages']:
             service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
        return True

    print(f"-> Could not find original application for '{company_name}'.")
    return False

# --- NEW: Greatly improved email processing logic ---
def process_emails(service, label_id):
    # Step 1: Discover new applications from SENT folder
    print("\n--- AI Scan: Searching 'sent' folder for new applications... ---")
    query_sent = f'from:me newer_than:7d -label:{PROCESSED_LABEL_NAME}'
    response_sent = service.users().threads().list(userId='me', q=query_sent).execute()
    threads_sent = response_sent.get('threads', [])
    if not threads_sent: print("No new sent applications found.")
    for thread_info in threads_sent:
        # Simplified logic for sent items: we only need the first message
        thread = service.users().threads().get(userId='me', id=thread_info['id']).execute()
        message = thread['messages'][0]
        if label_id in message.get('labelIds', []): continue
        subject = next((h['value'] for h in message['payload']['headers'] if h['name'].lower() == 'subject'), '')
        snippet = message.get('snippet', '')
        company_name, role, status = analyze_email_with_ai(f"Subject: {subject}\nBody: {snippet}")
        if company_name and role and status and status == "Applied":
            update_csv(company_name, role, status)
            service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
            time.sleep(31)

    # Step 2: Process replies from INBOX and backfill history if needed
    print("\n--- AI Scan: Searching 'inbox' folder for replies... ---")
    companies_db = []
    if os.path.exists(FILENAME):
        with open(FILENAME, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader: companies_db.append(row)

    query_inbox = f'in:inbox newer_than:7d -label:{PROCESSED_LABEL_NAME}'
    response_inbox = service.users().threads().list(userId='me', q=query_inbox).execute()
    threads_inbox = response_inbox.get('threads', [])
    if not threads_inbox: print("No new emails in inbox to process.")
    for thread_info in threads_inbox:
        # Process the most recent message in the thread
        thread = service.users().threads().get(userId='me', id=thread_info['id']).execute()
        message = thread['messages'][-1]
        if label_id in message.get('labelIds', []): continue
        subject = next((h['value'] for h in message['payload']['headers'] if h['name'].lower() == 'subject'), '')
        snippet = message.get('snippet', '')
        company_name, role, status = analyze_email_with_ai(f"Subject: {subject}\nBody: {snippet}")
        
        if company_name and role and status and status != "Applied" and status != "Unknown":
            # Check if we are already tracking this company and role
            is_tracked = any(c['Company Name'].lower() == company_name.lower() and c['Role'].lower() == role.lower() for c in companies_db)
            
            if not is_tracked:
                # If not tracked, find the original application in history FIRST
                found_history = find_original_application(service, label_id, company_name, role)
                if not found_history: continue # Skip if we can't find the original
            
            # Now, update the status with the reply info
            update_csv(company_name, role, status)
            service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
            time.sleep(31)

# (Main execution block is unchanged)
if __name__ == '__main__':
    service = get_gmail_service()
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    label_id = next((l['id'] for l in labels if l['name'] == PROCESSED_LABEL_NAME), None)
    if not label_id:
        label_body = {'name': PROCESSED_LABEL_NAME, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
        created_label = service.users().labels().create(userId='me', body=label_body).execute()
        label_id = created_label['id']
        print(f"Created Gmail label: '{PROCESSED_LABEL_NAME}'")
    
    process_emails(service, label_id) # Simplified call
    
    print("\n✅ AI Automation check complete.")
