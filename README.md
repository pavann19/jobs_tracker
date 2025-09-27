# AI-Powered Job Application Tracker

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

This project is a Python script that fully automates the process of tracking job applications. It scans your Gmail account to intelligently find applications you've sent and replies you've received, then logs everything to a CSV file. The script uses Google's Gemini AI to understand the content of your emails, extracting key information like company name, job role, and application status.

---
### Key Features 🚀

* **Automatic Discovery**: Scans your "Sent" mail to automatically find new job applications you've sent.
* **Intelligent AI Analysis**: Uses the Gemini AI to accurately extract the **Company Name** and **Job Role** from unstructured email text.
* **Status Tracking**: Monitors your inbox for replies and automatically updates the status of your applications to "Interviewing," "Rejected," or "Offer."
* **"Just-in-Time" History**: If a reply comes from an old, untracked application, the script automatically searches your email history to find and log the original application.
* **CSV Logging**: Keeps a clean, organized record of all your applications in a `job_applications_auto.csv` file.

---
###  How It Works ⚙️

The script uses a combination of the **Gmail API** to read your emails and the **Gemini API** for content analysis. It runs in two main phases:
1.  **Sent Scan**: It first looks for recent applications you've sent to build a list of your current job searches.
2.  **Inbox Scan**: It then checks for replies related to your applications. If a reply is for a new company, it triggers a targeted history search to backfill the data.

---
###  Setup and Installation

Follow these steps to get the script running.

#### 1. Prerequisites
* Python 3.9 or newer.
* A Google account (Gmail).

#### 2. Clone or Download
Download the `job_tracker_auto.py` and `requirements.txt` files from this repository.

#### 3. Install Dependencies
Navigate to the project folder in your terminal and run the following command to install the required Python libraries:
```bash
pip install -r requirements.txt
```

#### 4. Google Cloud & Gmail API Setup
You need to get a `credentials.json` file to allow the script to access your Gmail.
* Go to the [Google Cloud Console](https://console.cloud.google.com/).
* Create a new project.
* Enable the **Gmail API**.
* Create an **OAuth 2.0 Client ID** for a **Desktop app**.
* Download the JSON file and rename it to `credentials.json`. Place this file in the same folder as the script.

#### 5. Gemini AI API Key
The script needs an API key to use the AI model.
* Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and create a free API key.
* **Important**: Do **not** paste the key directly into the script. Instead, set it as an environment variable.

    * **On Windows (PowerShell):**
        ```powershell
        [System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'YOUR_API_KEY_HERE', 'User')
        ```
        *(Close and reopen your terminal after running this command.)*

    * **On macOS/Linux:**
        ```bash
        echo "export GEMINI_API_KEY='YOUR_API_KEY_HERE'" >> ~/.zshrc
        # (Or ~/.bashrc depending on your shell. Then run 'source ~/.zshrc')
        ```

#### 6. First Run & Authorization
You must run the script manually once to grant it permission to access your Gmail.
* Run the script from your terminal:
    ```bash
    python job_tracker_auto.py
    ```
* The script will print a URL. Copy it and paste it into your web browser.
* Log in to your Google account and grant the requested permissions.
* Google will give you an authorization code. Copy this code and paste it back into your terminal.
* This will create a `token.json` file in your folder, which will handle authentication automatically from now on.

---
### ## Usage

After the one-time setup, you can run the script whenever you want to check for updates. For full automation, you should schedule it to run automatically.

* **On Windows**: Use **Task Scheduler**.
* **On macOS/Linux**: Use **cron**.

Set the task to run the `python job_tracker_auto.py` command once or twice a day.

## Important: Create a requirements.txt File

For the setup instructions to work perfectly, you should also add a file named requirements.txt to your GitHub repository.

Create a new file named requirements.txt and paste the following lines into it:

```
google-generativeai
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
```
# jobs_tracker
