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
import os
from langchain_google_vertexai import ChatVertexAI, VertexAI
from langchain_community.vectorstores import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain import hub
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"
load_dotenv()


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

    def ExtractInfo(self):
        # Authenticate Gmail
        service = self.authenticate_gmail()
        prompt_template = PromptTemplate(input_variable=["transaction_text"],
                                         template=("""Return the information about the transaction mentioned in the following text.
        Your response should be structured in the JSON format and strictly based on given piece of text.
        {transaction_text}"""),)
        llm  = VertexAI(model_name=os.environ["GEN_MODEL"], project=os.environ["PROJECT_ID"], location=os.environ["REGION"],
                        temperature=0.2, prompt=prompt_template)

        transaction_chain = LLMChain(
            llm=llm,
            prompt=prompt_template
        )
        # Read recent emails
        print("Reading recent emails...")
        date = datetime.datetime.now() - MonthEnd(2)
        date = date.strftime('%Y/%m/%d')
        emails = self.read_emails(service, query=f'after:{date} is:read from:alerts@hdfcbank.net', max_results=5)
        email_data = pd.DataFrame(emails)
        email_data['details'] = email_data["body"].apply(lambda x: transaction_chain.run(transaction_text=x))
        email_data.to_csv("MonthlyTransactionDetails.csv")


if __name__ == '__main__':
    obj = ExtractTransactions()
    obj.ExtractInfo()