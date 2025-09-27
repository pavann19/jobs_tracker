# Final Version v4.1: job_tracker_auto.py (Secure and Corrected)

import os
import re
import csv
from datetime import date, datetime
import time
import json
import google.generativeai as genai

# --- 1. SECURELY LOAD API KEY ---
API_KEY = os.getenv('GEMINI_API_KEY')

if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not found.")
    print("Please follow the instructions to set up your API key securely.")
    exit()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-pro-latest')

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
FILENAME = 'job_applications_auto.csv'
HEADERS = ['Company Name', 'Application Date', 'Role', 'Status', 'Notes']
PROCESSED_LABEL_NAME = 'JobTracker-Processed'

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

def get_gmail_service():
    """Authenticates with Gmail API and returns the service object."""
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
            if new_status_value >= current_status_value: app['Status'] = new_status
            if notes: app['Notes'] = notes
            company_found = True
            break
    if not company_found:
        new_app = {
            'Company Name': company_name, 'Application Date': application_date if application_date else date.today().strftime('%Y-%m-%d'), 
            'Role': role, 'Status': new_status, 'Notes': notes
        }
        applications.append(new_app)
        print(f"✅ Discovered application for: {company_name} ({role})")
    sorted_applications = sorted(applications, key=lambda x: x['Application Date'], reverse=True)
    with open(FILENAME, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(sorted_applications)
    print(f"✅ CSV Updated: '{company_name} ({role})' status set to '{new_status}'")

# --- FINAL Resilient AI Analysis Function ---
def analyze_email_with_ai(email_content):
    """Sends email text to the Gemini AI, with automatic retries for rate limits."""
    
    prompt = f"""
    Analyze the following email text from a job seeker's email account.
    Your task is to extract three pieces of information:
    1. The name of the company involved. Be as precise as possible.
    2. The specific job role or title (e.g., "Software Engineer", "Data Scientist").
    3. The status of the application.

    The status can only be one of these five options: "Applied", "Interviewing", "Rejected", "Offer", "Unknown".

    - If the user is sending their application, the status is "Applied".
    - If a reply invites the user to talk, the status is "Interviewing".
    - If a reply says they are not moving forward, the status is "Rejected".
    - If a reply contains a job offer, the status is "Offer".

    Return your answer in a strict JSON format. If a value cannot be found, use "Unknown".
    Example: {{"company_name": "Google", "role": "Software Engineer", "status": "Interviewing"}}

    Here is the email text:
    ---
    {email_content}
    ---
    """
    
    retries = 3 # Number of times to retry before giving up
    for i in range(retries):
        try:
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            data = json.loads(json_text)
            return data.get("company_name"), data.get("role"), data.get("status")
        except Exception as e:
            # Check if the exception is due to a rate limit error (429)
            if "429" in str(e):
                print("⏳ Rate limit reached. Waiting for 61 seconds before retrying...")
                time.sleep(61) # Wait for a full minute plus one second
                continue # Go to the next iteration of the loop to retry
            else:
                print(f"An unexpected error occurred: {e}")
                return None, None, None # Return None for other errors
    
    print("❌ Failed to analyze with AI after several retries due to persistent errors.")
    return None, None, None

def find_original_application(service, label_id, company_name, role):
    print(f"-> Searching history for original application to '{company_name}' for role '{role}'...")
    query = f'from:me "{company_name}"'
    response = service.users().threads().list(userId='me', q=query).execute()
    threads = response.get('threads', [])
    if threads:
        thread = service.users().threads().get(userId='me', id=threads[0]['id']).execute()
        original_message = thread['messages'][0]
        timestamp_ms = int(original_message.get('internalDate', 0))
        application_date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
        update_csv(company_name, role, "Applied", application_date=application_date)
        for message in thread['messages']:
             service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
        return True
    print(f"-> Could not find original application for '{company_name}'.")
    return False

def process_emails(service, label_id, folder):
    print(f"\n--- AI Scan: Searching '{folder}' folder... ---")
    
    # Logic to handle different queries for sent vs. inbox
    if folder == "sent":
        query = f'from:me newer_than:7d -label:{PROCESSED_LABEL_NAME}'
    else: # inbox
        query = f'in:inbox newer_than:7d -label:{PROCESSED_LABEL_NAME}'

    response = service.users().threads().list(userId='me', q=query).execute()
    threads = response.get('threads', [])
    if not threads: 
        print(f"No new threads found in {folder}.")
        return

    for thread_info in threads:
        thread = service.users().threads().get(userId='me', id=thread_info['id']).execute()
        
        # In the inbox, we look at the last message. In sent, the first.
        message = thread['messages'][-1] if folder == "inbox" else thread['messages'][0]

        if label_id in message.get('labelIds', []): continue

        subject = next((h['value'] for h in message['payload']['headers'] if h['name'].lower() == 'subject'), '')
        snippet = message.get('snippet', '')
        company_name, role, status = analyze_email_with_ai(f"Subject: {subject}\nBody: {snippet}")

        if company_name and role and status and "Unknown" not in [company_name, role, status]:
            if folder == "sent":
                if status == "Applied":
                    update_csv(company_name, role, status)
                    service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
                    time.sleep(31)
            elif folder == "inbox":
                if status != "Applied":
                    companies_db = []
                    if os.path.exists(FILENAME):
                        with open(FILENAME, 'r', newline='', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader: companies_db.append(row)
                    is_tracked = any(c['Company Name'].lower() == company_name.lower() and c['Role'].lower() == role.lower() for c in companies_db)
                    if not is_tracked:
                        if not find_original_application(service, label_id, company_name, role): continue
                    update_csv(company_name, role, status)
                    service.users().messages().modify(userId='me', id=message['id'], body={'addLabelIds': [label_id]}).execute()
                    time.sleep(61)

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
    
    # --- Corrected Main Execution Logic ---
    process_emails(service, label_id, "sent")
    process_emails(service, label_id, "inbox")
    
    print("\n✅ AI Automation check complete.")
