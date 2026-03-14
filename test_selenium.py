from selenium import webdriver
from selenium.webdriver.chrome.options import Options
opts = Options()
opts.add_argument("--headless")
try:
    driver = webdriver.Chrome(options=opts)
    print("Success:", driver.capabilities["browserVersion"])
    driver.quit()
except Exception as e:
    print("Error:", e)
