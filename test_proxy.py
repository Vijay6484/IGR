import requests
try:
    r = requests.get("https://freesearchigrservice.maharashtra.gov.in/", timeout=10)
    print(r.status_code)
except Exception as e:
    print(e)
