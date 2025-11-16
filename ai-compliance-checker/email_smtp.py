import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(subject, body, recipients, smtp_server, smtp_port, smtp_user, smtp_password):
    """
    Sends an email using SMTP.
    Returns a dictionary with status and message.
    """

    try:
        # Email message setup
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        # Connect to SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        # Send email
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()

        return {
            "status": "sent",
            "message": "Email sent successfully",
            "recipients": recipients
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "recipients": recipients
        }
