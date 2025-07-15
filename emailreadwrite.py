import pickle
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import datetime
from pandas.tseries.offsets import MonthEnd
from bs4 import BeautifulSoup
import pandas as pd
from dotenv import load_dotenv
import os
from langchain_google_genai import GoogleGenerativeAI
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)

# If modifying these scopes, delete the file token.pickle.
# SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
#           'https://www.googleapis.com/auth/gmail.send']

class ExtractTransactions:
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.send']

    def authenticate_gmail(self):
        """Authenticate and return Gmail service object"""
        creds = None

        # The file token.pickle stores the user's access and refresh tokens.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    r"C:\Users\Shrimandhar\Downloads\credentials.json", self.scopes)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('gmail', 'v1', credentials=creds)


    def read_emails(self,service, query='', max_results=10):
        """Read emails from Gmail"""
        try:
            # Search for emails
            results = service.users().messages().list(
                userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])

            emails = []
            for message in messages:
                # Get the message details
                msg = service.users().messages().get(
                    userId='me', id=message['id']).execute()

                # Extract email data
                payload = msg['payload']
                headers = payload.get('headers', [])

                # Get subject, sender, date
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'No Date')

                # Get email body
                body = ''
                # if 'parts' in payload:
                for part in payload['parts']:
                    try:
                        if part['mimeType'] == 'text/html':
                            data = part['body']['data']
                            body = base64.urlsafe_b64decode(data).decode('utf-8')
                            soup = BeautifulSoup(body, 'html.parser')
                            plain_text = soup.get_text().replace('\n','')
                        elif part['mimeType'] == 'text/plain':
                            data = part['body']['data']
                            plain_text = base64.urlsafe_b64decode(data).decode('utf-8')
                        else:
                            pass
                    except:
                        plain_text = ''
                # else:
                #     if payload['mimeType'] == 'text/html':
                #         data = payload['body']['data']
                #         plain_text = base64.urlsafe_b64decode(data).decode('utf-8')

                emails.append({
                    'id': message['id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': plain_text
                })

            return emails

        except Exception as error:
            print(f'An error occurred: {error}')
            return []


    # def send_email(self, service, to_email, subject, body):
    #     """Send an email using Gmail API"""
    #     try:
    #         # Create message
    #         message = MIMEMultipart()
    #         message['to'] = to_email
    #         message['subject'] = subject
    #
    #         # Add body to email
    #         message.attach(MIMEText(body, 'plain'))
    #
    #         # Encode the message
    #         raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    #
    #         # Send the message
    #         send_message = service.users().messages().send(
    #             userId='me', body={'raw': raw_message}).execute()
    #
    #         print(f'Message sent successfully. Message ID: {send_message["id"]}')
    #         return send_message
    #
    #     except Exception as error:
    #         print(f'An error occurred: {error}')
    #         return None


    def ExtractInfo(self):
        # Authenticate Gmail
        for model in genai.list_models():
            print(f"Model name: {model.name}")
            print(f"  Supported versions: {model.supported_generation_methods}")
        service = self.authenticate_gmail()
        llm = GoogleGenerativeAI(model="models/gemini-1.5-pro-latest", google_api_key=GEMINI_API_KEY)


        # Confirm connection
        status = llm.invoke("who is president of usa?")

        # Read recent emails
        print("Reading recent emails...")
        date = datetime.datetime.now() - MonthEnd(2)
        date = date.strftime('%Y/%m/%d')
        emails = self.read_emails(service, query=f'after:{date} is:read from:alerts@hdfcbank.net', max_results=100)
        email_data = pd.DataFrame(emails)


        # # Send an email
        # print("\nSending email...")
        # send_email(
        #     service,
        #     'mshrimandhar@gmail.com',
        #     'Test Subject',
        #     'This is a test email sent using Gmail API!'
        # )


if __name__ == '__main__':
    obj = ExtractTransactions()
    obj.ExtractInfo()