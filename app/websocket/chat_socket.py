import asyncio
import re

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

from app.rag.rag_chain import ask_ai
from app.services.email_service import (
    notify_admin_by_email,
)
from app.services.handoff import (
    build_customer_handoff_message,
    is_commercial_intent,
    summarize_conversation,
)


router = APIRouter()


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\."
    r"[A-Za-z]{2,}$"
)


def normalize_email(
    email: str,
) -> str | None:
    cleaned = email.strip().lower()

    if not EMAIL_PATTERN.fullmatch(cleaned):
        return None

    return cleaned


def normalize_phone(
    phone: str,
) -> str | None:
    cleaned = re.sub(r"\D", "", phone)

    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]

    if not cleaned.startswith("62"):
        return None

    if len(cleaned) < 10 or len(cleaned) > 15:
        return None

    return cleaned


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
) -> None:
    await websocket.accept()
    print("Client connected")

    conversation_history: list[
        dict[str, str]
    ] = []

    handoff_state = "idle"
    customer_email: str | None = None

    try:
        while True:
            question = (
                await websocket.receive_text()
            ).strip()

            if not question:
                await websocket.send_json({
                    "error": (
                        "Pertanyaan tidak boleh kosong"
                    ),
                })
                continue

            conversation_history.append({
                "role": "user",
                "content": question,
            })

            try:
                # Tahap 1: menunggu email.
                if handoff_state == "waiting_email":
                    validated_email = normalize_email(
                        question
                    )

                    if validated_email is None:
                        response_message = (
                            "Alamat email belum valid. "
                            "Silakan masukkan alamat email aktif, "
                            "misalnya nama@email.com."
                        )

                        conversation_history.append({
                            "role": "assistant",
                            "content": response_message,
                        })

                        await websocket.send_json({
                            "question": question,
                            "answer": response_message,
                            "handoff_status": (
                                "waiting_email"
                            ),
                        })
                        continue

                    customer_email = validated_email
                    handoff_state = "waiting_phone"

                    response_message = (
                        "Terima kasih. Selanjutnya, silakan "
                        "masukkan nomor telepon atau nomor "
                        "WhatsApp aktif Bapak/Ibu.\n\n"
                        "Contoh: 081234567890"
                    )

                    conversation_history.append({
                        "role": "assistant",
                        "content": response_message,
                    })

                    await websocket.send_json({
                        "question": question,
                        "answer": response_message,
                        "handoff_status": (
                            "waiting_phone"
                        ),
                    })
                    continue

                # Tahap 2: menunggu nomor WhatsApp.
                if handoff_state == "waiting_phone":
                    customer_phone = normalize_phone(
                        question
                    )

                    if customer_phone is None:
                        response_message = (
                            "Nomor yang dimasukkan belum valid. "
                            "Silakan masukkan nomor aktif, "
                            "misalnya 081234567890."
                        )

                        conversation_history.append({
                            "role": "assistant",
                            "content": response_message,
                        })

                        await websocket.send_json({
                            "question": question,
                            "answer": response_message,
                            "handoff_status": (
                                "waiting_phone"
                            ),
                        })
                        continue

                    if customer_email is None:
                        raise RuntimeError(
                            "Email pelanggan belum tersedia"
                        )

                    summary = summarize_conversation(
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        messages=conversation_history,
                    )

                    await asyncio.to_thread(
                        notify_admin_by_email,
                        customer_email,
                        customer_phone,
                        summary,
                    )

                    customer_message = (
                        build_customer_handoff_message(
                            customer_email=customer_email,
                            customer_phone=customer_phone,
                        )
                    )

                    conversation_history.append({
                        "role": "assistant",
                        "content": customer_message,
                    })

                    await websocket.send_json({
                        "question": question,
                        "answer": customer_message,
                        "handoff_status": "sent",
                    })

                    handoff_state = "completed"
                    continue

                # Handoff sudah selesai.
                if handoff_state == "completed":
                    response_message = (
                        "Informasi Bapak/Ibu sudah diteruskan "
                        "kepada tim marketing. Mohon menunggu "
                        "proses tindak lanjut."
                    )

                    await websocket.send_json({
                        "question": question,
                        "answer": response_message,
                        "handoff_status": "completed",
                    })
                    continue

                # Mendeteksi harga, proyek, proposal,
                # anggaran, dan kerja sama.
                if is_commercial_intent(question):
                    handoff_state = "waiting_email"

                    response_message = (
                        "Baik, kebutuhan proyek, harga, biaya, "
                        "anggaran, proposal, penawaran, atau "
                        "kerja sama Bapak/Ibu akan diteruskan "
                        "kepada tim marketing "
                        "PT PowerNET Indosolution.\n\n"
                        "Silakan masukkan alamat email aktif "
                        "Bapak/Ibu terlebih dahulu."
                    )

                    conversation_history.append({
                        "role": "assistant",
                        "content": response_message,
                    })

                    await websocket.send_json({
                        "question": question,
                        "answer": response_message,
                        "handoff_status": (
                            "waiting_email"
                        ),
                    })
                    continue

         
                answer = await asyncio.to_thread(
                    ask_ai,
                    question,
                    conversation_history[:-1],
                )

                conversation_history.append({
                    "role": "assistant",
                    "content": answer,
                })

                await websocket.send_json({
                    "question": question,
                    "answer": answer,
                    "handoff_status": None,
                })

            except Exception as error:
                print(
                    "Chat processing error:",
                    str(error),
                )

                await websocket.send_json({
                    "question": question,
                    "error": (
                        "Sistem gagal memproses permintaan. "
                        "Silakan mencoba kembali."
                    ),
                })

    except WebSocketDisconnect:
        print("Client disconnected")