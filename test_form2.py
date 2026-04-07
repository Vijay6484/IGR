from script_revised import _form_to_dict
html = open("/Users/vijaytiwari/Documents/IGR/http_trace/rest_maharashtra_response.txt").read()
fd = _form_to_dict(html)
print(fd.keys())
