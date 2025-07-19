from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import re
from datetime import datetime
import gspread
import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN", "7874848041:AAF1HmDpNVGfJhQBetDW05c16SFqPAQJwLs")

GOOGLE_SHEET_NAME = "Catatan Keuangan Bot"
SERVICE_ACCOUNT_FILE = r'D:\BACK UP VIRA 05-05-2025\ONE DRIVE\DOKUMEN\VSCODE\bot telegram\telegram-bot-keuangan-ecdb509353f1.json'

gc = None 
USER_SHEET_MAPPING_FILE = 'user_sheets.json'
user_sheets = {} 

def authenticate_google_sheets():
    global gc
    try:
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_dict = json.loads(creds_json)
            gc = gspread.service_account_from_dict(creds_dict)
            print("Berhasil terhubung ke Google Sheets API dari environment variable.")
        else:
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                print(f"Error: File kredensial '{SERVICE_ACCOUNT_FILE}' tidak ditemukan.")
                print("Pastikan Anda sudah mengunduh file JSON dari Google Cloud Console dan menempatkannya di direktori yang benar.")
                print("PERHATIAN: Pastikan path di atas (SERVICE_ACCOUNT_FILE) adalah path LENGKAP dan ABSOLUT di sistem Anda.")
                return False
            gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
            print("Berhasil terhubung ke Google Sheets API dari file lokal.")

        load_user_sheet_mappings()
        return True
    except Exception as e:
        print(f"Gagal terhubung ke Google Sheets API: {e}")
        print("Pastikan Anda sudah mengaktifkan Google Sheets API dan service account memiliki izin Editor pada spreadsheet.")
        return False

def load_user_sheet_mappings():
    global user_sheets
    if os.path.exists(USER_SHEET_MAPPING_FILE):
        with open(USER_SHEET_MAPPING_FILE, 'r') as f:
            try:
                user_sheets = json.load(f)
                print("User sheet mappings dimuat.")
            except json.JSONDecodeError as e:
                print(f"Error membaca file JSON mapping: {e}. Membuat file baru.")
                user_sheets = {} 
                save_user_sheet_mappings()
    else:
        print("User sheet mapping file tidak ditemukan, membuat yang baru.")
        save_user_sheet_mappings()

def save_user_sheet_mappings():
    with open(USER_SHEET_MAPPING_FILE, 'w') as f:
        json.dump(user_sheets, f, indent=4)
    print("User sheet mappings disimpan.")


def get_or_create_user_worksheet(user_id):
    global user_sheets
    try:
        spreadsheet = gc.open(GOOGLE_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Spreadsheet '{GOOGLE_SHEET_NAME}' tidak ditemukan. Pastikan namanya benar dan bot memiliki akses.")
        return None
    except Exception as e:
        print(f"Gagal membuka spreadsheet utama: {e}")
        return None

    if str(user_id) not in user_sheets:
        worksheet_name = f"User_{user_id}"
        try:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="10")
            headers = ["Tanggal", "Deskripsi", "Kategori", "Income", "Expense"]
            worksheet.append_row(headers)
            user_sheets[str(user_id)] = worksheet_name
            save_user_sheet_mappings()
            print(f"Worksheet baru dibuat untuk user {user_id}: {worksheet_name}")
            return worksheet
        except gspread.exceptions.DuplicateWorksheet:
            worksheet = spreadsheet.worksheet(worksheet_name)
            user_sheets[str(user_id)] = worksheet_name
            save_user_sheet_mappings()
            print(f"Worksheet {worksheet_name} sudah ada, ditambahkan ke mapping.")
            return worksheet
        except Exception as e:
            print(f"Gagal membuat worksheet baru untuk user {user_id}: {e}")
            return None
    else:
        worksheet_name = user_sheets[str(user_id)]
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"Worksheet '{worksheet_name}' tidak ditemukan, kemungkinan terhapus manual. Membuat ulang.")
            del user_sheets[str(user_id)]
            save_user_sheet_mappings()
            return get_or_create_user_worksheet(user_id)
        except Exception as e:
            print(f"Gagal mendapatkan worksheet untuk user {user_id}: {e}")
            return None

