import requests
import img2pdf
import os
import re
import json
import time
import sys


# url = "https://max.book118.com/html/2021/1201/5134121031004130.shtm"
url = sys.argv[1]

headers = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer":"https://max.book118.com/"
}

dirname = './images'

""" Extracting params : the actual number of pages and the number of pages that can be previewed ......"""

def extract_value(data, key):
    if isinstance(key, str):
        value = re.search(r".*?"+key+r":[\s']*(.*?)[',\n]", data, re.DOTALL) if data and key is not None else None
        return value.group(1) if value else None
    
    elif isinstance(key, list):
        value = {}
        for item in key:
            result = re.search(r".*?"+item+r":[\s']*(.*?)[',\n]", data, re.DOTALL)
            if result:
                value[item] = result.group(1)
        return value
    else:
        raise Exception("[!] Key type exception")


""" Parse the main page """

def parse_main(text, label):
    # re.DOTALL -> . can match '\n'
    data = re.search(r".*?"+label+r":.*?({.*?})", text, re.DOTALL) if text and label is not None else None
    if data:
        return data.group(1).strip()
    else:
        return ''
    

""" Download all images """

def download_png(url, page):
    url = f"https:{url}"
    image_content = requests.get(url).content
    with open(f'{dirname}/{page}.png', 'wb') as f:
        f.write(image_content)
    # print(f"[*] Save Image {page}.png")


""" Fetch links of images from response and return the number of pages obtained """

def extract_img_url(dict_data):
    if dict_data.get('status') != 200 or dict_data.get('message') != 'ok':
        raise Exception("[!] Return jsonp data has error")
    img_dict = dict_data.get('data')
    for key in img_dict.keys():
        if key == 'page':
            continue
        print(f"[*] page:{key} link:{img_dict.get(key)}")
        download_png(img_dict.get(key), key)
        current_page = int(key)
    return current_page


""" Recursive request api to fetch the links of images """

def recursive_read_links(url, params, preview_page):
    resp = requests.get(url=url, params=params, timeout=5)
    if resp.status_code == 200:
        json_resp = re.search(r"jsonpReturn\((.*)\);", resp.text, re.DOTALL)
        # Convert response to json format
        if dict_data := json.loads(json_resp.group(1)):
            if (current_page := extract_img_url(dict_data)) < int(preview_page):
                params['page'] = str(current_page + 1)
                # print(params.get('page'))
                time.sleep(2)
                recursive_read_links(url, params, preview_page)
    else:
        raise Exception(f"[!] Unable access url : {url}  {resp.status_code}")
  

""" Crawling images by parameters """

def crawl_image(params):
    api_url = "https://openapi.book118.com"
    path = "/getPreview.html"
    preview_page = params.get('preview_page')
    params = {k: v for k, v in params.items() if k == 'aid' or k == 'view_token'}
    params['project_id'] = '1'
    params['page'] = 1
    try:
        recursive_read_links(url=api_url+path, params=params, preview_page=preview_page)
    except:
        raise


""" Convert png to pdf """

def convert_to_pdf(dirname, filename, preview_page):
    img_files = []
    for index in range(1,preview_page+1):
        img_files.append(f'{dirname}/{index}.png')
    try:
        with open(filename,"wb") as f:
            f.write(img2pdf.convert(img_files))
        print()
        print(f"Success convert pdf {filename}")
    except Exception:
        raise
    finally:
        [os.remove(img_file) for img_file in img_files]
    

try:

    resp = requests.get(url=url, headers=headers)
    if resp.status_code == 200:
        print(f"[*] Successfully access the page\n")
    
    if title := re.search(r".*?title:\s'(.*?)'.*?//文档标题", resp.text, re.DOTALL):
        print(f"[*] The title of document : {title.group(1)}\n")
    
    print("[*] Trying to find out the params")
    
    pic_info = parse_main(resp.text, label='pic')
    params = extract_value(pic_info, key=['aid', 'actual_page', 'preview_page', 'view_token'])
    print(f"{params}\n")

    print("[*] Trying to download images")
    crawl_image(params)

    convert_to_pdf(dirname=dirname, filename='target.pdf', preview_page=int(params.get('preview_page')))

except:
    raise