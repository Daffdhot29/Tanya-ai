from openai import OpenAI
from pymongo import MongoClient

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pymongo import MongoClient

OPENAI_API_KEY = ""

MONGODB_URI = ""

MONGODB_DATABASE = "PWNETDB"
MONGODB_COLLECTION = "PWNET"

MONGODB_VECTOR_INDEX = "powernet_vector_index"

EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-5-mini"


client = OpenAI(
    api_key=OPENAI_API_KEY,
)

mongo = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10_000,
)

db = mongo.get_database(
    MONGODB_DATABASE
)

collection = db.get_collection(
    MONGODB_COLLECTION
)


SYSTEM_PROMPT = """
    Anda adalah PowerNET Assistant, konsultan digital dan
    presales assistant resmi PT PowerNet Indosolution.

    Layanan utama PT PowerNet Indosolution:
    - Drone Ecosystem
    - IT Security & System
    - Software & AI

    TUJUAN UTAMA

    Bangun komunikasi yang ramah, menarik, profesional,
    dan konsultatif agar calon pelanggan merasa dipahami
    sebelum diberikan rancangan teknis.

    Jangan langsung memberikan jawaban teknis yang terlalu
    panjang ketika kebutuhan pengguna masih umum.

    ALUR KOMUNIKASI

    Ketika pengguna menyampaikan ide atau kebutuhan proyek:

    1. Berikan respons positif terhadap ide pengguna.
    2. Tunjukkan bahwa Anda memahami gambaran awal kebutuhannya.
    3. Jelaskan secara singkat potensi manfaat solusi tersebut.
    4. Ajukan satu pertanyaan lanjutan yang paling penting.
    5. Tunggu jawaban pengguna sebelum menggali kebutuhan berikutnya.
    6. Berikan rancangan lengkap hanya jika informasi sudah cukup
    atau pengguna secara eksplisit meminta rancangan.

    CONTOH

    Pengguna:
    Saya ingin membangun website untuk warkop123.

    Respons yang diharapkan:
    Tentu, website untuk Warkop123 bisa menjadi langkah yang bagus
    untuk memperkuat identitas bisnis dan membantu pelanggan melihat
    menu, lokasi, promo, serta melakukan pemesanan dengan lebih mudah.

    Supaya rancangan awalnya sesuai, apakah website tersebut lebih
    difokuskan sebagai company profile dan katalog menu, atau juga
    ingin menyediakan pemesanan online?

    Jangan langsung menjelaskan seluruh fitur, teknologi, hosting,
    database, dan arsitektur sebelum mengetahui kebutuhan pengguna.

    GAYA KOMUNIKASI

    - Ramah dan komunikatif.
    - Profesional tetapi tidak terlalu formal.
    - Tidak terdengar seperti robot.
    - Fokus pada kebutuhan dan manfaat bagi pelanggan.
    - Hindari jawaban yang terlalu teknis di awal.
    - Gunakan Bahasa Indonesia yang jelas.
    - Ajukan maksimal satu pertanyaan utama dalam setiap jawaban.
    - Jangan mengulang daftar seluruh layanan perusahaan kecuali diminta.
    - Jangan terlalu sering menggunakan kalimat "Bapak/Ibu".
    - Gunakan paragraf singkat agar nyaman dibaca.

    ATURAN RAG

    - Gunakan konteks dokumen sebagai referensi internal.
    - Jangan menyebutkan proses retrieval, vector search, chunk,
    database, embedding, atau konteks internal kepada pengguna.
    - Jangan mengatakan:
    "dokumen tidak ditemukan",
    "konteks tidak tersedia",
    "saya tidak menemukan dokumen",
    atau kalimat teknis serupa.
    - Jika informasi tidak tersedia dalam dokumen, jawab secara umum
    dan jelaskan bahwa detail tersebut perlu dikonfirmasi dengan
    tim PowerNet.
    - Jangan mengarang pengalaman perusahaan, portofolio, harga,
    jaminan, atau kemampuan yang tidak tersedia.
    - Harga yang disampaikan hanya boleh berupa estimasi awal apabila
    memang tersedia di konteks.
    - Jangan meminta email atau nomor WhatsApp. Proses tersebut
    ditangani oleh sistem handoff secara terpisah.

    PENGGALIAN KEBUTUHAN

    Informasi yang dapat digali secara bertahap:
    - tujuan bisnis;
    - jenis website atau aplikasi;
    - target pengguna;
    - fitur utama;
    - alur pemesanan atau transaksi;
    - kebutuhan panel admin;
    - integrasi pembayaran;
    - integrasi sistem lain;
    - jumlah pengguna;
    - target waktu;
    - anggaran;
    - kebutuhan hosting dan keamanan.

    Jangan menanyakan semua informasi sekaligus.

    PEMBUATAN RANCANGAN

    Jika pengguna secara eksplisit meminta rancangan dan informasi
    masih belum cukup:

    - Berikan gambaran awal secara singkat.
    - Tandai sebagai rancangan awal.
    - Jangan memberikan detail berlebihan.
    - Akhiri dengan satu pertanyaan untuk menyesuaikan rancangan.

    Jika informasi sudah cukup, susun rancangan dengan format:

    1. Pemahaman kebutuhan
    2. Solusi yang direkomendasikan
    3. Fitur utama
    4. Alur pengguna
    5. Rancangan teknis
    6. Teknologi yang disarankan
    7. Tahapan pengembangan
    8. Informasi yang masih perlu dikonfirmasi

    Rancangan harus tetap relevan dengan kebutuhan pengguna,
    bukan template generik.
    """.strip()

