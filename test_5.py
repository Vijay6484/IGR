"""
TEST SCRIPT: Same as 5.py but limited scope for testing.
- Year: 2026 only
- 1st district only
- 1st tehsil only
- 15th village only
- Property numbers: 1 to 20
"""
import os
import sys
import time
import json
import subprocess
import platform
try:
    import pyautogui
except (ImportError, KeyError):
    pyautogui = None  # KeyError when DISPLAY unset (VPS/headless)
try:
    import pyperclip
except ImportError:
    pyperclip = None
import traceback
import base64
import hashlib
import requests
import multiprocessing
import signal
import psutil
import logging
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException, 
    NoSuchWindowException, WebDriverException, ElementNotInteractableException
)
from webdriver_manager.chrome import ChromeDriverManager

# CAPTCHA API configuration
CAPTCHA_API_KEY = "CAP-75F09498C5E101DFDD1983D60827629D199BAD3721A5D3573A1423EB6EA6DF6B"
CAPTCHA_API_URL = "https://api.capsolver.com/createTask"
CAPTCHA_RESULT_URL = "https://api.capsolver.com/getTaskResult"

# Global constants
BUTTON_CLICK_TIMEOUT = 60
POPUP_TIMEOUT = 60
SESSION_CHECK_INTERVAL = 60
MAX_PAGES_PER_GUT = 10000
MAX_SESSION_RETRY = 5
WEBSITE_URL = "https://freesearchigrservice.maharashtra.gov.in"
MAX_CAPTCHA_WAIT = 80

# List of proxies to dynamically rotate IPs. Format: 'http://user:pass@ip:port' or 'http://ip:port'
# Example: PROXIES = ["http://12.34.56.78:8080", "http://98.76.54.32:80"]
PROXIES = [] # Keep empty to run without proxy

# Set HEADLESS_MODE to True to enable headless operation (no visible browser)
HEADLESS_MODE = False

# VPS_MODE: Set to True to force VPS/server mode (no GUI). When True: headless browser,
# Chrome/Chromium on Linux, no sounds. Auto-enabled when: (1) VPS_MODE=1 env var, or
# (2) Linux with no DISPLAY. To force on Mac: set VPS_MODE = True below or VPS_MODE=1.
VPS_MODE = (
    os.environ.get("VPS_MODE", "").lower() in ("1", "true", "yes") or
    (platform.system() == "Linux" and not os.environ.get("DISPLAY", "").strip())
)
# VPS mode forces headless (no browser window)
if VPS_MODE:
    HEADLESS_MODE = True

# Path to Brave Browser (macOS) - used when not in VPS mode
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"

# Paths to Chrome/Chromium on Linux VPS (checked in order when VPS_MODE is True).
# Install: sudo apt update && sudo apt install -y chromium  (Ubuntu 22.04+)
# Or Google Chrome: https://www.google.com/chrome/
CHROME_PATHS_LINUX = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",           # apt install chromium (Ubuntu 22.04+)
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
]

# Set MAX_CONCURRENT_PROCESSES to limit the number of simultaneous scrapers
MAX_CONCURRENT_PROCESSES = 1  # Sequential processing

# Set LOGGING_TYPE to choose logging method
# Options: "NONE", "JSON", "COMPRESSED_JSON", "TEXT", "LOGGING"
LOGGING_TYPE = "COMPRESSED_JSON"  # Default to compressed JSON for space efficiency

# Set LOG_RETENTION_DAYS to automatically delete old logs
LOG_RETENTION_DAYS = 30  # Keep logs for 30 days

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BRIGHT_RED = '\033[91;1m'
    BRIGHT_GREEN = '\033[92;1m'
    BRIGHT_YELLOW = '\033[93;1m'
    BRIGHT_BLUE = '\033[94;1m'
    BRIGHT_MAGENTA = '\033[95;1m'
    BRIGHT_CYAN = '\033[96;1m'
    BRIGHT_WHITE = '\033[97;1m'
    ENDC = '\033[0m'  # End color

# Generate year colors mapping for all years from 1985 to 2024
def generate_year_colors():
    year_colors = {}
    available_colors = [
        Colors.CYAN, Colors.MAGENTA, Colors.GREEN, Colors.YELLOW, 
        Colors.BLUE, Colors.RED, Colors.WHITE,
        Colors.BRIGHT_CYAN, Colors.BRIGHT_MAGENTA, Colors.BRIGHT_GREEN,
        Colors.BRIGHT_YELLOW, Colors.BRIGHT_BLUE, Colors.BRIGHT_RED, Colors.BRIGHT_WHITE
    ]
    
    years = list(range(1985, 2023))  # 1985 to 2022
    for i, year in enumerate(years):
        color_index = i % len(available_colors)
        year_colors[str(year)] = available_colors[color_index]
    
    return year_colors

YEAR_COLORS = generate_year_colors()

def kill_all_chrome_processes():
    """Kill all Chrome and ChromeDriver processes for current process only"""
    try:
        # Get current process ID
        current_pid = os.getpid()
        
        # Kill Chrome processes that are children of current process
        for proc in psutil.process_iter(['pid', 'name', 'ppid']):
            try:
                if 'chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower():
                    # Check if this is a child process of our scraper
                    parent_pid = proc.info['ppid']
                    if parent_pid == current_pid:
                        proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        time.sleep(3)  # Give processes time to terminate
        return True
    except:
        return False

def cleanup_orphaned_chrome_processes():
    """Clean up any orphaned Chrome processes for current process only"""
    try:
        current_pid = os.getpid()
        
        for proc in psutil.process_iter(['pid', 'name', 'ppid']):
            try:
                if ('chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower()) and proc.info['ppid'] == current_pid:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        time.sleep(2)
        return True
    except:
        return False

def make_safe_print(year):
    """Create a safe_print function with year prefix and color"""
    color = YEAR_COLORS.get(year, Colors.WHITE)  # Default to white if year not in mapping
    
    def safe_print_inner(*args):
        try:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{year}] {' '.join(map(str, args))}"
            print(f"{color}{msg}{Colors.ENDC}", flush=True)
        except:
            pass
    return safe_print_inner

def init_year_directories(year):
    """Initialize year-specific directories - TEST: uses test_scraped folder"""
    CURRENT_DIR = os.getcwd()
    OUTPUT_DIR = os.path.join(CURRENT_DIR, "test_scraped", year)
    SCREENSHOT_DIR = os.path.join(OUTPUT_DIR, "screenshots")
    LOG_DIR = os.path.join(OUTPUT_DIR, "logs")
    
    # Create directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    return {
        "OUTPUT_DIR": OUTPUT_DIR,
        "SCREENSHOT_DIR": SCREENSHOT_DIR,
        "LOG_DIR": LOG_DIR,
        "PROGRESS_FILE": os.path.join(LOG_DIR, "progress.json"),
        "FAILED_FILE": os.path.join(LOG_DIR, "failed_guts.json"),
        "SPECIAL_FILE": os.path.join(LOG_DIR, "special_case_guts.jsonl"),
        "RUN_STATUS_FILE": os.path.join(LOG_DIR, "run_status.json"),
        "LOG_FILE": os.path.join(LOG_DIR, "scraper.log"),
        "COMPRESSED_LOG_FILE": os.path.join(LOG_DIR, "scraper.log.gz"),
        "JSON_LOG_FILE": os.path.join(LOG_DIR, "scraper.json"),
        "CAPTCHA_IMAGE_PATH": os.path.join(SCREENSHOT_DIR, "captcha_image.png"),
        "VILLAGE_MISMATCH_FILE": os.path.join(LOG_DIR, "village_mismatch.json"),
        "SEEN_DOCS_FILE": os.path.join(LOG_DIR, "seen_docs.txt")
    }

def setup_logger(log_file, year):
    """Set up a logger for the given year"""
    logger = logging.getLogger(f"scraper_{year}")
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger

def log_to_json(log_file, level, category, message, details=None):
    """Log to a JSON file"""
    log_entry = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "level": level,
        "category": category,
        "message": message,
        "details": details or {}
    }
    
    try:
        # Read existing logs if file exists
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except:
                logs = []
        
        # Add new log entry
        logs.append(log_entry)
        
        # Write back to file
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LOG ERROR] Failed to write to JSON log: {e}")

def log_to_compressed_json(log_file, level, category, message, details=None):
    """Log to a compressed JSON file"""
    import gzip
    
    log_entry = {
        "t": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Shorter key name
        "l": level[0],  # Just first letter of level
        "c": category,
        "m": message,
        "d": details or {}
    }
    
    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)
            
    try:
        # Read existing logs if file exists
        logs = []
        if os.path.exists(log_file):
            try:
                with gzip.open(log_file, "rt", encoding="utf-8") as f:
                    logs = json.load(f)
            except:
                logs = []
        
        # Add new log entry
        logs.append(log_entry)
        
        # Write back to file with compression
        with gzip.open(log_file, "wt", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, cls=SetEncoder)
    except Exception as e:
        print(f"[LOG ERROR] Failed to write to compressed JSON log: {e}")

def cleanup_old_logs(log_dir, retention_days):
    """Remove log files older than retention_days"""
    try:
        now = time.time()
        cutoff = now - (retention_days * 24 * 60 * 60)
        
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff:
                    try:
                        os.remove(filepath)
                        print(f"Removed old log file: {filename}")
                    except Exception as e:
                        print(f"Failed to remove old log file {filename}: {e}")
    except Exception as e:
        print(f"Error during log cleanup: {e}")

