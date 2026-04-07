def _ajax_upmain(fd: dict, target: str):
    payload = dict(fd)
    payload["ScriptManager1"] = f"UpMain|{target}"
    if target.startswith("btn"):
        payload["__EVENTTARGET"] = ""
        payload[target] = "शोध / Search" if target == "btnSearch_RestMaha" else "Submit"
    else:
        payload["__EVENTTARGET"] = target
    payload["__EVENTARGUMENT"] = ""
    payload["__ASYNCPOST"] = "true"
    return payload

print(_ajax_upmain({}, "btnSearch_RestMaha"))
print(_ajax_upmain({}, "ddlvillage"))