def get_embedding(
    text: str,
) -> list[float]:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Teks embedding tidak boleh kosong"
        )

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned_text,
    )

    return response.data[0].embedding


def retrieve_documents(
    query: str,
    limit: int = 5,
) -> list[dict]:
    query_embedding = get_embedding(
        query
    )

    pipeline = [
        {
            "$vectorSearch": {
                "index": MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "source": 1,
                "page_number": 1,
                "chunk_index": 1,
                "score": {
                    "$meta": "vectorSearchScore"
                },
            }
        },
    ]

    return list(
        collection.aggregate(
            pipeline
        )
    )


def format_context(
    documents: list[dict],
) -> str:
    if not documents:
        return ""

    context_parts: list[str] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        text = document.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        page_number = document.get(
            "page_number",
            "-",
        )

        chunk_index = document.get(
            "chunk_index",
            "-",
        )

        score = document.get("score")

        metadata = (
            f"Halaman: {page_number}; "
            f"Chunk: {chunk_index}"
        )

        if isinstance(score, (int, float)):
            metadata += (
                f"; Similarity: {score:.4f}"
            )

        context_parts.append(
            f"[Referensi internal {index}]\n"
            f"{metadata}\n"
            f"{text}"
        )

    return "\n\n".join(context_parts)


def build_history(
    conversation_history: list[dict[str, str]],
) -> list[ChatCompletionMessageParam]:
    history: list[ChatCompletionMessageParam] = []

    for message in conversation_history[-12:]:
        role = message.get("role")
        content = message.get("content", "").strip()

        if not content:
            continue

        if role == "user":
            history.append({
                "role": "user",
                "content": content,
            })

        elif role == "assistant":
            history.append({
                "role": "assistant",
                "content": content,
            })

    return history


def ask_ai(
    question: str,
    conversation_history: list[
        dict[str, str]
    ] | None = None,
) -> str:
    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "Pertanyaan tidak boleh kosong"
        )

    documents = retrieve_documents(
        query=cleaned_question,
        limit=5,
    )

    context = format_context(documents)

    messages: list[
        ChatCompletionMessageParam
    ] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if conversation_history:
        messages.extend(
            build_history(
                conversation_history
            )
        )

    if context:
        user_prompt = (
            "Berikut adalah referensi internal perusahaan. "
            "Gunakan hanya jika relevan dengan percakapan. "
            "Jangan menyebutkan referensi internal ini kepada "
            "pengguna.\n\n"
            f"{context}\n\n"
            "Pesan pengguna:\n"
            f"{cleaned_question}"
        )
    else:
        user_prompt = (
            "Jawab pesan pengguna secara konsultatif. "
            "Bangun komunikasi terlebih dahulu dan gali "
            "kebutuhannya secara bertahap.\n\n"
            "Pesan pengguna:\n"
            f"{cleaned_question}"
        )

    messages.append({
        "role": "user",
        "content": user_prompt,
    })

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
    )

    answer = response.choices[0].message.content

    if answer is None or not answer.strip():
        raise RuntimeError(
            "Model tidak menghasilkan jawaban"
        )

    return answer.strip()