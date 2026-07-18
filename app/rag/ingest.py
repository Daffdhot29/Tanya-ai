from hashlib import sha256
from pathlib import Path

from openai import OpenAI
from pymongo import MongoClient
from pypdf import PdfReader


PDF_PATH = Path("docs/PT_PowerNet_Indosolution_Proposal_v2.pdf")
client = OpenAI(api_key="")

mongo = MongoClient("")
db = mongo.get_database("PWNETDB")
collection = db.get_collection("PWNET")


def get_embedding(
    text: str,
) -> list[float]:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Teks untuk embedding tidak boleh kosong"
        )

    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=cleaned_text,
    )

    return response.data[0].embedding


def read_pdf_pages() -> list[dict]:

    reader = PdfReader(
        str(PDF_PATH)
    )

    pages: list[dict] = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        page_text = page.extract_text() or ""

        cleaned_text = " ".join(
            page_text.split()
        )

        if cleaned_text:
            pages.append({
                "page_number": page_number,
                "text": cleaned_text,
            })

    return pages


def chunk_text(
    text: str,
    chunk_size: int = 1200,
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


def make_document_id() -> str:
    absolute_path = str(
        PDF_PATH.resolve()
    )

    return sha256(
        absolute_path.encode("utf-8")
    ).hexdigest()


def ingest_document() -> None:
    pages = read_pdf_pages()

    if not pages:
        raise ValueError(
            "PDF kosong atau tidak dapat dibaca"
        )

    document_id = make_document_id()

    documents: list[dict] = []

    global_chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        page_text = page["text"]

        chunks = chunk_text(
            page_text
        )

        for page_chunk_index, chunk in enumerate(
            chunks
        ):
            print(
                "Embedding page",
                page_number,
                "chunk",
                page_chunk_index,
            )

            embedding = get_embedding(
                chunk
            )

            documents.append({
                "document_id": document_id,
                "document_name": PDF_PATH.name,
                "source": str(PDF_PATH),
                "page_number": page_number,
                "page_chunk_index": page_chunk_index,
                "chunk_index": global_chunk_index,
                "text": chunk,
                "embedding": embedding,
                "embedding_model":"text-embedding-3-large",
            })

            global_chunk_index += 1

    collection.delete_many({
        "document_id": document_id,
    })

    if documents:
        collection.insert_many(
            documents
        )

    print(
        f"{len(documents)} chunks inserted ke MongoDB"
    )

    print(
        "Embedding dimension:",
        len(documents[0]["embedding"]),
    )


if __name__ == "__main__":
    ingest_document()