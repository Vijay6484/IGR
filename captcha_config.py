"""
Common CAPTCHA API configuration for 5.py, 6.py, 7.py, 8.py
Change the API key and URLs here; all scripts will use these values.
"""

# Capsolver API - replace with your key
CAPTCHA_API_KEY = "CAP-03DD9281E150148DCB0705A6F665CF337303C5FDC399749D977BEAC6CD398191"

# API endpoints (usually no need to change)
CAPTCHA_API_URL = "https://api.capsolver.com/createTask"
CAPTCHA_RESULT_URL = "https://api.capsolver.com/getTaskResult"

# Max seconds to wait for captcha image to load
MAX_CAPTCHA_WAIT = 80