def run_scraper_for_year(year, window_position):
    """Run the scraper for a specific year with window positioning"""
    # Set process name for better identification
    try:
        import setproctitle
        setproctitle.setproctitle(f"scraper_{year}")
    except ImportError:
        pass
    
    # Initialize year-specific paths
    paths = init_year_directories(year)
    
    # Extract paths for easier access
    OUTPUT_DIR = paths["OUTPUT_DIR"]
    SCREENSHOT_DIR = paths["SCREENSHOT_DIR"]
    LOG_DIR = paths["LOG_DIR"]
    PROGRESS_FILE = paths["PROGRESS_FILE"]
    FAILED_FILE = paths["FAILED_FILE"]
    SPECIAL_FILE = paths["SPECIAL_FILE"]
    RUN_STATUS_FILE = paths["RUN_STATUS_FILE"]
    LOG_FILE = paths["LOG_FILE"]
    COMPRESSED_LOG_FILE = paths["COMPRESSED_LOG_FILE"]
    JSON_LOG_FILE = paths["JSON_LOG_FILE"]
    CAPTCHA_IMAGE_PATH = paths["CAPTCHA_IMAGE_PATH"]
    VILLAGE_MISMATCH_FILE = paths["VILLAGE_MISMATCH_FILE"]
    SEEN_DOCS_FILE = paths.get("SEEN_DOCS_FILE", os.path.join(LOG_DIR, "seen_docs.txt"))
    
    # Create year-specific safe_print function
    safe_print = make_safe_print(year)
    
    # Initialize variables
    global_counter = {"total_records": 0, "total_pages": 0}
    RUN_STATUS = {}
    stop_script = False
    STOP_FILE = os.path.join(os.path.expanduser("~/Documents"), "stop_script.txt")
    
    # Setup logging based on selected type
    logger = None
    if LOGGING_TYPE == "LOGGING":
        logger = setup_logger(LOG_FILE, year)
    
    # Clean up old logs
    cleanup_old_logs(LOG_DIR, LOG_RETENTION_DAYS)
    
    # Play alert sounds (no-op in VPS/headless mode - no audio output)
    def play_alert_sound():
        if VPS_MODE:
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], capture_output=True)
            else:
                print("\a")
        except:
            print("\a")
    
    def play_village_complete_sound():
        """Play a different sound when village scraping is completed"""
        if VPS_MODE:
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(['afplay', '/System/Library/Sounds/Ping.aiff'], capture_output=True)
            else:
                print("\a\a")
        except:
            print("\a\a")
    
    def play_year_complete_sound():
        """Play a special sound when year scraping is completed"""
        if VPS_MODE:
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(['afplay', '/System/Library/Sounds/Blow.aiff'], capture_output=True)
            else:
                print("\a\a\a")
        except:
            print("\a\a\a")
    
    # Logging function based on selected type
    def log_message(level, category, message, details=None):
        if LOGGING_TYPE == "NONE":
            # No logging to files
            pass
        elif LOGGING_TYPE == "JSON":
            log_to_json(JSON_LOG_FILE, level, category, message, details)
        elif LOGGING_TYPE == "COMPRESSED_JSON":
            log_to_compressed_json(COMPRESSED_LOG_FILE, level, category, message, details)
        elif LOGGING_TYPE == "TEXT":
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")
                    if details:
                        f.write(f"Details: {json.dumps(details, ensure_ascii=False)}\n")
            except Exception as e:
                safe_print(f"[LOG ERROR] {e}")
        elif LOGGING_TYPE == "LOGGING":
            if logger:
                if details:
                    logger.info(f"[{category}] {message} - Details: {json.dumps(details, ensure_ascii=False)}")
                else:
                    logger.info(f"[{category}] {message}")
    
    # Save and load functions
    def save_run_status():
        try:
            with open(RUN_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(RUN_STATUS, f, ensure_ascii=False, indent=2)
        except Exception as e:
            safe_print(f"[ERROR] Failed to save run status: {e}")
    
    def load_run_status():
        if os.path.exists(RUN_STATUS_FILE):
            try:
                with open(RUN_STATUS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def load_progress():
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_progress(progress):
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            safe_print(f"[ERROR] Progress save failed: {e}")
    
    def log_failed(y, d, t, v, g, page=None):
        try:
            with open(FAILED_FILE, "a", encoding="utf-8") as f:
                data = {"year": y, "district": d, "tahsil": t, "village": v, "gut": g}
                if page:
                    data["page"] = page
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            safe_print(f"[ERROR] Failed to log failed attempt: {e}")
    
    def log_special(y, d, t, v, g):
        try:
            with open(SPECIAL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"year": y, "district": d, "tahsil": t, "village": v, "gut": g}, ensure_ascii=False) + "\n")
        except Exception as e:
            safe_print(f"[ERROR] Failed to log special case: {e}")
    
    def log_village_mismatch(district, tahsil, expected_village, available_villages):
        try:
            mismatch_data = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "district": district,
                "tahsil": tahsil,
                "expected_village": expected_village,
                "available_villages": available_villages[:10]
            }
            
            with open(VILLAGE_MISMATCH_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(mismatch_data, ensure_ascii=False) + "\n")
        except Exception as e:
            safe_print(f"[ERROR] Failed to log village mismatch: {e}")
            
    def _village_key(meta):
        """Unique key for village (used for deduplication scope)"""
        return f"{meta['year']}|{meta['district']}|{meta['tahsil']}|{meta['village']}"
    
    def _village_hash(meta):
        """Hash of village key for file storage"""
        return hashlib.md5(_village_key(meta).encode()).hexdigest()[:16]
    
    def load_seen_docs():
        """Load seen docs: dict of village_hash -> set of HTML content hashes (exact match dedup per village)"""
        seen = {}
        if os.path.exists(SEEN_DOCS_FILE):
            try:
                with open(SEEN_DOCS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "|" in line:
                            parts = line.split("|", 1)
                            if len(parts) == 2:
                                v_hash, content_hash = parts
                                seen.setdefault(v_hash, set()).add(content_hash)
            except Exception as e:
                safe_print(f"[ERROR] Failed to load seen docs: {e}")
        return seen

    def add_seen_doc(village_hash, content_hash):
        try:
            with open(SEEN_DOCS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{village_hash}|{content_hash}\n")
        except Exception as e:
            safe_print(f"[ERROR] Failed to save seen doc: {e}")
    
    # Browser functions
    def is_browser_alive(driver):
        """Check if browser/ChromeDriver session is still responsive"""
        try:
            _ = driver.current_url
            return True
        except (NoSuchWindowException, WebDriverException, ConnectionError, OSError):
            return False
        except Exception as e:
            if "Connection refused" in str(e) or "Connection" in str(e).lower():
                return False
            raise
    
    def is_session_dead_error(e):
        """Check if exception indicates session/browser connection is dead"""
        if isinstance(e, (WebDriverException, ConnectionError, OSError)):
            return True
        err_str = str(e).lower()
        return "connection refused" in err_str or "max retries exceeded" in err_str
    
    def safe_get_url(driver, url, max_retries=3):
        """Safely get URL with retries"""
        for attempt in range(1, max_retries + 1):
            try:
                safe_print(f"[URL LOAD] Attempt {attempt}/{max_retries} to load {url}")
                driver.set_page_load_timeout(120)
                driver.get(url)
                return True
            except TimeoutException:
                safe_print(f"[URL LOAD TIMEOUT] Attempt {attempt} failed for {url}")
                if attempt < max_retries:
                    try:
                        driver.execute_script("window.stop();")
                    except:
                        pass
                    time.sleep(5)
                    continue
                return False
            except Exception as e:
                safe_print(f"[URL LOAD ERROR] Attempt {attempt} failed for {url}: {e}")
                if is_session_dead_error(e):
                    safe_print("[URL LOAD] Session dead - caller should restart browser")
                    return False
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return False
        return False
    
    def terminate_driver_safely(driver):
        """Safely terminate the WebDriver and associated browser processes"""
        try:
            if driver:
                # Try to quit the driver normally first
                driver.quit()
        except:
            pass
        
        # Kill any remaining Chrome processes for this process only
        kill_all_chrome_processes()
        cleanup_orphaned_chrome_processes()
    
    def safe_browser_restart(max_retries=MAX_SESSION_RETRY):
        for attempt in range(1, max_retries + 1):
            try:
                safe_print(f"[SESSION RESTART] Attempt {attempt}/{max_retries}")
                
                # Kill any existing Chrome processes for this process only
                terminate_driver_safely(None)
                
                # Create new browser instance with enhanced options
                opts = Options()
                
                # Browser binary: VPS uses Chrome/Chromium on Linux; otherwise Brave on macOS
                browser_path = None
                if VPS_MODE:
                    for path in CHROME_PATHS_LINUX:
                        if os.path.exists(path):
                            browser_path = path
                            safe_print(f"[INFO] VPS mode: Using Chrome/Chromium from: {path}")
                            break
                    if not browser_path:
                        safe_print("[WARN] VPS mode: No Chrome/Chromium found, using system default")
                elif os.path.exists(BRAVE_PATH):
                    browser_path = BRAVE_PATH
                    safe_print(f"[INFO] Using Brave Browser from: {BRAVE_PATH}")
                else:
                    safe_print(f"[WARN] Brave not found at {BRAVE_PATH}, falling back to default Chrome")
                if browser_path:
                    opts.binary_location = browser_path
                
                opts.add_argument("--disable-extensions")
                opts.add_argument("--disable-notifications")
                opts.add_argument("--disable-blink-features=AutomationControlled")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                opts.add_argument("--disable-gpu")
                opts.add_argument("--remote-allow-origins=*")
                if VPS_MODE:
                    opts.add_argument("--disable-software-rasterizer")
                    opts.add_argument("--disable-setuid-sandbox")
                    opts.add_argument("--disable-background-networking")
                    opts.add_argument("--disable-default-apps")
                    opts.add_argument("--disable-sync")
                    opts.add_argument("--metrics-recording-only")
                    opts.add_argument("--mute-audio")
                opts.add_argument("--disable-infobars")
                opts.add_argument("--disable-popup-blocking")
                opts.add_argument("--dns-prefetch-disable")
                opts.add_argument("--disable-browser-side-navigation")
                opts.add_argument("--memory-cache-size=1")
                
                # IP Rotation logic via proxy selection
                if PROXIES:
                    random_proxy = random.choice(PROXIES)
                    opts.add_argument(f'--proxy-server={random_proxy}')
                    safe_print(f"[STEALTH] Random IP Rotation: Routing connection through {random_proxy}")
                
                opts.add_experimental_option("excludeSwitches", ["enable-automation"])
                opts.add_experimental_option('useAutomationExtension', False)
                
                # Add unique user data directory with timestamp to avoid lock issues
                timestamp = int(time.time())
                user_data_dir = os.path.join(os.path.expanduser("~"), f".chrome_scraper_{year}_{timestamp}")
                opts.add_argument(f"--user-data-dir={user_data_dir}")
                
                # Headless mode: no visible browser (required for VPS, optional for local)
                if HEADLESS_MODE:
                    opts.add_argument("--headless=new")
                    opts.add_argument("--window-size=1920,1080")
                    opts.add_argument("--disable-web-security")
                    opts.add_argument("--allow-running-insecure-content")
                    safe_print("[INFO] Running in headless mode (no browser window)")
                
                # Use eager strategy to DOM loaded only instead of full layout loaded (massive speed up)
                # Captcha solver has explicit wait for image, so this is safe
                opts.page_load_strategy = 'eager'
                
                driver = webdriver.Chrome(options=opts)
                driver.set_page_load_timeout(30)
                wait = WebDriverWait(driver, 30)
                
                # Set window position and size (only applies in non-headless mode)
                if not HEADLESS_MODE:
                    driver.set_window_position(window_position[0], window_position[1])
                    driver.set_window_size(window_position[2], window_position[3])
                
                # Test browser functionality
                if not safe_get_url(driver, "about:blank"):
                    raise Exception("Failed to load about:blank")
                    
                safe_print(f"[SESSION RESTART] Success on attempt {attempt}")
                return driver, wait
            except Exception as e:
                safe_print(f"[SESSION RESTART ERROR] Attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(5)  # Longer wait between retries
                    continue
                else:
                    raise RuntimeError(f"Failed to restart browser after {max_retries} attempts")
    
    def close_popup_and_click_rest(driver, wait):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Close popup if exists
                try:
                    popup_btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".btnclose.btn.btn-danger"))
                    )
                    popup_btn.click()
                    time.sleep(2)
                    safe_print("[INFO] Closed popup")
                except TimeoutException:
                    pass
                
                # Click other district search
                wait.until(EC.element_to_be_clickable((By.ID, "btnOtherdistrictSearch"))).click()
                wait.until(EC.visibility_of_element_located((By.ID, "ddlFromYear1")))
                return driver, wait
                
            except (TimeoutException, NoSuchWindowException, StaleElementReferenceException, WebDriverException) as e:
                safe_print(f"[WARN] Form not loaded, restarting browser ({attempt}/{max_attempts}): {e}")
                terminate_driver_safely(driver)
                driver, wait = safe_browser_restart()
                if not safe_get_url(driver, WEBSITE_URL):
                    if attempt < max_attempts:
                        continue
                    raise RuntimeError("Failed to load website after multiple attempts")
        
        raise RuntimeError("Form not loaded after retries")
    
    # CAPTCHA functions - keeping these unchanged as they're working correctly
    def solve_captcha_with_api(image_path, api_key, timeout=180):
        """Solve CAPTCHA using CapSolver API with multiple attempts and different modules"""
        modules_to_try = ["common", "queueit", "fast"]
        
        for module in modules_to_try:
            for attempt in range(1, 5):
                try:
                    with open(image_path, 'rb') as img_file:
                        img_data = img_file.read()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    
                    task_data = {
                        "clientKey": api_key,
                        "task": {
                            "type": "ImageToTextTask",
                            "body": img_base64,
                            "module": module
                        }
                    }
                    
                    headers = {"Content-Type": "application/json"}
                    safe_print(f"[CAPTCHA API] Trying module {module}, attempt {attempt}")
                    response = requests.post(CAPTCHA_API_URL, json=task_data, headers=headers, timeout=30)
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get("errorId") != 0:
                        safe_print(f"[CAPTCHA API ERROR] Module {module}, attempt {attempt}: {result.get('errorDescription', 'Unknown error')}")
                        continue
                        
                    if result.get("status") == "ready" and "solution" in result:
                        solution = result.get("solution", {})
                        captcha_text = solution.get("text", "")
                        if captcha_text:
                            safe_print(f"[CAPTCHA API] Module {module} solved CAPTCHA: {captcha_text}")
                            return [captcha_text.upper(), captcha_text.lower(), captcha_text]
                    
                    task_id = result.get("taskId")
                    if not task_id:
                        continue
                        
                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        result_data = {"clientKey": api_key, "taskId": task_id}
                        response = requests.post(CAPTCHA_RESULT_URL, json=result_data, headers=headers, timeout=10)
                        result = response.json()
                        
                        if result.get("errorId") != 0:
                            break
                            
                        if result.get("status") == "ready":
                            solution = result.get("solution", {})
                            captcha_text = solution.get("text", "")
                            if captcha_text:
                                safe_print(f"[CAPTCHA API] Module {module} solved CAPTCHA: {captcha_text}")
                                return [captcha_text.upper(), captcha_text.lower(), captcha_text]
                        time.sleep(5)
                        
                except Exception as e:
                    safe_print(f"[CAPTCHA API ERROR] Module {module}, attempt {attempt}: {e}")
                    continue
        
        return None
    
    def submit_dummy_captcha(driver, wait, safe_print_func):
        """Submit dummy captcha to trigger new captcha generation"""
        try:
            # Find captcha input and submit button
            cap_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Enter captcha as shown']")))
            submit_btn = wait.until(EC.element_to_be_clickable((By.ID, "btnSearch_RestMaha")))
            
            # Get current captcha image source for comparison later
            try:
                img_elem = driver.find_element(By.ID, "imgCaptcha_new")
                old_captcha_src = img_elem.get_attribute("src")
            except:
                old_captcha_src = None
            
            # Submit dummy captcha
            driver.execute_script("arguments[0].value='1';", cap_input)
            submit_btn.click()
            
            # Return the captcha element for later use
            try:
                captcha_elem = driver.find_element(By.ID, "imgCaptcha_new")
                return captcha_elem
            except:
                return None
                
        except Exception as e:
            safe_print_func(f"[DUMMY CAPTCHA ERROR] {e}")
            return None
    
    def solve_captcha_with_api_and_submit(driver, wait, safe_print_func, captcha_image_path):
        """Solve captcha with API integration and submit form"""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if not is_browser_alive(driver):
                    return False
                    
                # Wait for captcha input to be present
                cap_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Enter captcha as shown']")))
                
                # Get current captcha image source for comparison
                try:
                    img_elem = driver.find_element(By.ID, "imgCaptcha_new")
                    old_captcha_src = img_elem.get_attribute("src")
                except:
                    old_captcha_src = None
                    
                # Submit dummy captcha to trigger new captcha
                driver.execute_script("arguments[0].value='1';", cap_input)
                driver.find_element(By.ID, "btnSearch_RestMaha").click()
                
                # Define function to check if new captcha has loaded
                def new_captcha_loaded(driver):
                    try:
                        # Check if session is expired by looking for essential elements
                        try:
                            driver.find_element(By.ID, "ddlFromYear1")
                        except NoSuchElementException:
                            return False  # Session expired
                        
                        if not is_browser_alive(driver):
                            return False
                        img = driver.find_element(By.ID, "imgCaptcha_new")
                        if not img.is_displayed():
                            return False
                        current_src = img.get_attribute("src")
                        if old_captcha_src and current_src == old_captcha_src:
                            return False
                        if not current_src or "data:image" in current_src:
                            return False
                        natural_width = driver.execute_script("return arguments[0].naturalWidth;", img)
                        return natural_width > 0
                    except:
                        return False
                
                # Wait for new captcha to load with extended timeout
                try:
                    safe_print_func(f"[CAPTCHA] Waiting for new captcha to load (attempt {attempt}/3, timeout: {MAX_CAPTCHA_WAIT}s)...")
                    WebDriverWait(driver, MAX_CAPTCHA_WAIT).until(new_captcha_loaded)
                    time.sleep(1)
                    
                    if not is_browser_alive(driver):
                        return False
                        
                    # Take screenshot of the new captcha
                    img_elem = driver.find_element(By.ID, "imgCaptcha_new")
                    img_elem.screenshot(captcha_image_path)
                    
                    # Solve captcha with API
                    possible_solutions = solve_captcha_with_api(captcha_image_path, CAPTCHA_API_KEY)
                    if possible_solutions is None:
                        safe_print_func("[CAPTCHA API ERROR] Failed to solve captcha with API")
                        if attempt < max_attempts:
                            continue
                        return False
                    
                    # Try each possible solution
                    for i, captcha_text in enumerate(possible_solutions):
                        safe_print_func(f"[CAPTCHA] Trying solution {i+1}/{len(possible_solutions)}: {captcha_text}")
                        
                        if not is_browser_alive(driver):
                            return False
                            
                        # Enter captcha solution
                        cap_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Enter captcha as shown']")))
                        driver.execute_script(f"arguments[0].value='{captcha_text}';", cap_input)
                        driver.find_element(By.ID, "btnSearch_RestMaha").click()
                        time.sleep(2)
                        
                        # Check if captcha was accepted
                        try:
                            error_msg = driver.find_element(By.ID, "lblMsgCTS1").text
                            if "Invalid Captcha" in error_msg or "wrong captcha" in error_msg.lower():
                                safe_print_func(f"[CAPTCHA] Solution {captcha_text} was incorrect")
                                continue
                            else:
                                safe_print_func(f"[CAPTCHA] Solved and submitted: {captcha_text}")
                                return True
                        except NoSuchElementException:
                            # No error message, likely successful
                            safe_print_func(f"[CAPTCHA] Solved and submitted: {captcha_text}")
                            return True
                            
                except TimeoutException:
                    safe_print_func(f"[CAPTCHA] Timeout waiting for new captcha to load (attempt {attempt}/3)")
                    if attempt < max_attempts:
                        continue
                    return False
                    
            except Exception as e:
                safe_print_func(f"[CAPTCHA ERROR] Exception during captcha solving (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(2)
                    continue
                return False
        
        return False
    
    # Continue with the rest of the browser functions
    def get_dropdown_options_safe(driver, select_id, max_retries=10):
        for attempt in range(1, max_retries + 1):
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.ID, select_id))
                )
                
                WebDriverWait(driver, 30).until(
                    lambda d: len(Select(d.find_element(By.ID, select_id)).options) > 1
                )
                
                sel = Select(driver.find_element(By.ID, select_id))
                options = [(opt.text.strip(), opt.get_attribute("value")) 
                          for opt in sel.options[1:] if opt.get_attribute("value")]
                
                if options:
                    safe_print(f"[DROPDOWN] Found {len(options)} options in {select_id}")
                    return options
            except StaleElementReferenceException:
                safe_print(f"[DROPDOWN RETRY] Stale element for {select_id}, attempt {attempt}/{max_retries}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
            except Exception as e:
                safe_print(f"[DROPDOWN ERROR] Failed to get options for {select_id}: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
        return []
    
    def select_dropdown_safe(driver, select_id, value, max_retries=10):
        for attempt in range(1, max_retries + 1):
            try:
                WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.ID, select_id))
                )
                
                select_element = driver.find_element(By.ID, select_id)
                sel = Select(select_element)
                
                available_options = [opt.get_attribute("value") for opt in sel.options if opt.get_attribute("value")]
                
                if value not in available_options:
                    safe_print(f"[DROPDOWN WARN] Value '{value}' not found in {select_id} (attempt {attempt}/{max_retries})")
                    safe_print(f"[DROPDOWN INFO] Available values: {available_options[:5]}...")
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    return False
                
                sel.select_by_value(value)
                time.sleep(2)
                
                selected_value = sel.first_selected_option.get_attribute("value")
                if selected_value == value:
                    safe_print(f"[DROPDOWN SUCCESS] Selected '{value}' in {select_id}")
                    return True
                else:
                    safe_print(f"[DROPDOWN ERROR] Selection verification failed for {select_id}")
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                
            except (StaleElementReferenceException, TimeoutException, ElementNotInteractableException) as e:
                safe_print(f"[DROPDOWN RETRY] Attempt {attempt} for {select_id}: {e}")
                if attempt < max_retries:
                    time.sleep(3)
                    continue
            except Exception as e:
                safe_print(f"[DROPDOWN ERROR] {select_id}: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
        
        safe_print(f"[DROPDOWN ERROR] Failed to select '{value}' in {select_id} after {max_retries} attempts")
        return False
    
    def wait_for_dropdown_population(driver, dropdown_id, timeout=10):
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                WebDriverWait(driver, timeout).until(
                    lambda d: len(Select(d.find_element(By.ID, dropdown_id)).options) > 1
                )
                sel = Select(driver.find_element(By.ID, dropdown_id))
                safe_print(f"[INFO] Dropdown {dropdown_id} populated with {len(sel.options)} options")
                return True
            except TimeoutException:
                safe_print(f"[ERROR] Dropdown {dropdown_id} not populated within {timeout}s (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(2)
            except Exception as e:
                safe_print(f"[ERROR] Error waiting for {dropdown_id}: {e} (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(2)
        safe_print(f"[ERROR] Failed to wait for dropdown {dropdown_id} after {max_retries} attempts.")
        return False
    
    def reset_village_dropdown(driver, wait):
        try:
            village_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "ddlvillage")))
            driver.execute_script("arguments[0].selectedIndex = 0;", village_dropdown)
            time.sleep(2)
            
            if wait_for_dropdown_population(driver, "ddlvillage", timeout=30):
                safe_print("[VILLAGE RESET] Village dropdown reset successfully")
                return True
            return False
        except Exception as e:
            safe_print(f"[VILLAGE RESET ERROR] Failed to reset village dropdown: {e}")
            return False
    
    def get_fresh_village_options(driver, wait):
        try:
            if not reset_village_dropdown(driver, wait):
                safe_print("[VILLAGE ERROR] Failed to reset village dropdown")
                return []
            
            time.sleep(2)
            
            village_options = get_dropdown_options_safe(driver, "ddlvillage")
            safe_print(f"[VILLAGE REFRESH] Loaded {len(village_options)} fresh village options")
            
            return village_options
            
        except Exception as e:
            safe_print(f"[VILLAGE REFRESH ERROR] Failed to get fresh village options: {e}")
            return []
    
    def enter_gut_number(driver, wait, gut_no):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                gut_input = wait.until(EC.element_to_be_clickable((By.ID, "txtAttributeValue1")))
                driver.execute_script("arguments[0].scrollIntoView(true);", gut_input)
                
                driver.execute_script("arguments[0].value = '';", gut_input)
                time.sleep(1)
                gut_input.click()
                driver.execute_script(f"arguments[0].value = '{gut_no}';", gut_input)
                time.sleep(1)
                
                actual_value = driver.execute_script("return arguments[0].value;", gut_input)
                if str(actual_value).strip() == str(gut_no).strip():
                    safe_print(f"[GUT INPUT] Successfully entered gut number {gut_no}")
                    return True
                else:
                    safe_print(f"[GUT INPUT ERROR] Expected {gut_no}, but got {actual_value} (attempt {attempt}/{max_attempts})")
                    if attempt < max_attempts:
                        time.sleep(1)
                        
            except Exception as e:
                safe_print(f"[GUT INPUT ERROR] Failed to enter gut number {gut_no} (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    time.sleep(1)
        
        return False
    
    def wait_for_results(driver):
        try:
            WebDriverWait(driver, 60).until(
                lambda d: d.find_elements(By.ID, "RegistrationGrid") or d.find_elements(By.ID, "lblMsgCTS1")
            )
            
            if driver.find_elements(By.ID, "lblMsgCTS1"):
                return "NO_RECORDS"
            
            if driver.find_elements(By.ID, "RegistrationGrid"):
                try:
                    WebDriverWait(driver, 40).until(
                        lambda d: d.find_elements(By.XPATH, "//input[@value='IndexII']")
                    )
                except TimeoutException:
                    safe_print("[WARN] No IndexII buttons after table load")
                return "HAS_DATA"
            
            return "BLANK_PAGE"
        except TimeoutException:
            return "NO_LOAD"
        except Exception as e:
            safe_print(f"[RESULTS ERROR] Error waiting for results: {e}")
            return "ERROR"
    
    def save_html(html, meta, page, rec, suffix):
        try:
            if not html or len(html.strip()) == 0:
                safe_print(f"[SAVE ERROR] HTML content is empty for page {page}, record {rec}")
                return False
            
            village_safe = ''.join(c for c in meta['village'] if c.isalnum() or c in (' ', '_', '-')).replace(' ', '_')
            folder = os.path.join(OUTPUT_DIR, meta['year'], meta['district'], meta['tahsil'], village_safe)
            os.makedirs(folder, exist_ok=True)
            
            fn = f"{meta['year']}*{meta['district']}*{meta['tahsil']}*{village_safe}*{meta['property_no']}_p{page}_r{rec}_{suffix}.html"
            file_path = os.path.join(folder, fn)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            
            safe_print(f"[SAVED] {fn}")
            return True
            
        except Exception as e:
            safe_print(f"[SAVE ERROR] General error saving HTML for page {page}, record {rec}: {e}")
            return False
    
    def save_resume_point(meta, page_label, index2_done=0, index2_total=0, pending_action=None, ellipsis_info=None, last_page=None):
        """Save resume point for interrupted scraping"""
        vill = meta['village']
        gut_key = f"gut{meta['property_no']}"
        page_key = f"page{page_label}"
        
        RUN_STATUS.setdefault(vill, {}).setdefault(gut_key, {})
        RUN_STATUS[vill][gut_key].setdefault(page_key, {})
        
        RUN_STATUS[vill][gut_key][page_key]["index2_done"] = int(index2_done)
        RUN_STATUS[vill][gut_key][page_key]["index2_total"] = int(index2_total)
        RUN_STATUS[vill][gut_key][page_key]["completed"] = (index2_done >= index2_total and index2_total > 0)
        
        if pending_action is not None:
            RUN_STATUS[vill][gut_key][page_key]["pending_action"] = pending_action
        if ellipsis_info is not None:
            RUN_STATUS[vill][gut_key][page_key]["ellipsis_info"] = ellipsis_info
        if last_page is not None:
            RUN_STATUS[vill][gut_key][page_key]["last_page"] = str(last_page)
        
        RUN_STATUS[vill][gut_key][page_key]["timestamp"] = time.strftime('%Y-%m-%d %H:%M:%S')
        save_run_status()
    
    def clear_resume_point_for_page(meta, page_label):
        """Clear resume point for completed page"""
        vill = meta['village']
        gut_key = f"gut{meta['property_no']}"
        page_key = f"page{page_label}"
        
        try:
            if vill in RUN_STATUS and gut_key in RUN_STATUS[vill] and page_key in RUN_STATUS[vill][gut_key]:
                RUN_STATUS[vill][gut_key][page_key]["completed"] = True
                RUN_STATUS[vill][gut_key][page_key]["completion_time"] = time.strftime('%Y-%m-%d %H:%M:%S')
                save_run_status()
        except Exception as e:
            safe_print(f"[WARN] Could not clear resume point: {e}")
    
    def get_last_completed_page(meta):
        """Get the last successfully completed page for resume functionality"""
        vill = meta['village']
        gut_key = f"gut{meta['property_no']}"
        
        if vill not in RUN_STATUS or gut_key not in RUN_STATUS[vill]:
            return 0
        
        completed_pages = []
        for page_key, page_data in RUN_STATUS[vill][gut_key].items():
            if page_key.startswith("page") and page_data.get("completed", False):
                try:
                    page_num = int(page_key.replace("page", ""))
                    completed_pages.append(page_num)
                except ValueError:
                    continue
        
        return max(completed_pages) if completed_pages else 0
    
    def get_active_page_label(driver):
        """Get the current active page number"""
        try:
            selectors = [
                "//*[@id='RegistrationGrid']/tbody/tr[last()]/td/table/tbody/tr/td/span",
                "//span[contains(@class, 'current')]",
                "//td/span[not(@onclick)]",
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text.isdigit():
                            return text
                except:
                    continue
            
            return "1"
            
        except Exception as e:
            safe_print(f"[WARN] Error getting active page label: {e}")
            return "1"
    
    def get_pagination_info(driver):
        """Get comprehensive pagination information"""
        try:
            pagination_cells = driver.find_elements(By.XPATH, "//*[@id='RegistrationGrid']/tbody/tr[last()]/td/table/tbody/tr/td")
            
            if not pagination_cells:
                return {
                    "numeric_pages": [],
                    "ellipsis_positions": [],
                    "current_page": "1",
                    "has_ellipsis": False,
                    "has_forward_ellipsis": False,
                    "page_numbers": [],
                    "total_cells": 0
                }
            
            numeric_pages = []
            ellipsis_positions = []
            
            for i, cell in enumerate(pagination_cells, start=1):
                txt = cell.text.strip()
                if txt.isdigit():
                    numeric_pages.append((int(txt), i))
                elif txt == "...":
                    ellipsis_positions.append(i)
            
            current_page = get_active_page_label(driver)
            has_ellipsis = len(ellipsis_positions) > 0
            page_numbers = [p[0] for p in numeric_pages]
            
            has_forward_ellipsis = False
            if has_ellipsis and page_numbers:
                current_page_num = int(current_page) if current_page.isdigit() else 1
                max_visible_page = max(page_numbers)
                
                max_page_position = None
                for page_num, position in numeric_pages:
                    if page_num == max_visible_page:
                        max_page_position = position
                        break
                
                if max_page_position and ellipsis_positions:
                    for ellipsis_pos in ellipsis_positions:
                        if ellipsis_pos > max_page_position:
                            has_forward_ellipsis = True
                            break
            
            return {
                "numeric_pages": numeric_pages,
                "ellipsis_positions": ellipsis_positions,
                "current_page": current_page,
                "has_ellipsis": has_ellipsis,
                "has_forward_ellipsis": has_forward_ellipsis,
                "page_numbers": page_numbers,
                "total_cells": len(pagination_cells)
            }
            
        except Exception as e:
            safe_print(f"[ERROR] Getting pagination info: {e}")
            return {
                "numeric_pages": [],
                "ellipsis_positions": [],
                "current_page": get_active_page_label(driver),
                "has_ellipsis": False,
                "has_forward_ellipsis": False,
                "page_numbers": [],
                "total_cells": 0
            }
    
    def go_to_page(driver, wait, target_page, meta):
        """Navigate to specific page with automatic session reload on timeout"""
        if os.path.exists(STOP_FILE):
            return False
        
        safe_print(f"[NAVIGATE] Attempting to go to page {target_page}")
        
        current_page = get_active_page_label(driver)
        if current_page == target_page:
            safe_print(f"[NAVIGATE] Already on page {target_page}")
            return True
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                pagination_info = get_pagination_info(driver)
                page_numbers = pagination_info["page_numbers"]
                target_num = int(target_page)
                
                safe_print(f"[NAVIGATE DEBUG] Attempt {attempt + 1}: Current={pagination_info['current_page']}, Target={target_page}, Visible pages={page_numbers}")
                
                if target_num in page_numbers:
                    try:
                        page_link = driver.find_element(By.XPATH, f"//a[normalize-space()='{target_page}' and not(contains(@class, 'disabled'))]")
                        
                        driver, wait, click_result = safe_click_with_session_check(
                            driver, wait, page_link, "page_navigation", meta, current_page
                        )
                        
                        if click_result == "session_reloaded" or click_result == "session_recovered":
                            safe_print(f"[NAVIGATE] Session was reloaded, verifying page position")
                            actual_page = get_active_page_label(driver)
                            if actual_page == target_page:
                                safe_print(f"[NAVIGATE SUCCESS] Now on page {target_page} after session reload")
                                return True
                            else:
                                continue
                        
                        def page_loaded(d):
                            try:
                                return get_active_page_label(d) == target_page
                            except:
                                return False
                        
                        try:
                            WebDriverWait(driver, 30).until(page_loaded)
                        except TimeoutException:
                            safe_print(f"[NAVIGATE TIMEOUT] Page load timeout after clicking page {target_page}")
                            safe_print(f"[SESSION RELOAD] Restarting session due to page load timeout")
                            driver, wait = restart_and_resume(driver, wait, meta, current_page)
                            continue
                        
                        actual_page = get_active_page_label(driver)
                        if actual_page == target_page:
                            safe_print(f"[NAVIGATE SUCCESS] Now on page {target_page}")
                            time.sleep(2)
                            return True
                        else:
                            safe_print(f"[NAVIGATE] Page mismatch: expected {target_page}, got {actual_page}")
                            continue
                            
                    except NoSuchElementException:
                        safe_print(f"[NAVIGATE] Page link {target_page} not found or not clickable")
                        
                elif pagination_info["has_forward_ellipsis"] and target_num > max(page_numbers, default=0):
                    safe_print(f"[NAVIGATE] Page {target_page} not visible, clicking ellipsis")
                    
                    ellipsis_positions = pagination_info["ellipsis_positions"]
                    if ellipsis_positions:
                        max_ellipsis_pos = max(ellipsis_positions)
                        ellipsis_link = driver.find_element(By.XPATH, f"//*[@id='RegistrationGrid']/tbody/tr[last()]/td/table/tbody/tr/td[{max_ellipsis_pos}]/a")
                        
                        driver, wait, click_result = safe_click_with_session_check(
                            driver, wait, ellipsis_link, "ellipsis", meta, current_page
                        )
                        
                        if click_result == "session_reloaded" or click_result == "session_recovered":
                            safe_print(f"[NAVIGATE] Session was reloaded after ellipsis click")
                            continue
                        
                        time.sleep(4)
                        
                        new_current = get_active_page_label(driver)
                        if new_current == target_page:
                            safe_print(f"[NAVIGATE SUCCESS] Landed on target page {target_page} via ellipsis")
                            return True
                        elif int(new_current) > int(target_page):
                            safe_print(f"[NAVIGATE] Overshot to page {new_current}, trying to navigate to {target_page}")
                            continue
                        else:
                            continue
                else:
                    safe_print(f"[NAVIGATE] Page {target_page} not reachable from current position")
                    break
                    
            except Exception as e:
                safe_print(f"[NAVIGATE ERROR] Attempt {attempt + 1} failed: {e}")
                
                if isinstance(e, (WebDriverException, TimeoutException)):
                    safe_print(f"[SESSION EXPIRED] Detected session expiry during navigation")
                    if meta and current_page:
                        try:
                            driver, wait = restart_and_resume(driver, wait, meta, current_page)
                            continue
                        except Exception as restart_error:
                            safe_print(f"[RESTART ERROR] Failed to restart session: {restart_error}")
                            break
                
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                else:
                    break
        
        safe_print(f"[NAVIGATE FAIL] Failed to reach page {target_page} after {max_attempts} attempts")
        return False
    
    def click_next_page_button(driver, wait):
        """Click the Next/>> button to go to next page. Returns True if clicked, False if no next page."""
        try:
            pagination_xpath = "//*[@id='RegistrationGrid']/tbody/tr[last()]/td/table"
            pagination = driver.find_elements(By.XPATH, pagination_xpath)
            if not pagination:
                return False
            
            # Common Next button patterns: Next, >, >> (ASP.NET GridView style)
            next_selectors = [
                ".//a[normalize-space()='Next' and not(contains(@class, 'disabled'))]",
                ".//a[normalize-space()='>' and not(contains(@class, 'disabled'))]",
                ".//a[normalize-space()='>>' and not(contains(@class, 'disabled'))]",
                ".//a[contains(translate(normalize-space(), 'NEXT', 'next'), 'next') and not(contains(@class, 'disabled'))]",
            ]
            for selector in next_selectors:
                try:
                    next_links = pagination[0].find_elements(By.XPATH, selector)
                    for link in next_links:
                        if link.is_displayed() and link.is_enabled():
                            prev_page = get_active_page_label(driver)
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
                            time.sleep(0.5)
                            link.click()
                            time.sleep(2)
                            new_page = get_active_page_label(driver)
                            if new_page != prev_page or int(new_page) > int(prev_page):
                                safe_print(f"[PAGINATION] Clicked Next: page {prev_page} -> {new_page}")
                                return True
                except Exception:
                    continue
            return False
        except Exception as e:
            safe_print(f"[PAGINATION] Next button click failed: {e}")
            return False
    
    def restart_and_resume(driver, wait, meta, target_page, retry_count=0):
        """Restart browser session and resume from specific page"""
        if os.path.exists(STOP_FILE):
            return driver, wait
        
        safe_print(f"[RESTART] Restarting browser session for page {target_page} (Retry {retry_count}/3)")
        
        try:
            terminate_driver_safely(driver)
            
            driver, wait = safe_browser_restart()
            
            try:
                if not safe_get_url(driver, WEBSITE_URL):
                    raise RuntimeError("Failed to load website after restart")
                    
                driver, wait = close_popup_and_click_rest(driver, wait)
                
                Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(meta['year'])
                select_dropdown_safe(driver, "ddlDistrict1", meta['d_val'])
                wait_for_dropdown_population(driver, "ddltahsil")
                select_dropdown_safe(driver, "ddltahsil", meta['t_val'])
                wait_for_dropdown_population(driver, "ddlvillage")
                select_dropdown_safe(driver, "ddlvillage", meta['v_val'])
                
                if not enter_gut_number(driver, wait, meta['property_no']):
                    raise RuntimeError(f"Failed to enter gut number {meta['property_no']}")
                
                # For fresh session, we need to do dummy captcha submission first
                captcha_elem = submit_dummy_captcha(driver, wait, safe_print)
                if captcha_elem is None:
                    raise RuntimeError("Failed to submit dummy captcha")
                
                captcha_success = solve_captcha_with_api_and_submit(driver, wait, safe_print, CAPTCHA_IMAGE_PATH)
                if not captcha_success:
                    raise RuntimeError(f"Failed to solve captcha for gut {meta['property_no']}")
                
                status = wait_for_results(driver)
                if status != "HAS_DATA":
                    raise RuntimeError(f"No data found after resuming, status: {status}")
                
                if target_page != "1":
                    safe_print(f"[RESUME] Navigating to target page {target_page}")
                    if not go_to_page(driver, wait, str(target_page), meta):
                        raise RuntimeError(f"Failed to navigate to page {target_page}")
                
                try:
                    WebDriverWait(driver, 30).until(
                        lambda d: d.find_elements(By.XPATH, "//input[@value='IndexII']")
                    )
                    safe_print(f"[RESUME SUCCESS] Successfully resumed at page {target_page}")
                except TimeoutException:
                    raise RuntimeError(f"No IndexII buttons found on page {target_page}")
                
                return driver, wait
                
            except Exception as e:
                if retry_count < 3:
                    safe_print(f"[RETRY] Resume failed: {e}. Retrying...")
                    terminate_driver_safely(driver)
                    return restart_and_resume(driver, wait, meta, target_page, retry_count + 1)
                else:
                    safe_print(f"[CRITICAL] Resume failed after retries: {e}")
                    log_failed(meta['year'], meta['district'], meta['tahsil'], meta['village'], meta['property_no'], target_page)
                    raise RuntimeError(f"Resume failed for gut {meta['property_no']} page {target_page}")
                    
        except Exception as e:
            if retry_count < 3:
                safe_print(f"[RETRY] Resume failed: {e}. Retrying...")
                return restart_and_resume(driver, wait, meta, target_page, retry_count + 1)
            else:
                safe_print(f"[CRITICAL] Resume failed after retries: {e}")
                log_failed(meta['year'], meta['district'], meta['tahsil'], meta['village'], meta['property_no'], target_page)
                raise RuntimeError(f"Resume failed for gut {meta['property_no']} page {target_page}")
    
    def is_button_clickable_and_active(driver, element, element_type="button", wait_time=5):
        """Enhanced check for button state with better session expiry detection"""
        try:
            if element_type in ["page_navigation", "ellipsis"]:
                safe_print(f"[BUTTON CHECK] Waiting {wait_time}s for {element_type} to stabilize...")
                time.sleep(wait_time)
            
            try:
                if element_type == "page_navigation":
                    page_text = element.text.strip()
                    if page_text.isdigit():
                        fresh_element = driver.find_element(By.XPATH, f"//a[normalize-space()='{page_text}' and not(contains(@class, 'disabled'))]")
                    else:
                        fresh_element = element
                else:
                    fresh_element = element
            except:
                fresh_element = element
            
            if not fresh_element.is_displayed():
                safe_print(f"[BUTTON CHECK] {element_type} not displayed")
                return False
            
            if not fresh_element.is_enabled():
                safe_print(f"[BUTTON CHECK] {element_type} not enabled")
                return False
            
            classes = fresh_element.get_attribute("class") or ""
            if "disabled" in classes.lower() or "inactive" in classes.lower():
                safe_print(f"[BUTTON CHECK] {element_type} has disabled class: {classes}")
                return False
            
            if element_type in ["page_navigation", "ellipsis"]:
                onclick = fresh_element.get_attribute("onclick") or ""
                href = fresh_element.get_attribute("href") or ""
                
                if fresh_element.tag_name == "a" and not onclick.strip() and not href.strip():
                    safe_print(f"[BUTTON CHECK] {element_type} link has no onclick or href")
                    return False
                
                try:
                    driver.execute_script("return document.readyState;")
                    
                    reg_grid = driver.find_element(By.ID, "RegistrationGrid")
                    if not reg_grid.is_displayed():
                        safe_print(f"[BUTTON CHECK] Registration grid not visible - session may have expired")
                        return False
                        
                except (NoSuchElementException, WebDriverException):
                    safe_print(f"[BUTTON CHECK] Page appears unresponsive - session may have expired")
                    return False
            
            if element_type == "IndexII":
                try:
                    reg_grid = driver.find_element(By.ID, "RegistrationGrid")
                    if not reg_grid.is_displayed():
                        safe_print(f"[BUTTON CHECK] Registration grid not visible")
                        return False
                except NoSuchElementException:
                    safe_print(f"[BUTTON CHECK] Registration grid not found")
                    return False
            
            safe_print(f"[BUTTON CHECK] {element_type} appears to be active and clickable")
            return True
            
        except Exception as e:
            safe_print(f"[BUTTON CHECK] Error checking {element_type} button state: {e}")
            return False
    
    def safe_click_with_session_check(driver, wait, element, element_type, meta, current_page=None):
        """Safely click element with session expiry detection and recovery"""
        try:
            max_check_attempts = 2
            button_is_active = False
            
            for check_attempt in range(max_check_attempts):
                wait_time = 5 if element_type in ["page_navigation", "ellipsis"] else 1
                if is_button_clickable_and_active(driver, element, element_type, wait_time):
                    button_is_active = True
                    break
                else:
                    if check_attempt < max_check_attempts - 1:
                        safe_print(f"[BUTTON CHECK] {element_type} check attempt {check_attempt + 1} failed, retrying...")
                        time.sleep(2)
            
            if not button_is_active:
                safe_print(f"[SESSION EXPIRED] {element_type} button is inactive/disabled after {max_check_attempts} attempts - session likely expired")
                
                if current_page and meta:
                    safe_print(f"[STATUS SAVE] Saving status before session reload for page {current_page}")
                    try:
                        buttons = driver.find_elements(By.XPATH, "//input[@value='IndexII']")
                        index2_done = 0
                        save_resume_point(meta, current_page, index2_done, len(buttons), 
                                        pending_action=f"retry_{element_type}_click")
                    except:
                        pass
                
                safe_print(f"[SESSION RELOAD] Restarting session due to inactive {element_type} button")
                if meta and current_page:
                    driver, wait = restart_and_resume(driver, wait, meta, current_page)
                    return driver, wait, "session_reloaded"
                else:
                    terminate_driver_safely(driver)
                    driver, wait = safe_browser_restart()
                    return driver, wait, "session_reloaded"
            
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            time.sleep(0.5)
            element.click()
            return driver, wait, "clicked"
            
        except (TimeoutException, StaleElementReferenceException, WebDriverException) as e:
            safe_print(f"[CLICK ERROR] Failed to click {element_type}: {e}")
            
            if current_page and meta and "session_reloaded" not in str(e):
                safe_print(f"[SESSION RECOVERY] Attempting session recovery after click failure")
                try:
                    driver, wait = restart_and_resume(driver, wait, meta, current_page)
                    return driver, wait, "session_recovered"
                except Exception as recovery_error:
                    safe_print(f"[RECOVERY ERROR] Failed to recover session: {recovery_error}")
                    raise e
            
            raise e
    
    def validate_page_content(driver, expected_page):
        """Validate that we're on the correct page with proper content"""
        try:
            actual_page = get_active_page_label(driver)
            if actual_page != expected_page:
                safe_print(f"[VALIDATION] Page mismatch: expected {expected_page}, got {actual_page}")
                return False
            
            buttons = driver.find_elements(By.XPATH, "//input[@value='IndexII']")
            if not buttons:
                safe_print(f"[VALIDATION] No IndexII buttons found on page {expected_page}")
                return False
            
            safe_print(f"[VALIDATION] Page {expected_page} validated successfully with {len(buttons)} IndexII buttons")
            return True
        except Exception as e:
            safe_print(f"[VALIDATION ERROR] Failed to validate page {expected_page}: {e}")
            return False
    
    def process_indexii_buttons(driver, wait, initial_buttons, meta, page_label, suffix):
        saved_count = 0
        main_window = driver.current_window_handle
        total_buttons = len(initial_buttons)
        seen_docs = meta.get('seen_docs_dict', {})
        
        for idx in range(1, total_buttons + 1):
            try:
                safe_print(f"[PROCESSING] IndexII {idx}/{total_buttons} on page {page_label}")
                
                if idx > 1:
                    try:
                        time.sleep(0.5)
                        buttons = driver.find_elements(By.XPATH, "//input[@value='IndexII']")
                        if not buttons or len(buttons) < idx:
                            safe_print(f"[INDEXII WARN] Could not find IndexII button {idx}, only {len(buttons) if buttons else 0} buttons available")
                            break
                    except Exception as e:
                        safe_print(f"[INDEXII ERROR] Failed to re-locate buttons: {e}")
                        break
                
                if idx == 1:
                    button = initial_buttons[idx-1]
                else:
                    button = buttons[idx-1]

                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
                time.sleep(0.5)
                button.click()
                safe_print(f"[INFO] Clicked IndexII button {idx}")
                
                WebDriverWait(driver, POPUP_TIMEOUT).until(EC.number_of_windows_to_be(2))
                
                new_windows = [w for w in driver.window_handles if w != main_window]
                if not new_windows:
                    raise TimeoutException("No new window opened")
                
                driver.switch_to.window(new_windows[0])
                safe_print(f"[INFO] Switched to IndexII popup window")
                
                WebDriverWait(driver, POPUP_TIMEOUT).until(
                    lambda d: d.execute_script("return document.readyState;") == "complete"
                )
                time.sleep(1)
                
                html_content = driver.page_source
                
                # Deduplication by exact HTML content match (per village)
                content_hash = hashlib.sha256(html_content.encode('utf-8')).hexdigest()
                village_hash = _village_hash(meta)
                village_seen = seen_docs.get(village_hash, set())
                if content_hash in village_seen:
                    safe_print(f"[DEDUPLICATE] Skipping - HTML content exactly matches already downloaded doc in this village (row {idx})")
                    driver.close()
                    driver.switch_to.window(main_window)
                    continue
                
                if save_html(html_content, meta, page_label, idx, suffix):
                    village_seen.add(content_hash)
                    seen_docs[village_hash] = village_seen
                    add_seen_doc(village_hash, content_hash)
                    saved_count += 1
                    global_counter["total_records"] += 1
                    safe_print(f"[SUCCESS] Saved record {idx} on page {page_label}")
                
                driver.close()
                driver.switch_to.window(main_window)
                safe_print(f"[INFO] Closed popup and returned to main window")
                
            except Exception as e:
                safe_print(f"[INDEXII ERROR] Failed to process record {idx}: {e}")
                
                try:
                    for window in driver.window_handles:
                        if window != main_window:
                            driver.switch_to.window(window)
                            driver.close()
                    driver.switch_to.window(main_window)
                except:
                    pass
        
        safe_print(f"[INDEXII COMPLETE] Processed {saved_count}/{total_buttons} records on page {page_label}")
        return saved_count
    
    def process_single_page_data(driver, wait, meta, suffix):
        safe_print("[SINGLE PAGE] Processing page without pagination")
        
        try:
            WebDriverWait(driver, 40).until(
                lambda d: d.find_elements(By.XPATH, "//input[@value='IndexII']")
            )
            
            buttons = driver.find_elements(By.XPATH, "//input[@value='IndexII']")
            if not buttons:
                safe_print("[SINGLE PAGE] No IndexII buttons found")
                return 0
            
            safe_print(f"[SINGLE PAGE] Found {len(buttons)} IndexII buttons")
            return process_indexii_buttons(driver, wait, buttons, meta, "1", suffix)
            
        except TimeoutException:
            safe_print("[SINGLE PAGE] No IndexII buttons found within timeout")
            return 0
    
    def process_paginated_data(driver, wait, meta, suffix):
        total_saved = 0
        current_page = 1
        max_pages = 1000
        
        # Get the initial page number
        current_page_label = get_active_page_label(driver)
        safe_print(f"[PAGINATION] Starting on page {current_page_label}")
        
        while current_page <= max_pages:
            safe_print(f"[PAGE {current_page}] Processing page {current_page}")
            
            try:
                # Wait for IndexII buttons to be present
                WebDriverWait(driver, 30).until(
                    lambda d: d.find_elements(By.XPATH, "//input[@value='IndexII']")
                )
                buttons = driver.find_elements(By.XPATH, "//input[@value='IndexII']")
            except TimeoutException:
                safe_print(f"[PAGE {current_page}] No IndexII buttons found")
                break
                
            # Process the current page
            saved_count = process_indexii_buttons(driver, wait, buttons, meta, str(current_page), suffix)
            total_saved += saved_count
            safe_print(f"[PAGE {current_page}] Completed - saved {saved_count} records")
            
            # Check if we should stop
            if os.path.exists(STOP_FILE):
                safe_print("[STOP] Stop file detected, stopping pagination")
                break
                
            # Try to navigate to the next page (page number first, then Next button)
            next_page = current_page + 1
            safe_print(f"[PAGINATION] Attempting to navigate to page {next_page}")
            
            navigated = go_to_page(driver, wait, str(next_page), meta)
            if not navigated:
                safe_print(f"[PAGINATION] Page number nav failed, trying Next button...")
                navigated = click_next_page_button(driver, wait)
            
            if navigated:
                time.sleep(2)  # Allow page to load after navigation
            
            if not navigated:
                safe_print(f"[PAGINATION] No more pages (reached end of pagination)")
                break
            
            # Get actual page and validate (retry with new instance if session died)
            try:
                if not is_browser_alive(driver):
                    safe_print("[PAGINATION] Session dead during navigation, restarting and resuming...")
                    driver, wait = restart_and_resume(driver, wait, meta, str(next_page))
                actual_page = get_active_page_label(driver)
                current_page = int(actual_page) if actual_page.isdigit() else next_page
                if not validate_page_content(driver, str(current_page)):
                    safe_print(f"[PAGINATION] Page {current_page} has no IndexII content, stopping")
                    break
            except Exception as val_err:
                if is_session_dead_error(val_err):
                    safe_print(f"[PAGINATION] Session expired during validation, restarting and resuming: {val_err}")
                    try:
                        driver, wait = restart_and_resume(driver, wait, meta, str(next_page))
                        current_page = next_page
                        time.sleep(2)
                    except Exception as restart_err:
                        safe_print(f"[PAGINATION] Restart failed: {restart_err}")
                        break
                else:
                    raise
        
        safe_print(f"[SCRAPE COMPLETE] Gut {meta['property_no']}: {current_page} pages processed, {total_saved} records saved")
        return total_saved
    
    def scrape_all_pages_for_gut(driver, wait, meta, suffix):
        safe_print(f"[SCRAPE] Starting comprehensive scraping for gut {meta['property_no']}")
        
        try:
            # Check if pagination exists
            pagination_table = driver.find_elements(By.XPATH, "//*[@id='RegistrationGrid']/tbody/tr[last()]/td/table")
            if not pagination_table:
                safe_print("[PAGINATION] No pagination table found, processing as single page")
                return process_single_page_data(driver, wait, meta, suffix)
            
            # Process with pagination
            return process_paginated_data(driver, wait, meta, suffix)
        except Exception as e:
            safe_print(f"[SCRAPE ERROR] Error in scraping: {e}")
            return 0
    
    def process_gut_with_recovery(driver, wait, meta, suffix):
        gut_no = meta['property_no']
        for attempt in range(1, MAX_SESSION_RETRY + 1):
            try:
                safe_print(f"[GUT {gut_no}] Processing gut {gut_no} (attempt {attempt}/{MAX_SESSION_RETRY})")
                
                if not is_browser_alive(driver):
                    safe_print("[GUT ERROR] Browser session lost, restarting...")
                    terminate_driver_safely(driver)
                    driver, wait = safe_browser_restart()
                
                # Check if we are already on the correct page and the form is visible
                needs_full_reload = True
                try:
                    if "freesearchigrservice" in driver.current_url.lower():
                        village_dropdown = driver.find_element(By.ID, "ddlvillage")
                        if village_dropdown.is_displayed():
                            needs_full_reload = False
                except:
                    pass
                
                if needs_full_reload:
                    safe_print(f"[GUT {gut_no}] Form not ready, performing full reload...")
                    if not safe_get_url(driver, WEBSITE_URL):
                        safe_print(f"[GUT ERROR] Failed to load website (attempt {attempt})")
                        if attempt < MAX_SESSION_RETRY:
                            terminate_driver_safely(driver)
                            driver, wait = safe_browser_restart()
                            continue
                        return 0
                    
                    driver, wait = close_popup_and_click_rest(driver, wait)
                    
                    Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(meta['year'])
                    select_dropdown_safe(driver, "ddlDistrict1", meta['d_val'])
                    wait_for_dropdown_population(driver, "ddltahsil")
                    select_dropdown_safe(driver, "ddltahsil", meta['t_val'])
                    reset_village_dropdown(driver, wait)
                    select_dropdown_safe(driver, "ddlvillage", meta['v_val'])
                else:
                    # Just ensure the correct village is selected and form is clear
                    try:
                        # If there's a "Clear" or "Back" button, click it, but usually re-selecting village is enough
                        select_dropdown_safe(driver, "ddlvillage", meta['v_val'])
                    except:
                        pass
                
                if not enter_gut_number(driver, wait, gut_no):
                    safe_print(f"[GUT ERROR] Failed to enter gut number {gut_no}")
                    if attempt < MAX_SESSION_RETRY:
                        continue
                    log_message("ERROR", "GUT_INPUT", f"Failed to enter gut number {gut_no}", meta)
                    return 0
                
                # Submit dummy captcha first to trigger actual captcha
                captcha_elem = submit_dummy_captcha(driver, wait, safe_print)
                if captcha_elem is None:
                    safe_print(f"[GUT ERROR] Failed to submit dummy captcha for gut {gut_no}")
                    if attempt < MAX_SESSION_RETRY:
                        continue
                    log_message("ERROR", "DUMMY_CAPTCHA", f"Failed to submit dummy captcha for gut {gut_no}", meta)
                    return 0
                
                # Now solve the actual captcha
                captcha_success = solve_captcha_with_api_and_submit(driver, wait, safe_print, CAPTCHA_IMAGE_PATH)
                if not captcha_success:
                    safe_print(f"[GUT ERROR] Captcha failed for gut {gut_no}")
                    if attempt < MAX_SESSION_RETRY:
                        continue
                    log_message("ERROR", "CAPTCHA", f"Captcha failed for gut {gut_no}", meta)
                    return 0
                
                result_status = wait_for_results(driver)
                safe_print(f"[GUT {gut_no}] Search result: {result_status}")
                
                if result_status == "HAS_DATA":
                    saved_count = scrape_all_pages_for_gut(driver, wait, meta, suffix)
                    safe_print(f"[GUT {gut_no}] Successfully scraped {saved_count} records")
                    log_message("INFO", "SUCCESS", f"Scraped {saved_count} records for gut {gut_no}", meta)
                    global_counter["total_records"] += saved_count
                    return saved_count
                elif result_status == "NO_RECORDS":
                    safe_print(f"[GUT {gut_no}] No records found")
                    log_message("INFO", "NO_RECORDS", f"No records found for gut {gut_no}", meta)
                    return 0
                else:
                    safe_print(f"[GUT {gut_no}] Special case: {result_status}")
                    log_special(meta['year'], meta['district'], meta['tahsil'], meta['village'], gut_no)
                    log_message("WARN", "SPECIAL_CASE", f"Special case: {result_status} for gut {gut_no}", meta)
                    return 0
                    
            except (NoSuchWindowException, WebDriverException) as e:
                safe_print(f"[GUT ERROR] Browser error processing gut {gut_no} (attempt {attempt}): {e}")
                if attempt < MAX_SESSION_RETRY:
                    terminate_driver_safely(driver)
                    driver, wait = safe_browser_restart()
                    continue
            except Exception as e:
                safe_print(f"[GUT ERROR] General error processing gut {gut_no} (attempt {attempt}): {e}")
                if attempt < MAX_SESSION_RETRY:
                    time.sleep(2)
                    continue
        
        safe_print(f"[GUT ERROR] Failed to process gut {gut_no} after {MAX_SESSION_RETRY} attempts")
        log_failed(meta['year'], meta['district'], meta['tahsil'], meta['village'], gut_no)
        log_message("ERROR", "FAILED", f"Failed to process gut {gut_no} after {MAX_SESSION_RETRY} attempts", meta)
        return 0
    
    # Main processing loop
    RUN_STATUS = load_run_status()
    progress = load_progress()
    seen_docs_dict = load_seen_docs()
    html_count = 0
    suffix = str(int(time.time() * 1000))
    
    safe_print("=== MILITARY GRADE WEB SCRAPER STARTED ===")
    if VPS_MODE:
        safe_print("[INFO] VPS mode: headless, no GUI required")
    elif HEADLESS_MODE:
        safe_print("[INFO] Running in headless mode")
    else:
        safe_print("[INFO] Browser will open in visible mode for terminal monitoring")
    safe_print(f"[INFO] Create file at {STOP_FILE} to stop gracefully")
    
    driver, wait = safe_browser_restart()
    
    try:
        if not safe_get_url(driver, WEBSITE_URL):
            raise RuntimeError("Failed to load website on initial attempt")
            
        driver, wait = close_popup_and_click_rest(driver, wait)
        Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(year)
        
        district_options = get_dropdown_options_safe(driver, "ddlDistrict1")
        safe_print(f"[INFO] Found {len(district_options)} districts to process")
        safe_print("[TEST] Processing 1st district only")
        
        for d_name, d_val in district_options[:1]:
            if os.path.exists(STOP_FILE):
                break
            safe_print(f"\n[DISTRICT] Processing {d_name}")
            
            if not select_dropdown_safe(driver, "ddlDistrict1", d_val):
                safe_print(f"[ERROR] Failed to select district {d_name}, skipping")
                continue
                
            if not wait_for_dropdown_population(driver, "ddltahsil"):
                safe_print(f"[ERROR] Tahsil dropdown not populated for district {d_name}")
                continue
                
            tahsil_options = get_dropdown_options_safe(driver, "ddltahsil")
            safe_print(f"[INFO] Found {len(tahsil_options)} tahsils in district {d_name}")
            safe_print("[TEST] Processing 1st tehsil only")
            
            for t_name, t_val in tahsil_options[:1]:
                if os.path.exists(STOP_FILE):
                    break
                safe_print(f"[TAHSIL] Processing {t_name}")
                
                if not select_dropdown_safe(driver, "ddltahsil", t_val):
                    safe_print(f"[ERROR] Failed to select tahsil {t_name}, skipping")
                    continue
                    
                village_options = get_fresh_village_options(driver, wait)
                if not village_options:
                    safe_print(f"[ERROR] No villages found for tahsil {t_name}")
                    continue
                safe_print(f"[INFO] Found {len(village_options)} villages in tahsil {t_name}")
                if len(village_options) < 15:
                    safe_print(f"[ERROR] Tahsil has only {len(village_options)} villages, need 15th. Skipping.")
                    continue
                safe_print("[TEST] Processing 15th village only")
                
                for v_name, v_val in village_options[14:15]:
                    if os.path.exists(STOP_FILE):
                        break
                    safe_print(f"[VILLAGE] Processing {v_name}")
                    
                    key = f"{year}|{d_name}|{t_name}"
                    progress.setdefault(key, {})
                    last_gut = progress[key].get(v_name, -1)
                    if last_gut >= 20:
                        safe_print(f"[VILLAGE {v_name}] Already complete (last_gut={last_gut}), skipping")
                        continue
                        
                    if not select_dropdown_safe(driver, "ddlvillage", v_val):
                        safe_print(f"[ERROR] Failed to select village {v_name}, skipping")
                        log_village_mismatch(d_name, t_name, v_name, 
                                           [opt[0] for opt in get_dropdown_options_safe(driver, "ddlvillage")])
                        continue
                    
                    for gut_no in range(max(1, int(last_gut) + 1), 21):
                        if os.path.exists(STOP_FILE):
                            break
                        safe_print(f"\n[GUT {gut_no}] Processing gut {gut_no} in village {v_name}")
                        
                        meta = {
                            'year': year,
                            'district': d_name,
                            'tahsil': t_name,
                            'village': v_name,
                            'property_no': str(gut_no),
                            'd_val': d_val,
                            't_val': t_val,
                            'v_val': v_val,
                            'seen_docs_dict': seen_docs_dict
                        }
                        
                        saved_count = process_gut_with_recovery(driver, wait, meta, suffix)
                        html_count += saved_count
                        progress[key][v_name] = gut_no
                        save_progress(progress)
                        
                        # Refresh website and re-enter details for next property (retry with new instance on session death)
                        if gut_no < 20:
                            refresh_ok = False
                            for refresh_attempt in range(MAX_SESSION_RETRY):
                                if not is_browser_alive(driver):
                                    safe_print(f"[REFRESH] Session dead, restarting browser (attempt {refresh_attempt + 1}/{MAX_SESSION_RETRY})...")
                                    terminate_driver_safely(driver)
                                    driver, wait = safe_browser_restart()
                                try:
                                    safe_print(f"[GUT {gut_no}] Refreshing website and re-entering details for next property...")
                                    if not safe_get_url(driver, WEBSITE_URL):
                                        raise RuntimeError("URL load failed")
                                    driver, wait = close_popup_and_click_rest(driver, wait)
                                    Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(year)
                                    select_dropdown_safe(driver, "ddlDistrict1", d_val)
                                    wait_for_dropdown_population(driver, "ddltahsil")
                                    select_dropdown_safe(driver, "ddltahsil", t_val)
                                    reset_village_dropdown(driver, wait)
                                    select_dropdown_safe(driver, "ddlvillage", v_val)
                                    refresh_ok = True
                                    break
                                except Exception as refresh_err:
                                    if refresh_attempt < MAX_SESSION_RETRY - 1:
                                        safe_print(f"[REFRESH] Error, restarting session and retrying ({refresh_attempt + 1}/{MAX_SESSION_RETRY}): {refresh_err}")
                                        terminate_driver_safely(driver)
                                        driver, wait = safe_browser_restart()
                                    else:
                                        safe_print(f"[ERROR] Failed to refresh website after property: {refresh_err}")
                                        break
                            if not refresh_ok:
                                break
                    
                    progress[key][v_name] = 20
                    save_progress(progress)
                    safe_print(f"[VILLAGE {v_name}] Processing complete")
                    # Play village completion sound
                    play_village_complete_sound()
                    
                    # Completely restart browser session after each village
                    terminate_driver_safely(driver)
                    driver, wait = safe_browser_restart()
                    
                    if not safe_get_url(driver, WEBSITE_URL):
                        safe_print("[ERROR] Failed to reload website after village completion")
                        raise RuntimeError("Failed to reload website after village completion")
                    driver, wait = close_popup_and_click_rest(driver, wait)
                    Select(driver.find_element(By.ID, "ddlFromYear1")).select_by_visible_text(year)
                    select_dropdown_safe(driver, "ddlDistrict1", d_val)
                    wait_for_dropdown_population(driver, "ddltahsil")
                    select_dropdown_safe(driver, "ddltahsil", t_val)
                    if not wait_for_dropdown_population(driver, "ddlvillage"):
                        safe_print(f"[ERROR] Village dropdown not populated after selecting tahsil {t_name}")
                        break
                    village_options = get_fresh_village_options(driver, wait)
                    if not village_options:
                        safe_print(f"[ERROR] No villages found for tahsil {t_name} after refresh")
                        break
    
    except Exception as e:
        safe_print(f"[MAIN ERROR] Critical error in main loop: {e}")
        traceback.print_exc()
        log_message("ERROR", "MAIN_LOOP", "Critical error in main processing", {
            "error": str(e),
            "stack_trace": traceback.format_exc()
        })
    finally:
        terminate_driver_safely(driver)
        
        final_summary = {
            "html_files": html_count,
            "total_records": global_counter["total_records"],
            "completion_time": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        safe_print("[FINAL] Scraping completed:")
        safe_print(f"  - HTML files saved: {html_count}")
        safe_print(f"  - Total records: {global_counter['total_records']}")
        
        log_message("INFO", "COMPLETE", f"Scraping session completed for year {year}", final_summary)
        save_run_status()
        play_alert_sound()
        play_year_complete_sound()  # Play special sound when year is completed

def run_years_in_batches(years_to_scrape, max_concurrent):
    """Run scraper for multiple years in batches to avoid resource exhaustion"""
    # Set window dimensions (only used in non-headless mode)
    window_width = 1920
    window_height = 1080
    
    print(f"Starting MILITARY GRADE multi-year scraper in batches of {max_concurrent}...")
    print(f"Will scrape years: {years_to_scrape}")
    print(f"Logging type: {LOGGING_TYPE}")
    
    print(f"Create a file at {os.path.join(os.path.expanduser('~/Documents'), 'stop_script.txt')} to stop all scrapers gracefully")
    
    if HEADLESS_MODE or VPS_MODE:
        print("Running in headless mode - no browser windows, no GUI required")
        if VPS_MODE:
            print("VPS mode: optimized for server/headless environment")
    else:
        if pyautogui:
            try:
                print(f"Screen size: {pyautogui.size()}")
            except Exception:
                pass
        print(f"Window size: {window_width}x{window_height}")
        print("Windows will be positioned on left and right halves of the screen")
    
    # Print color legend for terminal output
    print("\nTerminal Output Color Legend:")
    for year in years_to_scrape:
        color = YEAR_COLORS.get(year, Colors.WHITE)
        print(f"{color}Year {year}{Colors.ENDC}")
    
    # Split years into batches
    batches = [years_to_scrape[i:i + max_concurrent] for i in range(0, len(years_to_scrape), max_concurrent)]
    
    for batch_num, batch in enumerate(batches, 1):
        print(f"\n{'='*50}")
        print(f"Processing batch {batch_num}/{len(batches)}: {batch}")
        print(f"{'='*50}")
        
        # Create processes for each year in the current batch
        processes = []
        for i, year in enumerate(batch):
            # Position windows side by side (only used in non-headless mode)
            x_position = i * (window_width + 20)
            window_position = (x_position, 0, window_width, window_height)
            
            p = multiprocessing.Process(
                target=run_scraper_for_year,
                args=(year, window_position)
            )
            processes.append(p)
            p.start()
            print(f"Started scraper process for year {year}")
        
        # Wait for all processes in the current batch to complete
        for p in processes:
            p.join()
        
        print(f"Batch {batch_num}/{len(batches)} completed")
        
        # Check if stop file was created
        stop_file = os.path.join(os.path.expanduser("~/Documents"), "stop_script.txt")
        if os.path.exists(stop_file):
            print("Stop file detected, stopping remaining batches")
            os.remove(stop_file)  # Remove stop file for future runs
            break
        
        # Add a small delay between batches to reduce system load
        if batch_num < len(batches):
            print("Taking a short break between batches...")
            time.sleep(10)
    
    print("All scrapers have completed")

def main():
    """Main function - TEST: 2026 only, 1 district, 1 tehsil, 15th village, properties 1-20"""
    years_to_scrape = ["2026"]
    print("[TEST] Running test script: year 2026, 1st district, 1st tehsil, 15th village, properties 1-20")
    
    run_years_in_batches(years_to_scrape, MAX_CONCURRENT_PROCESSES)

if __name__ == "__main__":
    main()