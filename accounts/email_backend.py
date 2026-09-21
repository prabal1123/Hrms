import logging
import os

from azure.communication.email import EmailClient
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class AzureEmailBackend(BaseEmailBackend):
    """Django email backend that sends through Azure Communication Services Email.

    Reads AZURE_EMAIL_CONNECTION_STRING and AZURE_EMAIL_SENDER from the
    environment. Always sends from AZURE_EMAIL_SENDER, because Azure only
    accepts the verified sender address.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.connection_string = os.environ.get("AZURE_EMAIL_CONNECTION_STRING", "").strip()
        self.sender = os.environ.get("AZURE_EMAIL_SENDER", "").strip()
        if not self.connection_string or not self.sender:
            raise ImproperlyConfigured(
                "AZURE_EMAIL_CONNECTION_STRING and AZURE_EMAIL_SENDER must both "
                "be set to use AzureEmailBackend."
            )

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        client = EmailClient.from_connection_string(self.connection_string)
        sent = 0
        for message in email_messages:
            try:
                if self._send_one(client, message):
                    sent += 1
            except Exception:
                logger.exception("Azure email send failed")
                if not self.fail_silently:
                    raise
        return sent

    def _send_one(self, client, message):
        recipients = {}
        if message.to:
            recipients["to"] = [{"address": a} for a in message.to]
        if message.cc:
            recipients["cc"] = [{"address": a} for a in message.cc]
        if message.bcc:
            recipients["bcc"] = [{"address": a} for a in message.bcc]
        if not recipients:
            return False

        content = {"subject": message.subject, "plainText": message.body}
        for alternative, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                content["html"] = alternative
                break

        payload = {
            "senderAddress": self.sender,
            "recipients": recipients,
            "content": content,
        }

        poller = client.begin_send(payload)
        result = poller.result(timeout=30)
        status = result.get("status") if hasattr(result, "get") else None
        if status != "Succeeded":
            raise RuntimeError(f"Azure email was not delivered. Status: {status}")
        return True