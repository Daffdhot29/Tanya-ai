import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f"{name} belum diisi dengan benar di file .env"
        )

    return value.strip()


SMTP_EMAIL: str = "" 

SMTP_APP_PASSWORD: str = ""

ADMIN_EMAIL: str = ""


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"\D", "", phone)

    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]

    if not cleaned.startswith("62"):
        raise ValueError(
            "Nomor WhatsApp harus diawali 0 atau 62"
        )

    if len(cleaned) < 10 or len(cleaned) > 15:
        raise ValueError(
            "Panjang nomor WhatsApp tidak valid"
        )

    return cleaned


def build_whatsapp_url(phone: str) -> str:
    normalized_phone = normalize_phone(phone)

    return f"https://wa.me/{normalized_phone}"


def notify_admin_by_email(
    customer_email: str,
    customer_phone: str,
    summary: str,
) -> None:
    cleaned_email = customer_email.strip().lower()
    cleaned_phone = normalize_phone(customer_phone)
    cleaned_summary = summary.strip()

    if not cleaned_email:
        raise ValueError(
            "Email pelanggan tidak boleh kosong"
        )

    if not cleaned_summary:
        raise ValueError(
            "Ringkasan kebutuhan tidak boleh kosong"
        )

    whatsapp_url = build_whatsapp_url(
        cleaned_phone
    )

    message = EmailMessage()

    message["Subject"] = (
        "[PowerNET AI] Lead Baru - "
        "Proyek atau Permintaan Penawaran"
    )

    message["From"] = formataddr(
        (
            "PowerNET Assistant",
            SMTP_EMAIL,
        )
    )

    message["To"] = ADMIN_EMAIL
    message["Reply-To"] = cleaned_email

    message.set_content(
        f"""
            Halo Tim Marketing PT PowerNET Indosolution,

            PowerNET Assistant menerima kebutuhan komersial atau
            pengajuan proyek dari calon pelanggan.

            EMAIL PELANGGAN
            {cleaned_email}

            NOMOR WHATSAPP PELANGGAN
            +{cleaned_phone}

            LINK WHATSAPP
            {whatsapp_url}

            RINGKASAN KEBUTUHAN
            {cleaned_summary}

            Silakan menghubungi calon pelanggan melalui email atau
            tautan WhatsApp di atas untuk proses tindak lanjut.

            Pesan ini dikirim secara otomatis oleh PowerNET Assistant.
            """.strip()
    )

    with smtplib.SMTP_SSL(
        host="smtp.gmail.com",
        port=465,
        timeout=30,
    ) as smtp:
        smtp.login(
            user=SMTP_EMAIL,
            password=SMTP_APP_PASSWORD,
        )

        smtp.send_message(message)