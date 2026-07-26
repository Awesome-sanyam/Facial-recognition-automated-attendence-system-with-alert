from twilio.rest import Client
import logging

class SmsLibrary:
    """
    A lightweight Robot Framework library for sending SMS alerts via Twilio.
    """
    def __init__(self):
        self.client = None
        self.from_number = None

    def authorize_sms(self, account_sid, auth_token, from_number):
        """
        Initializes the Twilio client with credentials.
        """
        # If Twilio credentials are blank or just placeholder text, do not initialize.
        if not account_sid or account_sid.startswith('ACxxx') or not auth_token:
            logging.warning("SMS Authorization failed: Invalid Twilio credentials.")
            return

        try:
            self.client = Client(account_sid, auth_token)
            self.from_number = from_number
        except Exception as e:
            logging.error(f"Failed to initialize Twilio Client: {str(e)}")

    def send_sms(self, to_number, body):
        """
        Sends an SMS message using the authorized Twilio client.
        """
        if not self.client:
            logging.warning(f"Skipping SMS to {to_number}: Twilio client not configured.")
            return
            
        if not to_number or to_number.strip() == "":
            logging.warning("Skipping SMS: No recipient phone number provided.")
            return
            
        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number
            )
            logging.info(f"SMS successfully sent to {to_number}. SID: {message.sid}")
        except Exception as e:
            logging.error(f"Failed to send SMS to {to_number}. Error: {str(e)}")
