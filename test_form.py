from bs4 import BeautifulSoup
import requests
from script_revised import _form_to_dict

html = open("/Users/vijaytiwari/Documents/IGR/http_trace/login_response.txt").read()
fd = _form_to_dict(html)
print(fd.keys())