def add_to_sheet(user_id, tanggal, deskripsi, kategori, income, expense):
    if not gc:
        print("Google Sheets belum terautentikasi atau gagal terhubung. Tidak dapat menambahkan data.")
        return False

    try:
        worksheet = get_or_create_user_worksheet(user_id)
        if not worksheet:
            return False

        row = [tanggal, deskripsi, kategori, income, expense]
        worksheet.append_row(row)
        print(f"Data berhasil ditambahkan ke Google Sheets untuk user {user_id}: {row}")
        return True
    except Exception as e:
        print(f"Gagal menambahkan data ke Google Sheets untuk user {user_id}: {e}")
        return False


def parse_message(message_text):
    tanggal = datetime.now().strftime("%Y-%m-%d")
    deskripsi = ""
    kategori = "Lain-lain"
    income = ""
    expense = ""
    amount = 0

    match_amount = re.search(r'(\d[\d\.,]*)(\s*(rb|ribu|k|juta|jt)?)?$', message_text.lower())

    if match_amount:
        raw_amount_str = match_amount.group(1).replace('.', '').replace(',', '')
        multiplier_text = match_amount.group(2)
        amount = int(raw_amount_str)

        if multiplier_text:
            if "rb" in multiplier_text or "ribu" in multiplier_text or "k" in multiplier_text:
                amount *= 1000
            elif "juta" in multiplier_text or "jt" in multiplier_text:
                amount *= 1000000

        deskripsi = re.sub(r'(\d[\d\.,]*)(\s*(rb|ribu|k|juta|jt)?)?$', '', message_text, flags=re.IGNORECASE).strip()
    else:
        return None, None, None, None, None

    lower_text = message_text.lower()

    if "beli" in lower_text or "bayar" in lower_text or "keluar" in lower_text or "jajan" in lower_text:
        expense = str(amount)
        if "makan" in lower_text or "minum" in lower_text or "kuliner" in lower_text or "cilok" in lower_text or "kopi" in lower_text:
            kategori = "Makanan & Minuman"
        elif "transport" in lower_text or "ojol" in lower_text or "bensin" in lower_text:
            kategori = "Transportasi"
        elif "belanja" in lower_text or "indomaret" in lower_text or "alfamart" in lower_text:
            kategori = "Belanja Kebutuhan"
        elif "pulsa" in lower_text or "paket data" in lower_text:
            kategori = "Komunikasi"
        elif "listrik" in lower_text or "air" in lower_text:
            kategori = "Tagihan & Utilitas"
        elif "hiburan" in lower_text or "nonton" in lower_text or "game" in lower_text:
            kategori = "Hiburan"
        else:
            kategori = "Pengeluaran Lain-lain"
    elif "gaji" in lower_text or "masuk" in lower_text or "jual" in lower_text or "dapat" in lower_text or "income" in lower_text:
        income = str(amount)
        if "gaji" in lower_text:
            kategori = "Gaji"
        elif "investasi" in lower_text or "dividen" in lower_text:
            kategori = "Investasi"
        elif "bonus" in lower_text:
            kategori = "Bonus"
        else:
            kategori = "Pemasukan Lain-lain"
    else:
        expense = str(amount)
        kategori = "Pengeluaran Tak Terkategori"

    if not deskripsi:
        deskripsi = message_text.strip()

    return tanggal, deskripsi, kategori, income, expense


def _get_user_sheet_data(user_id):
    if not gc:
        return None

    try:
        worksheet = get_or_create_user_worksheet(user_id)
        if not worksheet:
            return None
        data = worksheet.get_all_records()
        return data
    except Exception as e:
        print(f"Gagal mengambil data dari Google Sheets untuk user {user_id}: {e}")
        return None

def _calculate_totals(data):
    total_income = 0.0
    total_expense = 0.0

    if data is None:
        return 0.0, 0.0, 0.0

    for row in data:
        try:
            income_str = str(row.get('Income', '')).strip()
            expense_str = str(row.get('Expense', '')).strip()

            income_num_str = ''
            expense_num_str = ''

            if income_str:
                income_num_str = re.sub(r'[^\d.]', '', income_str)
            if expense_str:
                expense_num_str = re.sub(r'[^\d.]', '', expense_str)
            
            if income_num_str:
                total_income += float(income_num_str)
            if expense_num_str:
                total_expense += float(expense_num_str)

        except ValueError as ve:
            print(f"Warning: Could not convert value to number in row {row}: {ve}. Skipping.")
            continue
        except KeyError as ke:
            print(f"Warning: Missing key in row {row}: {ke}. Ensure 'Income' and 'Expense' headers are correct.")
            continue

    saldo = total_income - total_expense
    return total_income, total_expense, saldo

