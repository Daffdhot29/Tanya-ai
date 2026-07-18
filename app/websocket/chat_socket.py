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
    is_cancel_command,
    is_commercial_intent,
    is_handoff_request,
    is_negative_confirmation,
    is_positive_confirmation,
    summarize_conversation,
)


router = APIRouter()


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\."
    r"[A-Za-z]{2,}$"
)


HANDOFF_OFFER = (
    "\n\n---\n"
    "Jika rancangan atau kebutuhan ini ingin diteruskan "
    "kepada tim marketing PT PowerNET Indosolution, "
    "ketik **kirim ke marketing**."
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
    cleaned = re.sub(
        r"\D",
        "",
        phone,
    )

    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]

    if not cleaned.startswith("62"):
        return None

    if len(cleaned) < 10 or len(cleaned) > 15:
        return None

    return cleaned


def append_history(
    history: list[dict[str, str]],
    role: str,
    content: str,
) -> None:
    history.append({
        "role": role,
        "content": content,
    })


async def send_answer(
    websocket: WebSocket,
    question: str,
    answer: str,
    handoff_status: str | None = None,
) -> None:
    await websocket.send_json({
        "question": question,
        "answer": answer,
        "handoff_status": handoff_status,
    })


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

    consultation_turns = 0
    handoff_offer_active = False

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

            append_history(
                conversation_history,
                "user",
                question,
            )

            try:
    
                if (
                    handoff_state
                    in {
                        "waiting_confirmation",
                        "waiting_email",
                        "waiting_phone",
                    }
                    and is_cancel_command(question)
                ):
                    handoff_state = "consultation"

                    customer_email = None
                    handoff_offer_active = False

                    response_message = (
                        "Baik, proses pengiriman ke tim "
                        "marketing dibatalkan.\n\n"
                        "Kita dapat melanjutkan konsultasi. "
                        "Silakan sampaikan kebutuhan atau "
                        "pertanyaan berikutnya."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        response_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=response_message,
                        handoff_status="cancelled",
                    )
                    continue

          
                if handoff_state == "waiting_confirmation":
                    if is_positive_confirmation(question):
                        handoff_state = "waiting_email"

                        response_message = (
                            "Baik. Silakan masukkan alamat "
                            "email aktif Bapak/Ibu.\n\n"
                            "Contoh: nama@email.com\n\n"
                            "Ketik **batal** untuk kembali "
                            "ke konsultasi."
                        )

                        append_history(
                            conversation_history,
                            "assistant",
                            response_message,
                        )

                        await send_answer(
                            websocket=websocket,
                            question=question,
                            answer=response_message,
                            handoff_status="waiting_email",
                        )
                        continue

                    if is_negative_confirmation(question):
                        handoff_state = "consultation"
                        handoff_offer_active = False

                        response_message = (
                            "Baik, kita lanjutkan konsultasi "
                            "terlebih dahulu.\n\n"
                            "Silakan sampaikan bagian mana "
                            "yang ingin dibahas atau diubah."
                        )

                        append_history(
                            conversation_history,
                            "assistant",
                            response_message,
                        )

                        await send_answer(
                            websocket=websocket,
                            question=question,
                            answer=response_message,
                            handoff_status="consultation",
                        )
                        continue

                    response_message = (
                        "Apakah kebutuhan ini ingin diteruskan "
                        "kepada tim marketing PowerNET?\n\n"
                        "Ketik **ya** untuk melanjutkan atau "
                        "**tidak** untuk kembali berkonsultasi."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        response_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=response_message,
                        handoff_status=(
                            "waiting_confirmation"
                        ),
                    )
                    continue

                if handoff_state == "waiting_email":
                    validated_email = normalize_email(
                        question
                    )

                    if validated_email is None:
                        response_message = (
                            "Alamat email belum valid.\n\n"
                            "Silakan masukkan email aktif, "
                            "misalnya nama@email.com.\n\n"
                            "Ketik **batal** untuk kembali "
                            "ke konsultasi."
                        )

                        append_history(
                            conversation_history,
                            "assistant",
                            response_message,
                        )

                        await send_answer(
                            websocket=websocket,
                            question=question,
                            answer=response_message,
                            handoff_status="waiting_email",
                        )
                        continue

                    customer_email = validated_email
                    handoff_state = "waiting_phone"

                    response_message = (
                        "Terima kasih. Selanjutnya, silakan "
                        "masukkan nomor telepon atau WhatsApp "
                        "aktif Bapak/Ibu.\n\n"
                        "Contoh: 081234567890\n\n"
                        "Ketik **batal** untuk membatalkan."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        response_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=response_message,
                        handoff_status="waiting_phone",
                    )
                    continue

                # ======================================
                # MENUNGGU NOMOR WHATSAPP
                # ======================================
                if handoff_state == "waiting_phone":
                    customer_phone = normalize_phone(
                        question
                    )

                    if customer_phone is None:
                        response_message = (
                            "Nomor WhatsApp belum valid.\n\n"
                            "Silakan masukkan nomor aktif, "
                            "misalnya 081234567890.\n\n"
                            "Ketik **batal** untuk membatalkan."
                        )

                        append_history(
                            conversation_history,
                            "assistant",
                            response_message,
                        )

                        await send_answer(
                            websocket=websocket,
                            question=question,
                            answer=response_message,
                            handoff_status="waiting_phone",
                        )
                        continue

                    if customer_email is None:
                        raise RuntimeError(
                            "Email pelanggan belum tersedia"
                        )

                    summary = await asyncio.to_thread(
                        summarize_conversation,
                        customer_email,
                        customer_phone,
                        conversation_history,
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

                    customer_message += (
                        "\n\nAnda tetap dapat melanjutkan "
                        "konsultasi melalui chat ini."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        customer_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=customer_message,
                        handoff_status="sent",
                    )

                    # Setelah email terkirim,
                    # user tetap dapat melanjutkan chat.
                    handoff_state = "consultation"

                    customer_email = None
                    consultation_turns = 0
                    handoff_offer_active = False

                    continue

             
                if is_handoff_request(question):
                    handoff_state = "waiting_confirmation"
                    handoff_offer_active = True

                    response_message = (
                        "Baik. Saya akan menyiapkan ringkasan "
                        "percakapan dan kebutuhan proyek untuk "
                        "diteruskan kepada tim marketing "
                        "PT PowerNET Indosolution.\n\n"
                        "Apakah Anda ingin melanjutkan?\n\n"
                        "Ketik **ya** untuk melanjutkan atau "
                        "**tidak** untuk kembali berkonsultasi."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        response_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=response_message,
                        handoff_status=(
                            "waiting_confirmation"
                        ),
                    )
                    continue

        
                if (
                    handoff_offer_active
                    and is_positive_confirmation(question)
                ):
                    handoff_state = "waiting_email"

                    response_message = (
                        "Baik. Silakan masukkan alamat "
                        "email aktif Bapak/Ibu.\n\n"
                        "Contoh: nama@email.com\n\n"
                        "Ketik **batal** untuk kembali "
                        "ke konsultasi."
                    )

                    append_history(
                        conversation_history,
                        "assistant",
                        response_message,
                    )

                    await send_answer(
                        websocket=websocket,
                        question=question,
                        answer=response_message,
                        handoff_status="waiting_email",
                    )
                    continue

                # ======================================
                # DETEKSI AWAL KEBUTUHAN KOMERSIAL
                # ======================================
                if is_commercial_intent(question):
                    if handoff_state == "idle":
                        handoff_state = "consultation"

                    consultation_turns += 1

                elif handoff_state == "consultation":
                    consultation_turns += 1

             
                answer = await asyncio.to_thread(
                    ask_ai,
                    question,
                    conversation_history[:-1],
                )

                if (
                    handoff_state == "consultation"
                    and consultation_turns >= 2
                ):
                    answer += HANDOFF_OFFER
                    handoff_offer_active = True

                append_history(
                    conversation_history,
                    "assistant",
                    answer,
                )

                await send_answer(
                    websocket=websocket,
                    question=question,
                    answer=answer,
                    handoff_status=(
                        "consultation"
                        if handoff_state == "consultation"
                        else None
                    ),
                )

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