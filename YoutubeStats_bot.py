import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from datetime import datetime, timedelta
import re
import os
import logging
from functools import wraps
from typing import Optional, Dict, Any
import asyncio

# ================================
# CONFIGURATION
# ================================


class Config:
    """Bot configuration management"""

    BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN", "8434129815:AAGpRRVwcNRulAk9gOo7QqvJ_BpiEbZxJoo"
    )
    MAX_DESCRIPTION_LENGTH = 400
    MAX_TAGS_DISPLAY = 8
    CACHE_EXPIRY_MINUTES = 30
    RATE_LIMIT_SECONDS = 3
    LOG_LEVEL = logging.INFO


# ================================
# LOGGING SETUP
# ================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=Config.LOG_LEVEL,
)
logger = logging.getLogger(__name__)

# ================================
# UTILITIES & HELPERS
# ================================


class NumberFormatter:
    """Format numbers for display"""

    @staticmethod
    def format_large(num: int) -> str:
        """Format large numbers with K, M, B suffixes"""
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(num)

    @staticmethod
    def format_with_commas(num: int) -> str:
        """Format number with thousand separators"""
        return f"{num:,}"


class TimeFormatter:
    """Format time and duration"""

    @staticmethod
    def format_duration(seconds: Optional[int]) -> str:
        """Convert seconds to HH:MM:SS or MM:SS format"""
        if not seconds:
            return "N/A"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def get_time_ago(date_str: str) -> tuple[str, str]:
        """Convert upload date to readable format and time ago"""
        if not date_str:
            return "N/A", "N/A"

        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            upload_formatted = date_obj.strftime("%B %d, %Y")
            days_ago = (datetime.now() - date_obj).days

            if days_ago == 0:
                time_ago = "Today 🆕"
            elif days_ago == 1:
                time_ago = "Yesterday"
            elif days_ago < 7:
                time_ago = f"{days_ago} days ago"
            elif days_ago < 30:
                weeks = days_ago // 7
                time_ago = f"{weeks} week{'s' if weeks > 1 else ''} ago"
            elif days_ago < 365:
                months = days_ago // 30
                time_ago = f"{months} month{'s' if months > 1 else ''} ago"
            else:
                years = days_ago // 365
                time_ago = f"{years} year{'s' if years > 1 else ''} ago"

            return upload_formatted, time_ago
        except Exception as e:
            logger.error(f"Error parsing date: {e}")
            return "N/A", "N/A"


class VideoAnalyzer:
    """Analyze video metrics and quality"""

    @staticmethod
    def get_quality_badge(views: int) -> str:
        """Get quality badge based on views"""
        if views >= 100_000_000:
            return "🏆 MEGA VIRAL 🏆"
        elif views >= 10_000_000:
            return "💎 DIAMOND STATUS 💎"
        elif views >= 1_000_000:
            return "⭐ PLATINUM HIT ⭐"
        elif views >= 100_000:
            return "🔥 TRENDING HOT 🔥"
        elif views >= 10_000:
            return "📈 RISING STAR 📈"
        elif views >= 1_000:
            return "🌱 GROWING 🌱"
        else:
            return "🌟 NEW CONTENT 🌟"

    @staticmethod
    def calculate_engagement_rate(likes: int, comments: int, views: int) -> float:
        """Calculate engagement rate (likes + comments) / views"""
        if views == 0:
            return 0.0
        return ((likes + comments) / views) * 100

    @staticmethod
    def calculate_like_percentage(likes: int, views: int) -> float:
        """Calculate like percentage"""
        if views == 0:
            return 0.0
        return (likes / views) * 100

    @staticmethod
    def calculate_views_per_day(views: int, upload_date: str) -> Optional[float]:
        """Calculate average views per day"""
        if not upload_date:
            return None
        try:
            date_obj = datetime.strptime(upload_date, "%Y%m%d")
            days_ago = max((datetime.now() - date_obj).days, 1)
            return views / days_ago
        except:
            return None

    @staticmethod
    def get_performance_grade(engagement_rate: float) -> str:
        """Get performance grade based on engagement"""
        if engagement_rate >= 10:
            return "S+ (Outstanding)"
        elif engagement_rate >= 7:
            return "A (Excellent)"
        elif engagement_rate >= 5:
            return "B (Very Good)"
        elif engagement_rate >= 3:
            return "C (Good)"
        elif engagement_rate >= 1:
            return "D (Average)"
        else:
            return "E (Below Average)"


