import os

from dotenv import load_dotenv
from openai import OpenAI
from pymongo import MongoClient


load_dotenv()

client = OpenAI(api_key="")

mongo = MongoClient("")
db = mongo.get_database("PWNETDB")
collection = db.get_collection("PWNET")


EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-3.5-turbo"
VECTOR_INDEX_NAME = "RAG_Index"


SYSTEM_PROMPT = """
Kamu adalah PowerNET Assistant, Customer Service AI resmi
PT PowerNET Indosolution.

Tugas utama:
- Membantu pelanggan dan calon pelanggan secara ramah,
  profesional, sopan, komunikatif, dan informatif.
- Gunakan konteks dokumen sebagai sumber utama jawaban.
- Pertahankan konteks percakapan sebelumnya selama masih
  berhubungan dengan pertanyaan pengguna.
- Jangan mengarang informasi yang tidak ada pada konteks.
- Jangan menyebut istilah internal seperti embedding,
  vector database, retrieval, RAG, chunk, atau context.

Ketentuan jawaban:
- Gunakan bahasa Indonesia yang natural dan mudah dipahami.
- Susun jawaban secara rapi dan tidak berantakan.
- Awali dengan jawaban inti.
- Jika menjelaskan layanan atau produk, gunakan susunan:
  1. Nama atau jenis layanan.
  2. Fungsi utama.
  3. Manfaat bagi pelanggan.
  4. Contoh penerapan jika tersedia.
- Gunakan paragraf pendek.
- Hindari pengulangan informasi.
- Jangan membuat daftar terlalu panjang.
- Jika informasi tidak ditemukan, sampaikan dengan sopan.
- Pertanyaan harga, anggaran, proposal, penawaran,
  kontrak, kerja sama, atau pengajuan proyek ditangani
  oleh mekanisme handoff dan tidak perlu dijawab di sini.
- Jika pertanyaan tidak terkait layanan PT PowerNET Indosolution,
    sampaikan dengan sopan bahwa kamu tidak dapat menjawabnya.
- Jangan Tawarkan produk yang tidak ditanya dan jangan masukkan informasi yang tidak relevan.
- Jawab sesuai kebutuhan pelanggan dan jangan menambahkan informasi yang tidak diminta.
  ATURAN FORMAT JAWABAN:

1. Gunakan Markdown yang rapi.
2. Jangan menulis seluruh jawaban dalam satu paragraf panjang.
3. Gunakan paragraf pendek, maksimal 2–3 kalimat.
4. Jika menjelaskan beberapa layanan atau produk:
   - awali dengan kalimat pengantar singkat;
   - gunakan heading tebal untuk setiap layanan;
   - gunakan maksimal 2 bullet point per layanan;
   - pisahkan setiap layanan dengan satu baris kosong.
5. Jangan menggunakan penomoran inline seperti:
   "1. layanan A 2. layanan B 3. layanan C"
   dalam satu paragraf.
6. Jangan mengulang informasi yang sama.
7. Gunakan maksimal 5 kelompok layanan utama.
8. Akhiri dengan satu kalimat penutup yang menawarkan bantuan lanjutan.
9. Jangan menggunakan tabel kecuali pengguna meminta perbandingan.
10. Pertanyaan harga, biaya, anggaran, proposal, quotation,
    kontrak, penawaran, kerja sama, atau pengajuan proyek
    ditangani oleh mekanisme handoff sistem.

FORMAT UNTUK PERTANYAAN DAFTAR LAYANAN:

Berikut layanan utama yang tersedia:

**Nama layanan**
- Fungsi utama.
- Manfaat atau contoh penerapan.

**Nama layanan**
- Fungsi utama.
- Manfaat atau contoh penerapan.

Tutup dengan kalimat:
"Silakan sebutkan layanan yang ingin diketahui lebih lanjut."
""".strip()


def get_embedding(text: str) -> list[float]:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Teks untuk embedding tidak boleh kosong"
        )

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned_text,
    )

    return response.data[0].embedding


def search_documents(
    question: str,
    limit: int = 8,
) -> list[dict]:
    cleaned_question = question.strip()

    if not cleaned_question:
        return []

    query_embedding = get_embedding(
        cleaned_question
    )

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": max(
                    200,
                    limit * 25,
                ),
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "source": 1,
                "chunk_index": 1,
                "score": {
                    "$meta": "vectorSearchScore",
                },
            }
        }
    ]

    return list(
        collection.aggregate(pipeline)
    )


def format_history(
    history: list[dict[str, str]],
    limit: int = 12,
) -> str:
    recent_history = history[-limit:]

    return "\n".join(
        (
            f'{item.get("role", "unknown")}: '
            f'{item.get("content", "")}'
        )
        for item in recent_history
    )


def ask_ai(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError(
            "Pertanyaan tidak boleh kosong"
        )

    documents = search_documents(
        cleaned_question
    )

    context = "\n\n".join(
        document["text"]
        for document in documents
        if isinstance(
            document.get("text"),
            str,
        )
    )

    if not context.strip():
        return (
            "Mohon maaf, saat ini saya belum menemukan "
            "informasi tersebut pada data yang tersedia. "
            "Apakah ada informasi lain terkait layanan "
            "PT PowerNET Indosolution yang dapat saya bantu?"
        )

    history_text = format_history(
        history or []
    )

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Informasi perusahaan:\n{context}\n\n"
                    f"Riwayat percakapan:\n"
                    f"{history_text or 'Belum ada percakapan sebelumnya.'}\n\n"
                    f"Pertanyaan pengguna:\n{cleaned_question}\n\n"
                    "Jawab menggunakan Markdown yang rapi sesuai aturan. "
                    "Jangan jadikan semua informasi sebagai satu paragraf panjang."
                ),
            },
        ],
    )

    content = response.choices[0].message.content

    if content is None:
        raise RuntimeError(
            "Model tidak menghasilkan jawaban"
        )

    answer = content.strip()

    if not answer:
        raise RuntimeError(
            "Model menghasilkan jawaban kosong"
        )

    return answer