async def start(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets. Mohon periksa konfigurasi dan coba lagi.")
            return

    worksheet = get_or_create_user_worksheet(user_id)
    if not worksheet:
        await update.message.reply_text("Maaf, terjadi masalah saat menyiapkan akun keuangan Anda. Mohon coba lagi.")
        return

    await update.message.reply_text('Halo! Selamat datang di Bot Pencatat Keuangan Anda. Kirimkan pemasukan/pengeluaran Anda. Contoh: "beli cilok 5000", "gaji 2jt", "Indomaret 10 ribu". Gunakan /sisa_saldo untuk cek saldo, /total_income untuk total pemasukan, dan /total_pengeluaran untuk total pengeluaran. Untuk menghapus data: /clear_history atau /delete_last.')

async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets. Mohon periksa konfigurasi dan coba lagi.")
            return

    tanggal, deskripsi, kategori, income, expense = parse_message(text)

    if tanggal is None:
        await update.message.reply_text("Format pesan tidak dikenali. Mohon sertakan angka untuk jumlah transaksi. Contoh: 'beli cilok 5000', 'gaji 2jt'.")
        return

    if add_to_sheet(user_id, tanggal, deskripsi, kategori, income, expense):
        response_text = f"✅ Dicatat:\n"
        response_text += f"Tanggal: {tanggal}\n"
        response_text += f"Deskripsi: {deskripsi if deskripsi else text}\n"
        response_text += f"Kategori: {kategori}\n"
        if income:
            response_text += f"Pemasukan: Rp{int(float(income)):,}\n" 
        if expense:
            response_text += f"Pengeluaran: Rp{int(float(expense)):,}\n" 
        response_text += "Data sudah tersimpan di Google Sheets Anda."
        await update.message.reply_text(response_text)
    else:
        await update.message.reply_text("Terjadi kesalahan saat mencoba mencatat transaksi ke Google Sheets. Mohon coba lagi nanti.")

async def sisa_saldo(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets untuk menghitung saldo. Mohon periksa konfigurasi.")
            return

    data = _get_user_sheet_data(user_id)
    if data is None:
        await update.message.reply_text("Maaf, gagal mengambil data dari Google Sheets Anda.")
        return

    total_inc, total_exp, current_balance = _calculate_totals(data)

    if current_balance is not None:
        await update.message.reply_text(
            f"💰 Saldo Anda saat ini: Rp{int(current_balance):,}\n"
            f"📈 Total Pemasukan: Rp{int(total_inc):,}\n"
            f"📉 Total Pengeluaran: Rp{int(total_exp):,}"
        )
    else:
        await update.message.reply_text("Maaf, gagal menghitung saldo Anda. Coba lagi nanti atau periksa log.")

async def total_pengeluaran(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets untuk menghitung total pengeluaran. Mohon periksa konfigurasi.")
            return

    data = _get_user_sheet_data(user_id)
    if data is None:
        await update.message.reply_text("Maaf, gagal mengambil data dari Google Sheets Anda.")
        return

    total_inc, total_exp, current_balance = _calculate_totals(data)

    if total_exp is not None:
        await update.message.reply_text(f"📉 Total Pengeluaran Anda: Rp{int(total_exp):,}")
    else:
        await update.message.reply_text("Maaf, gagal menghitung total pengeluaran Anda. Coba lagi nanti atau periksa log.")

async def total_income(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets untuk menghitung total pemasukan. Mohon periksa konfigurasi.")
            return

    data = _get_user_sheet_data(user_id)
    if data is None:
        await update.message.reply_text("Maaf, gagal mengambil data dari Google Sheets Anda.")
        return

    total_inc, total_exp, current_balance = _calculate_totals(data)

    if total_inc is not None:
        await update.message.reply_text(f"📈 Total Pemasukan Anda: Rp{int(total_inc):,}")
    else:
        await update.message.reply_text("Maaf, gagal menghitung total pemasukan Anda. Coba lagi nanti atau periksa log.")


async def clear_history(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets untuk menghapus history. Mohon periksa konfigurasi.")
            return

    keyboard = [
        [
            InlineKeyboardButton("Ya, Kosongkan Data!", callback_data=f'confirm_clear_content_{user_id}'),
            InlineKeyboardButton("Batal", callback_data=f'cancel_clear_{user_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚠️ PERINGATAN: Apakah Anda yakin ingin MENGOSONGKAN SEMUA DATA transaksi dari sheet Anda?\n"
        "Tindakan ini TIDAK dapat dibatalkan!",
        reply_markup=reply_markup
    )

async def delete_last(update, context):
    user_id = update.effective_user.id
    if not gc:
        if not authenticate_google_sheets():
            await update.message.reply_text("Maaf, bot belum bisa terhubung ke Google Sheets untuk menghapus data. Mohon periksa konfigurasi.")
            return

    keyboard = [
        [
            InlineKeyboardButton("Ya, Hapus Baris Terakhir!", callback_data=f'confirm_delete_last_{user_id}'),
            InlineKeyboardButton("Batal", callback_data=f'cancel_clear_{user_id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚠️ PERINGATAN: Apakah Anda yakin ingin MENGHAPUS BARIS TERAKHIR transaksi dari sheet Anda?\n"
        "Tindakan ini TIDAK dapat dibatalkan!",
        reply_markup=reply_markup
    )

async def button_callback(update, context):
    query = update.callback_query
    await query.answer() 

    callback_data_parts = query.data.split('_')
    action = "_".join(callback_data_parts[:-1])
    user_id_from_callback = callback_data_parts[-1]

    if str(query.from_user.id) != user_id_from_callback:
        await query.edit_message_text("Aksi tidak diizinkan. Ini bukan data Anda.")
        return

    user_id = int(user_id_from_callback)

    if action == 'confirm_clear_content':
        try:
            worksheet = get_or_create_user_worksheet(user_id)
            if not worksheet:
                await query.edit_message_text("❌ Gagal mendapatkan worksheet untuk dikosongkan.")
                return

            num_rows = worksheet.row_count
            num_cols = worksheet.col_count

            if num_rows > 1: 
                last_col_letter = chr(ord('A') + num_cols - 1)
                range_to_update = f'A2:{last_col_letter}{num_rows}'
                empty_data = [[''] * num_cols for _ in range(num_rows - 1)]
                worksheet.update(range_to_update, empty_data)

                await query.edit_message_text("✅ Semua data transaksi Anda berhasil dikosongkan (baris tetap ada).")
            else:
                await query.edit_message_text("Tidak ada data transaksi untuk dikosongkan.")
        except Exception as e:
            await query.edit_message_text(f"❌ Gagal mengosongkan data: {e}")
    elif action == 'confirm_delete_last':
        try:
            worksheet = get_or_create_user_worksheet(user_id)
            if not worksheet:
                await query.edit_message_text("❌ Gagal mendapatkan worksheet untuk dihapus.")
                return

            num_rows = worksheet.row_count
            if num_rows > 1: 
                worksheet.delete_rows(num_rows)
                await query.edit_message_text("✅ Baris transaksi terakhir Anda berhasil dihapus.")
            else:
                await query.edit_message_text("Tidak ada baris transaksi untuk dihapus (hanya header atau kosong).")
        except Exception as e:
            await query.edit_message_text(f"❌ Gagal menghapus baris terakhir: {e}")
    elif action == 'cancel_clear':
        await query.edit_message_text("Aksi penghapusan dibatalkan.")

def main():
    if not authenticate_google_sheets():
        print("Autentikasi Google Sheets gagal. Bot mungkin tidak berfungsi penuh.")
  

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sisa_saldo", sisa_saldo))
    application.add_handler(CommandHandler("total_saldo", sisa_saldo))
    application.add_handler(CommandHandler("total_pengeluaran", total_pengeluaran))
    application.add_handler(CommandHandler("total_income", total_income))
    application.add_handler(CommandHandler("clear_history", clear_history))
    application.add_handler(CommandHandler("delete_last", delete_last))
    
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r'^(confirm_clear_content|confirm_delete_last|cancel_clear)_\d+$'))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot sedang berjalan... Tekan Ctrl+C untuk berhenti.")
    application.run_polling()

if __name__ == '__main__':
    main()
