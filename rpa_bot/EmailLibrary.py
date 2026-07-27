import smtplib
from email.message import EmailMessage

class EmailLibrary:
    """
    A lightweight replacement for RPA.Email.ImapSmtp that provides the exact same 
    keywords but without the heavy macOS dependencies that break the installation.
    Maintains a persistent SMTP connection to avoid Gmail rate-limits during bulk sending.
    """
    def __init__(self, smtp_server='smtp.gmail.com', smtp_port=587):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.account = None
        self.password = None
        self.server = None

    def authorize(self, account, password):
        self.account = account
        self.password = password
        
        # Open persistent connection
        self.server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        self.server.starttls()
        self.server.login(self.account, self.password)
        print(f"SMTP connection established for {account}")

    def send_message(self, sender, recipients, subject, body):
        if not self.server:
            raise Exception("SMTP Server not authorized. Call Authorize first.")
            
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipients

        self.server.send_message(msg)
        print(f"Message dispatched to {recipients}")

    def close_connection(self):
        if self.server:
            self.server.quit()
            self.server = None
            print("SMTP connection closed.")
