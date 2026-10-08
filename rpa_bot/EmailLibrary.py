import os
import smtplib
import mimetypes
from email.message import EmailMessage

class EmailLibrary:
    """
    A lightweight replacement for RPA.Email.ImapSmtp that provides the exact same 
    keywords but without the heavy macOS dependencies that break the installation.
    Maintains a persistent SMTP connection to avoid Gmail rate-limits during bulk sending.
    Supports file attachments (e.g. PDF reports).
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
        
        # Open persistent connection with a 20-second timeout guard
        self.server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=20)
        self.server.starttls()
        self.server.login(self.account, self.password)
        print(f"SMTP connection established for {account}")

    def send_message(self, sender, recipients, subject, body, attachments=None):
        if not self.server:
            raise Exception("SMTP Server not authorized. Call Authorize first.")
            
        # Ensure body is string (handles RF Set Variable returning a list)
        if isinstance(body, (list, tuple)):
            body = "\n".join(str(item) for item in body)
        else:
            body = str(body)

        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = str(subject)
        msg['From'] = str(sender)
        msg['To'] = str(recipients)

        # Handle file attachments (single path string or list of paths)
        if attachments:
            if isinstance(attachments, str):
                attachment_paths = [attachments]
            else:
                attachment_paths = list(attachments)

            for path in attachment_paths:
                if not path or not os.path.exists(path):
                    print(f"⚠️ Attachment file not found: {path}")
                    continue

                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)

                with open(path, 'rb') as f:
                    file_data = f.read()
                    filename = os.path.basename(path)

                msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=filename)
                print(f"📎 Attached file: {filename} ({len(file_data)} bytes)")

        self.server.send_message(msg)
        print(f"Message dispatched to {recipients}")

    def close_connection(self):
        if self.server:
            try:
                self.server.quit()
            except Exception:
                pass
            self.server = None
            print("SMTP connection closed.")

