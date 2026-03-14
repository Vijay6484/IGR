import requests

session = requests.Session()
response = session.get("https://freesearchigrservice.maharashtra.gov.in", verify=False)
print("Status Code:", response.status_code)
print("Cookies:", session.cookies.get_dict())
with open("test.html", "w") as f:
    f.write(response.text)

