import smtplib
from email.message import EmailMessage

class EmailLibrary:
    """
    A lightweight replacement for RPA.Email.ImapSmtp that provides the exact same 
    keywords but without the heavy macOS dependencies that break the installation.
    """
    def __init__(self, smtp_server='smtp.gmail.com', smtp_port=587):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.account = None
        self.password = None

    def authorize(self, account, password):
        self.account = account
        self.password = password

    def send_message(self, sender, recipients, subject, body):
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipients

        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.account, self.password)
        server.send_message(msg)
        server.quit()
