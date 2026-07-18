import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pymongo import MongoClient
from pypdf import PdfReader 


load_dotenv()


client = OpenAI(api_key="")

mongo = MongoClient("")
db = mongo.get_database("PWNETDB")
collection = db.get_collection("PWNET")


PDF_PATH = "docs/PT_PowerNet_Indosolution_Proposal_v2.pdf"

EMBEDDING_MODEL = "text-embedding-3-large"


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


def read_pdf() -> str:
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Dokumen tidak ditemukan: {PDF_PATH}"
        )

    reader = PdfReader(str(PDF_PATH))
    text_parts: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text_parts.append(page_text)

    return "\n".join(text_parts)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError(
            "chunk_size harus lebih besar dari 0"
        )

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap harus lebih kecil dari chunk_size"
        )

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += step

    return chunks


def ingest_document() -> None:
    text = read_pdf()

    print("PDF TEXT LENGTH:", len(text))
    print("PDF PREVIEW:", text[:500])

    if not text.strip():
        raise ValueError(
            "PDF kosong atau tidak dapat dibaca"
        )

    chunks = chunk_text(text)
    documents: list[dict] = []

    for index, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)

        documents.append({
            "source": str(PDF_PATH),
            "chunk_index": index,
            "text": chunk,
            "embedding": embedding,
            "embedding_model": EMBEDDING_MODEL,
        })

    collection.delete_many({})
    collection.insert_many(documents)

    print(
        f"{len(documents)} chunks inserted to MongoDB"
    )
    print(
        "Embedding dimension:",
        len(documents[0]["embedding"]),
    )


if __name__ == "__main__":
    ingest_document()