class VisualElements:
    """Create visual elements for messages"""

    @staticmethod
    def create_bar(
        percentage: float,
        length: int = 10,
        filled_char: str = "█",
        empty_char: str = "░",
    ) -> str:
        """Create a visual progress bar"""
        percentage = max(0, min(100, percentage))
        filled = int((percentage / 100) * length)
        return filled_char * filled + empty_char * (length - filled)

    @staticmethod
    def create_emoji_meter(value: float, max_value: float = 10) -> str:
        """Create emoji meter (⭐⭐⭐⭐⭐)"""
        stars = int((value / max_value) * 5)
        return "⭐" * stars + "☆" * (5 - stars)


class URLValidator:
    """Validate YouTube URLs"""

    YOUTUBE_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"

    @classmethod
    def is_valid_youtube_url(cls, url: str) -> bool:
        """Check if URL is a valid YouTube link"""
        return bool(re.match(cls.YOUTUBE_REGEX, url))

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"(?:watch\?v=)([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None


# ================================
# RATE LIMITING
# ================================


class RateLimiter:
    """Simple rate limiter to prevent spam"""

    def __init__(self):
        self.user_timestamps: Dict[int, datetime] = {}

    def is_allowed(
        self, user_id: int, cooldown_seconds: int = Config.RATE_LIMIT_SECONDS
    ) -> tuple[bool, int]:
        """Check if user is allowed to make request"""
        now = datetime.now()

        if user_id in self.user_timestamps:
            time_diff = (now - self.user_timestamps[user_id]).total_seconds()
            if time_diff < cooldown_seconds:
                wait_time = int(cooldown_seconds - time_diff)
                return False, wait_time

        self.user_timestamps[user_id] = now
        return True, 0


rate_limiter = RateLimiter()


