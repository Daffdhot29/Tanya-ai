import os
import re

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()




client = OpenAI(api_key="")

CHAT_MODEL = "gpt-3.5-turbo"


COMMERCIAL_KEYWORDS = (
    # Harga dan anggaran
    "harga",
    "biaya",
    "budget",
    "anggaran",
    "estimasi",
    "kisaran harga",
    "nilai proyek",
    "dana",
    "berapa harganya",
    "berapa biayanya",

    # Penawaran
    "proposal",
    "quotation",
    "penawaran",
    "invoice",
    "kontrak",
    "purchase order",
    "po proyek",

    # Kerja sama dan proyek
    "kerja sama",
    "kerjasama",
    "kolaborasi",
    "mengajukan proyek",
    "pengajuan proyek",
    "ada proyek",
    "punya proyek",
    "proyek baru",
    "kebutuhan proyek",
    "pengadaan",
    "tender",
    "vendor",
    "mitra",
    "konsultasi proyek",

    # Permintaan pengerjaan
    "ingin membuat",
    "ingin membangun",
    "ingin mengembangkan",
    "membutuhkan pembuatan",
    "membutuhkan pengembangan",
    "butuh dibuatkan",
    "bisa mengerjakan",
    "bisa dibuatkan",
    "mau bikin",
)


COMMERCIAL_PATTERNS = (
    r"\b(?:rp|idr)\s*[\d.,]+\b",
    r"\b\d+(?:[.,]\d+)?\s*(?:juta|jt|miliar|milyar)\b",
    r"\b(?:kami|saya)\s+(?:punya|ada|memiliki)\s+proyek\b",
    r"\b(?:kami|saya)\s+ingin\s+"
    r"(?:membuat|membangun|mengembangkan)\b",
    r"\b(?:kami|saya)\s+membutuhkan\s+"
    r"(?:jasa|pembuatan|pengembangan)\b",
    r"\bbudget\s+(?:kami|saya)\b",
    r"\banggaran\s+(?:kami|saya)\b",
)


def is_commercial_intent(
    message: str,
) -> bool:
    normalized = " ".join(
        message.casefold().split()
    )

    has_keyword = any(
        keyword in normalized
        for keyword in COMMERCIAL_KEYWORDS
    )

    has_pattern = any(
        re.search(pattern, normalized)
        for pattern in COMMERCIAL_PATTERNS
    )

    return has_keyword or has_pattern


def summarize_conversation(
    customer_email: str,
    customer_phone: str,
    messages: list[dict[str, str]],
) -> str:
    conversation_text = "\n".join(
        (
            f'{message.get("role", "unknown")}: '
            f'{message.get("content", "")}'
        )
        for message in messages[-20:]
    )

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": """
                    Buat ringkasan kebutuhan calon pelanggan
                    PT PowerNET Indosolution untuk diteruskan kepada
                    tim marketing.

                    Pelanggan dapat:
                    - menanyakan harga atau biaya;
                    - memberikan anggaran atau nilai proyek;
                    - langsung mengajukan proyek;
                    - meminta pengembangan website, aplikasi, GIS,
                    sistem informasi, infrastruktur IT, atau layanan lain;
                    - meminta proposal, quotation, atau penawaran;
                    - mengajukan kerja sama;
                    - menyebutkan target waktu.

                    Gunakan format persis berikut:

                    Email pelanggan:
                    Nomor WhatsApp pelanggan:
                    Jenis kebutuhan:
                    Layanan atau proyek:
                    Gambaran kebutuhan:
                    Permintaan komersial:
                    Harga atau anggaran yang disebutkan:
                    Target waktu:
                    Permintaan khusus:
                    Tindak lanjut yang disarankan:

                    Aturan:
                    - Jangan mengarang informasi.
                    - Gunakan hanya informasi dari percakapan.
                    - Tulis "Belum disebutkan" jika informasi tidak tersedia.
                    - Pertahankan nominal anggaran secara tepat.
                    - Bedakan pertanyaan harga dan pengajuan proyek.
                    - Buat ringkasan singkat, rapi, dan mudah dibaca.
                    """.strip(),
            },
            {
                "role": "user",
                "content": (
                    f"Email pelanggan: "
                    f"{customer_email}\n"
                    f"Nomor WhatsApp pelanggan: "
                    f"+{customer_phone}\n\n"
                    f"Riwayat percakapan:\n"
                    f"{conversation_text}"
                ),
            },
        ],
    )

    summary = response.choices[0].message.content

    if summary is None or not summary.strip():
        raise RuntimeError(
            "Ringkasan kebutuhan tidak berhasil dibuat"
        )

    return summary.strip()


def build_customer_handoff_message(
    customer_email: str,
    customer_phone: str,
) -> str:
    return (
        "Terima kasih. Informasi dan ringkasan kebutuhan "
        "Bapak/Ibu telah diteruskan kepada tim marketing "
        "PT PowerNET Indosolution.\n\n"
        f"Email tindak lanjut: {customer_email}\n"
        f"Nomor WhatsApp: +{customer_phone}\n\n"
        "Tim kami akan menghubungi Bapak/Ibu untuk "
        "membahas kebutuhan proyek atau penawaran lebih lanjut."
    )