import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from ..config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, SES_SENDER
from ..utils.logger import logger

def send_email_ses(to_email: str, subject: str, html_body: str, text_body: str = None):
    client = boto3.client(
        "ses",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = 'app@greatmanagerinstitute.com'
    msg["To"] = to_email

    if text_body is None:
        text_body = html_body

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    response = client.send_raw_email(
        Source='app@greatmanagerinstitute.com',
        Destinations=[to_email],
        RawMessage={"Data": msg.as_string()},
    )
    logger.info("SES email sent: %s", response.get("MessageId"))
