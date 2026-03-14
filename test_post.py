import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

url = "https://freesearchigrservice.maharashtra.gov.in"
session = requests.Session()

# 1. First get the page to acquire initial __VIEWSTATE
res = session.get(url, verify=False)
soup = BeautifulSoup(res.text, "html.parser")

viewstate = soup.find("input", id="__VIEWSTATE").get("value")
eventval = soup.find("input", id="__EVENTVALIDATION").get("value")
vsg = soup.find("input", id="__VIEWSTATEGENERATOR").get("value")

print("Got initial state")

# 2. Simulate District Dropdown Change
# According to script, user selects Year first?
# ddlFromYear1: '2022'
# ddlDistrict1 is District

payload = {
    '__EVENTTARGET': 'ddlDistrict1',
    '__EVENTARGUMENT': '',
    '__VIEWSTATE': viewstate,
    '__VIEWSTATEGENERATOR': vsg,
    '__EVENTVALIDATION': eventval,
    'ddlFromYear1': '2022',
    'ddlDistrict1': '31' # Pune (just an example district ID)
}

res2 = session.post(url, data=payload, verify=False)
soup2 = BeautifulSoup(res2.text, "html.parser")

tahsils = [(opt.text, opt.get("value")) for opt in soup2.find("select", id="ddltahsil").find_all("option")]
print("Tahsils found after district change:", len(tahsils))
print("First few tahsils:", tahsils[:5])
