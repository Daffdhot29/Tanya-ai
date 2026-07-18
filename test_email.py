import asyncio

from app.services.email_service import (
    notify_admin_by_email,
)


async def main() -> None:
    await asyncio.to_thread(
        notify_admin_by_email,
        "customer@example.com",
        "081298192099",
        (
            "Email pelanggan: customer@example.com\n"
            "Nomor WhatsApp pelanggan: +6281298192099\n"
            "Jenis kebutuhan: Permintaan penawaran\n"
            "Layanan atau proyek: Website company profile\n"
            "Gambaran kebutuhan: Calon pelanggan membutuhkan "
            "website company profile untuk perusahaan.\n"
            "Permintaan komersial: Meminta informasi harga "
            "dan estimasi pengerjaan.\n"
            "Harga atau anggaran yang disebutkan: "
            "Belum disebutkan\n"
            "Target waktu: Belum disebutkan\n"
            "Permintaan khusus: Belum disebutkan\n"
            "Tindak lanjut yang disarankan: Hubungi pelanggan "
            "untuk menggali kebutuhan dan menyusun penawaran."
        ),
    )

    print("Email berhasil dikirim ke admin.")


if __name__ == "__main__":
    asyncio.run(main())