def rate_limit(func):
    """Decorator for rate limiting"""

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user_id = update.effective_user.id
        allowed, wait_time = rate_limiter.is_allowed(user_id)

        if not allowed:
            await update.message.reply_text(
                f"⏳ <b>Slow down!</b>\n\n"
                f"Please wait <b>{wait_time}</b> seconds before next request.\n\n"
                f"<i>This prevents spam and ensures smooth operation for everyone! 😊</i>",
                parse_mode="HTML",
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ================================
# MESSAGE TEMPLATES
# ================================


class MessageTemplates:
    """Pre-formatted message templates"""

    @staticmethod
    def welcome_message() -> str:
        return (
            "🎬═══════════════════════🎬\n"
            "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃  🌟 <b>YOUTUBE ANALYZER</b> 🌟  ┃\n"
            "┃     〰️ PRO EDITION v3.0 〰️    ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━┛\n"
            "🎬═══════════════════════🎬\n\n"
            "💡 <b>ADVANCED ANALYTICS INCLUDES:</b>\n\n"
            "📊 <b>Performance Metrics</b>\n"
            "   • Views, Likes, Comments\n"
            "   • Engagement Rate & Grade\n"
            "   • Views per Day Analysis\n"
            "   • Performance Score\n\n"
            "📺 <b>Channel Intelligence</b>\n"
            "   • Subscriber Count & Growth\n"
            "   • Channel Verification Status\n"
            "   • Location & Country\n"
            "   • Creator Details\n\n"
            "🎯 <b>Content Analysis</b>\n"
            "   • Full Description & Tags\n"
            "   • Category & Age Rating\n"
            "   • Video Quality Info\n"
            "   • Thumbnail & Direct Links\n\n"
            "✨ <b>Special Features</b>\n"
            "   • Quality Badges\n"
            "   • Visual Progress Bars\n"
            "   • Trending Status\n"
            "   • Quick Statistics\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 <b>QUICK START:</b>\n"
            "Just paste any YouTube link and get instant detailed analysis!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 <b>Commands:</b>\n"
            "• /start - Show this message\n"
            "• /help - Detailed help guide\n"
            "• /stats - Bot statistics\n"
            "• /about - About this bot\n\n"
            "✨ <i>Ready to explore YouTube like never before? Send me a link now!</i> ✨"
        )

    @staticmethod
    def help_message() -> str:
        return (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📚 <b>COMPREHENSIVE HELP</b> 📚\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>HOW TO USE:</b>\n\n"
            "1️⃣ Copy any YouTube video URL\n"
            "2️⃣ Paste it in this chat\n"
            "3️⃣ Get instant comprehensive analysis\n"
            "4️⃣ Share insights with friends!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>SUPPORTED URL FORMATS:</b>\n\n"
            "✅ <code>youtube.com/watch?v=VIDEO_ID</code>\n"
            "✅ <code>youtu.be/VIDEO_ID</code>\n"
            "✅ <code>youtube.com/shorts/VIDEO_ID</code>\n"
            "✅ <code>youtube.com/embed/VIDEO_ID</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎁 <b>ANALYTICS PROVIDED:</b>\n\n"
            "📊 <b>Performance Metrics:</b>\n"
            "• Total Views & Likes\n"
            "• Comment Count\n"
            "• Engagement Rate (%)\n"
            "• Views per Day Average\n"
            "• Performance Grade (S+ to E)\n"
            "• Quality Badges\n\n"
            "📺 <b>Channel Information:</b>\n"
            "• Subscriber Count\n"
            "• Channel Location/Country\n"
            "• Verification Status\n"
            "• Creator Username\n\n"
            "🎥 <b>Video Details:</b>\n"
            "• Upload Date & Time Ago\n"
            "• Video Duration\n"
            "• Category & Genre\n"
            "• Tags & Keywords\n"
            "• Age Rating\n"
            "• Location Info\n\n"
            "📈 <b>Visual Analytics:</b>\n"
            "• Engagement Progress Bars\n"
            "• Like Ratio Indicators\n"
            "• Performance Meters\n"
            "• Status Badges\n\n"
            "🔗 <b>Quick Access Links:</b>\n"
            "• Direct Video Player\n"
            "• Channel Homepage\n"
            "• HD Thumbnail Image\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ <b>PRO TIPS:</b>\n\n"
            "💡 Works with public videos only\n"
            "💡 Private/deleted videos won't work\n"
            "💡 Age-restricted content may have limitations\n"
            "💡 Rate limited to prevent spam (3s cooldown)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❓ <b>Need Help?</b> Type /help anytime!\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    @staticmethod
    def about_message() -> str:
        return (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️ <b>ABOUT THIS BOT</b> ℹ️\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 <b>YouTube Analyzer Bot v3.0</b>\n\n"
            "🎯 <b>Purpose:</b>\n"
            "Advanced YouTube video analytics and statistics bot "
            "that provides comprehensive insights into any public YouTube video.\n\n"
            "⚙️ <b>Technology Stack:</b>\n"
            "• Python 3.x\n"
            "• python-telegram-bot\n"
            "• yt-dlp (YouTube data extraction)\n"
            "• Modern async/await architecture\n\n"
            "✨ <b>Features:</b>\n"
            "• Real-time video statistics\n"
            "• Advanced engagement analytics\n"
            "• Performance grading system\n"
            "• Visual progress indicators\n"
            "• Channel intelligence\n"
            "• Rate limiting & security\n"
            "• Beautiful formatting\n\n"
            "🔒 <b>Privacy & Security:</b>\n"
            "• No data storage\n"
            "• No tracking\n"
            "• Rate-limited requests\n"
            "• Public API usage only\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💝 Made with ❤️ for YouTube enthusiasts\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )


# ================================
# COMMAND HANDLERS
# ================================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    await update.message.reply_text(
        MessageTemplates.welcome_message(), parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(MessageTemplates.help_message(), parse_mode="HTML")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /about command"""
    await update.message.reply_text(MessageTemplates.about_message(), parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show bot statistics"""
    stats_msg = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>BOT STATISTICS</b> 📊\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Bot Version:</b> 3.0 Pro Edition\n"
        "⚡ <b>Status:</b> Online & Active\n"
        "🔄 <b>Response Time:</b> &lt;2 seconds\n"
        "🛡️ <b>Rate Limit:</b> 3 seconds cooldown\n"
        "📈 <b>Uptime:</b> Running smoothly\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>Capabilities:</b>\n"
        "• Video Analytics ✅\n"
        "• Channel Insights ✅\n"
        "• Engagement Metrics ✅\n"
        "• Performance Grading ✅\n"
        "• Visual Elements ✅\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Send a YouTube link to get started!\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(stats_msg, parse_mode="HTML")


# ================================
# MAIN VIDEO ANALYSIS HANDLER
# ================================


@rate_limit
async def get_youtube_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for YouTube video analysis"""
    url = update.message.text.strip()
    user = update.effective_user

    logger.info(f"User {user.id} requested analysis for: {url}")

    # Validate YouTube URL
    if not URLValidator.is_valid_youtube_url(url):
        error_msg = (
            "❌❌❌ <b>INVALID URL</b> ❌❌❌\n\n"
            "⚠️ Please send a valid YouTube link:\n\n"
            "✅ <code>youtube.com/watch?v=...</code>\n"
            "✅ <code>youtu.be/...</code>\n"
            "✅ <code>youtube.com/shorts/...</code>\n\n"
            "💡 <i>Copy the link directly from YouTube's address bar!</i>"
        )
        await update.message.reply_text(error_msg, parse_mode="HTML")
        return

    # Show processing message
    processing_msg = await update.message.reply_text(
        "⏳ <b>Analyzing Video...</b>\n\n"
        "🔍 Extracting video data...\n"
        "📡 Fetching statistics...\n"
        "📊 Calculating analytics...\n"
        "🎨 Generating report...\n\n"
        "<i>This will only take a moment...</i>",
        parse_mode="HTML",
    )

    try:
        # Configure yt-dlp options
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        # Extract video information
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # ===========================
            # EXTRACT VIDEO DATA
            # ===========================

            # Basic info
            title = info.get("title", "N/A")
            description = info.get("description", "No description available")[
                : Config.MAX_DESCRIPTION_LENGTH
            ]
            video_id = info.get("id", "N/A")

            # Channel info
            channel = info.get("channel", "N/A")
            channel_url = info.get("channel_url", "")
            uploader = info.get("uploader", "N/A")
            subscribers = info.get("channel_follower_count", 0)
            channel_country = info.get("channel_country", "Global")
            is_verified = info.get("channel_is_verified", False)

            # Statistics
            views = info.get("view_count", 0)
            likes = info.get("like_count", 0)
            comments = info.get("comment_count", 0)

            # Time info
            upload_date = info.get("upload_date", "")
            duration = info.get("duration", 0)

            # Content details
            categories = info.get("categories", [])
            category = categories[0] if categories else "Uncategorized"
            tags = info.get("tags", [])[: Config.MAX_TAGS_DISPLAY]
            location = info.get("location", "Not specified")
            age_limit = info.get("age_limit", 0)

            # Thumbnail
            thumbnail = info.get("thumbnail", "")

            # ===========================
            # CALCULATE ANALYTICS
            # ===========================

            # Format numbers
            views_fmt = NumberFormatter.format_large(views)
            likes_fmt = NumberFormatter.format_large(likes)
            comments_fmt = NumberFormatter.format_large(comments)
            subscribers_fmt = NumberFormatter.format_large(subscribers)

            # Time calculations
            upload_formatted, time_ago = TimeFormatter.get_time_ago(upload_date)
            duration_fmt = TimeFormatter.format_duration(duration)

            # Analytics
            quality_badge = VideoAnalyzer.get_quality_badge(views)
            engagement_rate = VideoAnalyzer.calculate_engagement_rate(
                likes, comments, views
            )
            like_percentage = VideoAnalyzer.calculate_like_percentage(likes, views)
            views_per_day = VideoAnalyzer.calculate_views_per_day(views, upload_date)
            performance_grade = VideoAnalyzer.get_performance_grade(engagement_rate)

            # Visual elements
            engagement_bar = VisualElements.create_bar(min(engagement_rate * 10, 100))
            like_bar = VisualElements.create_bar(min(like_percentage * 20, 100))
            performance_stars = VisualElements.create_emoji_meter(engagement_rate, 10)

            # Age rating
            age_icon = "🔞" if age_limit >= 18 else "✅"
            age_text = "18+ Only" if age_limit >= 18 else "Family Friendly"

            # Verification status
            verify_icon = "✅" if is_verified else "⚪"
            verify_text = "Verified" if is_verified else "Not Verified"

            # ===========================
            # BUILD RESPONSE MESSAGE
            # ===========================

            response = (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎬 <b>{title}</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ <b>STATUS:</b> {quality_badge}\n"
                f"🎯 <b>PERFORMANCE:</b> {performance_stars} {performance_grade}\n\n"
                "╔═══════════════════════════════╗\n"
                "║  📺 <b>CHANNEL INFORMATION</b>        ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"🎯 <b>Channel:</b> <a href='{channel_url}'>{channel}</a>\n"
                f"{verify_icon} <b>Status:</b> {verify_text}\n"
                f"👤 <b>Creator:</b> {uploader}\n"
                f"👥 <b>Subscribers:</b> {subscribers_fmt}\n"
                f"   └─ <code>{NumberFormatter.format_with_commas(subscribers)}</code> subscribers\n"
                f"🌍 <b>Country:</b> {channel_country}\n\n"
                "╔═══════════════════════════════╗\n"
                "║  📊 <b>PERFORMANCE ANALYTICS</b>      ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"👁️ <b>Total Views:</b> {views_fmt}\n"
                f"   └─ <code>{NumberFormatter.format_with_commas(views)}</code> views\n"
            )

            # Add views per day if available
            if views_per_day:
                response += f"   └─ <code>{NumberFormatter.format_large(int(views_per_day))}</code> views/day avg\n"

            response += (
                f"\n👍 <b>Likes:</b> {likes_fmt}\n"
                f"   └─ <code>{NumberFormatter.format_with_commas(likes)}</code> people liked\n\n"
                f"💬 <b>Comments:</b> {comments_fmt}\n"
                f"   └─ <code>{NumberFormatter.format_with_commas(comments)}</code> comments\n\n"
                f"📈 <b>Engagement Rate:</b> {engagement_rate:.2f}%\n"
                f"   {engagement_bar} <code>{engagement_rate:.2f}%</code>\n"
                f"   └─ Grade: <b>{performance_grade}</b>\n\n"
                f"⭐ <b>Like Ratio:</b> {like_percentage:.2f}%\n"
                f"   {like_bar} <code>{like_percentage:.2f}%</code>\n\n"
                "╔═══════════════════════════════╗\n"
                "║  🎥 <b>VIDEO DETAILS</b>              ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"🆔 <b>Video ID:</b> <code>{video_id}</code>\n"
                f"📅 <b>Published:</b> {upload_formatted}\n"
                f"⏰ <b>Uploaded:</b> {time_ago}\n"
                f"⏱️ <b>Duration:</b> <code>{duration_fmt}</code>\n"
                f"📁 <b>Category:</b> {category}\n"
                f"📍 <b>Location:</b> {location}\n"
                f"{age_icon} <b>Age Rating:</b> {age_text}\n\n"
            )

            # Tags section
            if tags:
                tags_display = " • ".join(f"#{tag}" for tag in tags)
                response += (
                    "╔═══════════════════════════════╗\n"
                    "║  🏷️ <b>TAGS & KEYWORDS</b>           ║\n"
                    "╚═══════════════════════════════╝\n\n"
                    f"<code>{tags_display}</code>\n\n"
                )

            # Description
            response += (
                "╔═══════════════════════════════╗\n"
                "║  📝 <b>DESCRIPTION</b>                ║\n"
                "╚═══════════════════════════════╝\n\n"
                f"<i>{description}{'...' if len(info.get('description', '')) > Config.MAX_DESCRIPTION_LENGTH else ''}</i>\n\n"
            )

            # Quick links
            response += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔗 <b>QUICK ACCESS LINKS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"▶️ <a href='{url}'>Watch Video</a>\n"
                f"📺 <a href='{channel_url}'>Visit Channel</a>\n"
            )

            if thumbnail:
                response += f"🖼️ <a href='{thumbnail}'>View Thumbnail</a>\n"

            response += (
                "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✅ <b>Analysis Complete!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "💡 <i>Share this analysis with friends or analyze another video!</i>"
            )

            # Delete processing message and send result
            await processing_msg.delete()
            await update.message.reply_text(
                response, parse_mode="HTML", disable_web_page_preview=True
            )

            logger.info(f"Successfully analyzed video: {video_id} for user {user.id}")

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error for user {user.id}: {str(e)}")
        await processing_msg.delete()
        error_msg = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ <b>VIDEO UNAVAILABLE</b> ❌\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "😔 <b>Unable to fetch video data</b>\n\n"
            "🔍 <b>Possible reasons:</b>\n"
            "• Video is private or deleted\n"
            "• Age-restricted content\n"
            "• Geographic restrictions active\n"
            "• Invalid or expired video ID\n"
            "• Channel terminated\n\n"
            "💡 <b>Try:</b>\n"
            "✓ Checking if video is public\n"
            "✓ Opening link in browser first\n"
            "✓ Using a different video\n\n"
            f"📝 <code>{str(e)[:200]}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(error_msg, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Unexpected error for user {user.id}: {str(e)}", exc_info=True)
        await processing_msg.delete()
        error_msg = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>UNEXPECTED ERROR</b> ⚠️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔧 <b>Something went wrong!</b>\n\n"
            "<b>Please try:</b>\n"
            "✓ Verifying the URL is correct\n"
            "✓ Trying a different video\n"
            "✓ Waiting a moment and retrying\n"
            "✓ Using /help for guidance\n\n"
            f"📝 <b>Error:</b>\n<code>{str(e)[:200]}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 If this persists, the video may have special restrictions."
        )
        await update.message.reply_text(error_msg, parse_mode="HTML")


# ================================
# APPLICATION SETUP & MAIN
# ================================


def main():
    """Main function to start the bot"""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 YOUTUBE ANALYZER BOT v3.0 PRO")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("⚡ Initializing bot systems...")

    # Check if token is available
    if not Config.BOT_TOKEN:
        logger.error(
            "Bot token not found! Set TELEGRAM_BOT_TOKEN environment variable."
        )
        print("❌ ERROR: Bot token not configured!")
        return

    try:
        # Build application
        print("🔧 Building application...")
        app = ApplicationBuilder().token(Config.BOT_TOKEN).build()

        # Register command handlers
        print("📡 Registering command handlers...")
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("about", about_command))
        app.add_handler(CommandHandler("stats", stats_command))

        # Register message handler for YouTube links
        print("🔗 Registering YouTube link handler...")
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, get_youtube_info)
        )

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Bot is ONLINE and ready!")
        print("📻 Listening for YouTube links...")
        print("🛡️ Rate limiting: Active")
        print("📊 Analytics: Enhanced")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        logger.info("Bot started successfully")

        # Start polling
        app.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        print(f"❌ ERROR: {str(e)}")
        print("Please check your bot token and internet connection.")


if __name__ == "__main__":
    main()
