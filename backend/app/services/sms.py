"""SMS: an interface with one honest implementation that sends nothing.

No SMS is ever faked. Where an SMS would go out (reminders, escalations,
verification), the portal sends the email and the in-app message instead,
and the Admin page shows "SMS planned".

To plug in a real gateway, add a class with the same `send` method and pick
it with SMS_PROVIDER in .env, for example:

    class Msg91Sms:      # https://docs.msg91.com  (DLT-registered template id needed in India)
        name, configured = "msg91", True
        def send(self, phone, text):
            httpx.post("https://control.msg91.com/api/v5/flow/", headers={"authkey": MSG91_AUTH_KEY},
                       json={"template_id": MSG91_TEMPLATE_ID, "recipients": [{"mobiles": phone, "text": text}]})

    class TwilioSms:     # https://www.twilio.com/docs/sms
        name, configured = "twilio", True
        def send(self, phone, text):
            httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json",
                       auth=(SID, TOKEN), data={"From": TWILIO_FROM, "To": phone, "Body": text})

Users would also need a verified mobile number field."""
from __future__ import annotations

from typing import Protocol

from ..config import settings


class SmsProvider(Protocol):
    name: str
    configured: bool

    def send(self, phone: str, text: str) -> str: ...


class NotConfiguredSms:
    name, configured = "not_configured", False

    def send(self, phone: str, text: str) -> str:
        return "NOT_CONFIGURED"  # nothing sent; email + in-app message carry the alert


def provider() -> SmsProvider:
    # Only the honest stub exists today; see the docstring for MSG91 / Twilio.
    return NotConfiguredSms() if not settings.sms_provider else NotConfiguredSms()


def status() -> dict:
    p = provider()
    return {"provider": p.name, "configured": p.configured,
            "label": "SMS planned: no SMS gateway is connected. Email and in-app messages are sent instead."}
