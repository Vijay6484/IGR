import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

url = "https://freesearchigrservice.maharashtra.gov.in"
session = requests.Session()

# Important headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded"
}

res = session.get(url, verify=False, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

inputs = soup.find_all("input")
payload = {}
for i in inputs:
    if i.get("name"):
        payload[i.get("name")] = i.get("value", "")

payload['__EVENTTARGET'] = 'ddlDistrict1'
payload['__EVENTARGUMENT'] = ''
payload['ddlFromYear1'] = '2022'
payload['ddlDistrict1'] = '31'

res2 = session.post(url, data=payload, verify=False, headers=headers)
print("Select not found. Length of response:", len(res2.text))
with open("test2.html", "w") as f:
    f.write(res2.text)
