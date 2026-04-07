from bs4 import BeautifulSoup
from script_revised import _form_to_dict
html = open("/Users/vijaytiwari/Documents/IGR/http_trace/login_response.txt").read()
fd = _form_to_dict(html)
fd["ScriptManager1"] = "UpMain|btnOtherdistrictSearch"
fd["__EVENTTARGET"] = ""
fd["__EVENTARGUMENT"] = ""
fd["__ASYNCPOST"] = "true"
fd["btnOtherdistrictSearch"] = "Rest of Maharashtra / उर्वरित महाराष्ट्र"
print(fd.keys())
