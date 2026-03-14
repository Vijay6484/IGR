from bs4 import BeautifulSoup

with open("test.html", "r") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

for input_tag in soup.find_all("input", type="hidden"):
    print((input_tag.get("name"), input_tag.get("id"), len(input_tag.get("value", ""))))
