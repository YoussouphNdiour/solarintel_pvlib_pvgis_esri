"""WhatsApp Business API integration for sending PDF quotes and notifications.

Uses the Meta WhatsApp Business Cloud API v19.0.
Requires WHATSAPP_TOKEN and WHATSAPP_PHONE_ID in settings.

Cache key: n/a — stateless HTTP calls, no caching required.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"

# Regex that a normalised Senegalese number must satisfy: +221 followed by 9 digits
_E164_SN_RE = re.compile(r"^\+221\d{9}$")

# Senegal mobile/fixed prefixes (without country code)
_SN_LOCAL_PREFIXES = ("77", "78", "76", "70", "33", "75", "74")


@dataclass
class WhatsAppMessage:
    """Describes a pending WhatsApp outbound message."""

    to: str                        # normalised phone: +221XXXXXXXXX
    message_type: str              # "text" | "document"
    content: str                   # text body or document URL
    filename: str | None = None
    caption: str | None = None


class WhatsAppService:
    """Sends WhatsApp messages via the Meta Cloud API."""

    # ── Phone normalisation ───────────────────────────────────────────────────

    def normalize_phone(self, phone: str) -> str:
        """Normalise a Senegalese phone number to E.164 format (+221XXXXXXXXX).

        Handles:
        - Local 9-digit format: 77XXXXXXX → +221 77XXXXXXX
        - Country-code prefix (no +): 221XXXXXXXXX → +221XXXXXXXXX
        - Already E.164: +221XXXXXXXXX → unchanged
        - Spaces and dashes: stripped before processing

        Args:
            phone: Raw phone number string in any supported format.

        Returns:
            E.164 phone number string (e.g. ``+221771234567``).

        Raises:
            ValueError: If the number cannot be normalised to a valid format.
        """
        # Strip all non-digit characters except leading +
        digits_only = re.sub(r"[\s\-\(\)]", "", phone)

        # Separate a leading + if present
        has_plus = digits_only.startswith("+")
        digits = digits_only.lstrip("+")

        # Already E.164 or has + prefix
        if has_plus:
            candidate = f"+{digits}"
            if _E164_SN_RE.match(candidate):
                return candidate
            raise ValueError(f"Cannot normalise phone number: {phone!r}")

        # Starts with full country code 221 (12 digits total)
        if digits.startswith("221") and len(digits) == 12:
            candidate = f"+{digits}"
            if _E164_SN_RE.match(candidate):
                return candidate

        # Local 9-digit number starting with known Senegal prefix
        if len(digits) == 9 and any(digits.startswith(p) for p in _SN_LOCAL_PREFIXES):
            candidate = f"+221{digits}"
            if _E164_SN_RE.match(candidate):
                return candidate

        raise ValueError(f"Cannot normalise phone number: {phone!r}")

    # ── Message dispatch ──────────────────────────────────────────────────────

    async def send_pdf_quote(
        self,
        phone: str,
        pdf_url: str,
        filename: str,
        caption: str,
    ) -> dict:  # type: ignore[type-arg]
        """Send a PDF report as a WhatsApp document message.

        Args:
            phone: Destination phone number (any supported Senegal format).
            pdf_url: Public HTTPS URL of the PDF file.
            filename: Filename to display in WhatsApp (e.g. ``rapport.pdf``).
            caption: Short caption shown below the document.

        Returns:
            Parsed JSON response from the WhatsApp API.

        Raises:
            ValueError: If WHATSAPP_TOKEN is not configured.
            httpx.HTTPStatusError: If the API returns a non-2xx status.
        """
        settings = get_settings()
        token = settings.whatsapp_token
        phone_id = settings.whatsapp_phone_id

        if not token:
            raise ValueError(
                "WHATSAPP_TOKEN is not configured. "
                "Set the WHATSAPP_TOKEN environment variable."
            )

        normalised = self.normalize_phone(phone)

        payload = {
            "messaging_product": "whatsapp",
            "to": normalised,
            "type": "document",
            "document": {
                "link": pdf_url,
                "filename": filename,
                "caption": caption,
            },
        }

        return await self._post_message(payload, token=token, phone_id=phone_id or "")

    async def send_text(self, phone: str, message: str) -> dict:  # type: ignore[type-arg]
        """Send a plain text WhatsApp message.

        Args:
            phone: Destination phone number.
            message: Text body of the message.

        Returns:
            Parsed JSON response from the WhatsApp API.

        Raises:
            ValueError: If WHATSAPP_TOKEN is not configured.
        """
        settings = get_settings()
        token = settings.whatsapp_token
        phone_id = settings.whatsapp_phone_id

        if not token:
            raise ValueError(
                "WHATSAPP_TOKEN is not configured. "
                "Set the WHATSAPP_TOKEN environment variable."
            )

        normalised = self.normalize_phone(phone)

        payload = {
            "messaging_product": "whatsapp",
            "to": normalised,
            "type": "text",
            "text": {"body": message},
        }

        return await self._post_message(payload, token=token, phone_id=phone_id or "")

    async def send_simulation_alert(
        self,
        phone: str,
        project_name: str,
        performance_pct: float,
    ) -> dict:  # type: ignore[type-arg]
        """Send a performance alert notification.

        Formats the message as:
        ``Alerte: production {project_name} à {performance_pct:.0f}% du prévu``

        Args:
            phone: Destination phone number.
            project_name: Human-readable project name.
            performance_pct: Actual production as a percentage of expected.

        Returns:
            Parsed JSON response from the WhatsApp API.
        """
        body = (
            f"Alerte: production {project_name} "
            f"à {performance_pct:.0f}% du prévu"
        )
        return await self.send_text(phone=phone, message=body)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _post_message(
        self,
        payload: dict,  # type: ignore[type-arg]
        *,
        token: str,
        phone_id: str,
    ) -> dict:  # type: ignore[type-arg]
        """POST a message payload to the WhatsApp Cloud API.

        Args:
            payload: The JSON body to send.
            token: Bearer token for authentication.
            phone_id: WhatsApp Business phone number ID.

        Returns:
            Parsed API JSON response.

        Raises:
            httpx.HTTPStatusError: On non-2xx API response.
        """
        url = f"{WHATSAPP_API_URL}/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result: dict = response.json()  # type: ignore[type-arg]
                return result
        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API error %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except Exception as exc:
            logger.error("WhatsApp send failed: %s", exc)
            raise
