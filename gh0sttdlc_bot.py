import os, asyncio, sqlite3, secrets, urllib.parse, random, string, requests, threading
from datetime import datetime, timedelta
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8747534538:AAEvH_qlquUXlM0p3P2x_hbqZ1SljLPy4wM"
WALLET_NUMBER = "4100118548432704"
SECRET_KEY = "Q7lcid9Bzlzwbj73cqDXr2B1"
APK_LINK = "https://t.me/zjTfte-9i282MmQy"

conn = sqlite3.connect('shop.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT, uid INT, amount INT, days INT, status TEXT, key TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS subs (uid INT PRIMARY KEY, expires TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS ghost_keys (
    key TEXT PRIMARY KEY,
    days INTEGER,
    expire TEXT,
    created_at TEXT,
    used_by TEXT
)''')
conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

def key(): return f"GHOST-{''.join(random.choices(string.ascii_uppercase, k=10))}"
def price(x): return round(x / 0.97, 2)

def menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="300₽ 7д"), KeyboardButton(text="600₽ 14д")],
        [KeyboardButton(text="1200₽ 30д")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📜 История"), KeyboardButton(text="📥 APK")]
    ], resize_keyboard=True)

def sub_status(uid):
    c.execute("SELECT expires FROM subs WHERE uid=?", (uid,))
    row = c.fetchone()
    if not row: return None
    exp = datetime.fromisoformat(row[0])
    if exp < datetime.now():
        c.execute("DELETE FROM subs WHERE uid=?", (uid,))
        conn.commit()
        return None
    return (exp - datetime.now()).days

def activate(uid, days):
    c.execute("SELECT expires FROM subs WHERE uid=?", (uid,))
    row = c.fetchone()
    now = datetime.now()
    if row and datetime.fromisoformat(row[0]) > now:
        new = datetime.fromisoformat(row[0]) + timedelta(days=days)
    else:
        new = now + timedelta(days=days)
    c.execute("INSERT OR REPLACE INTO subs VALUES (?,?)", (uid, new.isoformat()))
    conn.commit()
    return new

@dp.message(Command("start"))
async def start(m): await m.answer("👻 GHOST DLC\nВыбери тариф:", reply_markup=menu())

@dp.message(lambda m: m.text == "📥 APK")
async def apk(m):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Скачать", url=APK_LINK)]])
    await m.answer("📱 Скачай APK:", reply_markup=kb)

@dp.message(lambda m: m.text in ["300₽ 7д", "600₽ 14д", "1200₽ 30д"])
async def buy(m):
    days = 7 if "300" in m.text else 14 if "600" in m.text else 30
    amount = 300 if days==7 else 600 if days==14 else 1200
    pay = price(amount)
    oid = f"{m.from_user.id}_{int(datetime.now().timestamp())}"
    k = key()
    c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)", (oid, m.from_user.id, amount, days, "waiting", k))
    conn.commit()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {pay}₽", callback_data=f"pay_{oid}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    await m.answer(f"✅ {amount}₽\n💳 К оплате: {pay}₽", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("pay_"))
async def pay(callback):
    oid = callback.data.replace("pay_", "")
    c.execute("SELECT amount FROM orders WHERE id=?", (oid,))
    row = c.fetchone()
    if not row:
        return await callback.answer("Ошибка")
    amount = row[0]
    pay_amount = price(amount)
    params = {"receiver": WALLET_NUMBER, "quickpay-form": "button", "paymentType": "AC", "sum": pay_amount, "label": oid, "successURL": "https://t.me"}
    url = "https://yoomoney.ru/quickpay/confirm?" + urllib.parse.urlencode(params)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=url)],
        [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_{oid}")]
    ])
    await callback.message.edit_text(f"💳 {pay_amount}₽", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("check_"))
async def check(callback):
    oid = callback.data.replace("check_", "")
    c.execute("SELECT uid, status, key FROM orders WHERE id=?", (oid,))
    row = c.fetchone()
    if not row:
        return await callback.answer("Ошибка")
    uid, status, k = row
    if status == "paid":
        days = sub_status(uid)
        await callback.message.edit_text(f"✅ Активна! Осталось: {days} дней\nКлюч: {k}")
        return await callback.answer()
    await callback.answer("⏳ Не оплачено", show_alert=True)

@dp.callback_query(lambda c: c.data == "cancel")
async def cancel(callback):
    await callback.message.edit_text("❌ Отменено")
    await callback.message.answer("Главное меню", reply_markup=menu())
    await callback.answer()

@dp.message(lambda m: m.text == "👤 Профиль")
async def profile(m):
    days = sub_status(m.from_user.id)
    if not days:
        return await m.answer("❌ Нет подписки", reply_markup=menu())
    c.execute("SELECT key FROM orders WHERE uid=? AND status='paid' ORDER BY rowid DESC LIMIT 1", (m.from_user.id,))
    row = c.fetchone()
    k = row[0] if row else "Нет"
    await m.answer(f"👤 Осталось: {days} дней\n🔑 {k}", reply_markup=menu())

@dp.message(lambda m: m.text == "📜 История")
async def history(m):
    c.execute("SELECT amount, status FROM orders WHERE uid=? ORDER BY rowid DESC LIMIT 5", (m.from_user.id,))
    rows = c.fetchall()
    if not rows:
        return await m.answer("📭 Пусто", reply_markup=menu())
    text = "📜 История:\n"
    for amount, status in rows:
        icon = "✅" if status == "paid" else "⏳"
        text += f"{icon} {amount}₽\n"
    await m.answer(text, reply_markup=menu())

@app.route('/yoomoney-webhook', methods=['POST'])
def webhook():
    data = request.form
    oid = data.get('label')
    if data.get('status') == 'success' and oid:
        c.execute("SELECT uid, days, key FROM orders WHERE id=?", (oid,))
        row = c.fetchone()
        if row:
            uid, days, k = row
            c.execute("UPDATE orders SET status='paid' WHERE id=?", (oid,))
            activate(uid, days)
            conn.commit()
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": uid, "text": f"✅ Оплачено!\n\nКлюч: {k}\n\nAPK: {APK_LINK}"})
            except: pass
    return "OK", 200

@app.route('/')
def index(): return "OK"

async def reminders():
    while True:
        try:
            for uid, exp_str in c.execute("SELECT uid, expires FROM subs").fetchall():
                days = (datetime.fromisoformat(exp_str) - datetime.now()).days
                if days == 3:
                    await bot.send_message(uid, "⚠️ Осталось 3 дня!")
            await asyncio.sleep(86400)
        except:
            await asyncio.sleep(86400)

def run():
    app.run(host='0.0.0.0', port=8080)

ADMIN_TOKEN = "ghost_admin_2024"

@app.route('/admin/create_key', methods=['POST'])
def admin_create_key():
    data = request.json
    if data.get('token') != ADMIN_TOKEN:
        return {"error": "Unauthorized"}, 401
    key = data.get('key')
    days = data.get('days')
    from datetime import datetime, timedelta
    expire = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("INSERT INTO ghost_keys VALUES (?, ?, ?, ?, ?)", (key, days, expire, datetime.now().isoformat(), None))
    conn.commit()
    return {"key": key, "expire": expire}

@app.route('/admin/list_keys', methods=['GET'])
def admin_list_keys():
    token = request.args.get('token')
    if token != ADMIN_TOKEN:
        return {"error": "Unauthorized"}, 401
    c.execute("SELECT key, days, expire FROM ghost_keys ORDER BY created_at DESC")
    rows = c.fetchall()
    keys = []
    for key, days, expire in rows:
        keys.append({"key": key, "days": days, "expire": expire, "valid": datetime.fromisoformat(expire) > datetime.now()})
    return keys

@app.route('/admin/delete_key', methods=['DELETE'])
def admin_delete_key():
    data = request.json
    if data.get('token') != ADMIN_TOKEN:
        return {"error": "Unauthorized"}, 401
    c.execute("DELETE FROM ghost_keys WHERE key=?", (data.get('key'),))
    conn.commit()
    return {"success": True}

async def main():
    await bot.delete_webhook()
    threading.Thread(target=run, daemon=True).start()
    asyncio.create_task(reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
