import requests
import img2pdf
import sys
import logging
import colorlog
import configparser
import json
import urllib3
import re
import os
import time
import argparse
from collections import OrderedDict
from typing import Dict


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


""" Logging Init """
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handle = logging.StreamHandler()
handle.setLevel(logging.DEBUG)
fmt = colorlog.ColoredFormatter(
    "%(name)s: %(white)s%(asctime)s%(reset)s %(log_color)s%(levelname)s%(reset)s %(process)d >>> %(log_color)s%(message)s%(reset)s"
)
handle.setFormatter(fmt=fmt)
logger.addHandler(handle)


""" Command line parse """
def SetParser():
    parser = argparse.ArgumentParser(
        prog = "Crawler",
        description="Crawl document of max.book118.com"
    )
    parser.add_argument("-u","--url", required=True, help="Specify url of document", type=str)
    parser.add_argument("-l", "--list", required=False,  help="Specify file list of document")
    parser.add_argument("-o", "--output-file",required=False,help="Specify path of output-file", type=str)

    return parser.parse_args()


""" Global variable Config """
config = configparser.ConfigParser()
config.read('./web_crawler.ini')
base_api = config['Settings']['BASE_API']
base_path = config['Settings']['BASE_PATH']
timeout = config['Settings']['TIMEOUT']
save_path = config['Settings']['SAVE_PATH'] 


class Crawler():
    def __init__(self, url, base_api, base_path, timeout, save_path=save_path) -> None:
        self.url: str = url
        self._metadata: Dict = {}
        self._image_dict: Dict = OrderedDict()
        self.base_api: str = base_api
        self.base_path: str = base_path
        self.timeout: int = timeout
        self.save_path: str = save_path


    """ Formatted raw metadata text"""
    def extract_metadata(self, raw_string: Dict):
        # Remove annotation
        pattern = re.compile("//.*\n")
        format_list = pattern.sub("", raw_string).split(',')
        format_dict = {}
        for item in format_list:
            item = item.strip('{} \n')
            key, value = item.split(':')[0], item.split(':')[1]
            format_dict[key.strip('\'" ')] = value.strip('\'" ')
        return format_dict

    """ Fetch the metadata of document """
    def fetch_mata_info(self):
        try:
            resp = requests.get(url=self.url)
            if resp.status_code == 200:
                logging.info("[*] Successfully access the page")
            if title := re.search(r".*?title:\s'(.*?)'.*?//文档标题", resp.text, re.DOTALL):
                logging.info(f"[*] The title of document : {title.group(1)}")
            if pic_info := re.search(r".*?pic:.*?({.*?})", resp.text, re.DOTALL):
                self._metadata = self.extract_metadata(pic_info.group(1).strip())
                logging.info(f"[*] The metadata : {self._metadata}")
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("Exception type: ", exc_type)
            logging.error("Exception value: ", exc_value)
            logging.error("Exception traceback: ", exc_traceback)
            raise
        
    """ Crawl all links of image, fitting in self._image_dict"""
    def crawl_image(self):
        if not self._metadata:
            return
        else:
            req_url = self.base_api + self.base_path
            req_params = {k: v for k, v in self._metadata.items() if k == 'aid' or k == 'view_token'}
            req_params['project_id'] = 1
            req_params['page'] = 1
            try:
                logging.info("[*] Try to fetch all links of images")
                self.fetch_pic_url(url=req_url, params=req_params, preview_page=self._metadata.get('preview_page'))
            except:
                raise
    
    def fetch_pic_url(self, url, params, preview_page):
        try:
            resp = requests.get(url=url, params=params, timeout=self.timeout)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logging.error("Exception type: ", exc_type)
            logging.error("Exception value: ", exc_value)
            logging.error("Exception traceback: ", exc_traceback)
            raise

        if not resp.status_code == 200:
            logging.error(f"[!] Unable to access url : {url}  {resp.status_code}")
            return

        json_resp = re.search(r"jsonpReturn\((.*)\);", resp.text, re.DOTALL)
        # Convert response to json format
        if dict_data := json.loads(json_resp.group(1)):
            if dict_data.get('status') != 200 or dict_data.get('message') != 'ok':
                logging.error("[!] Return jsonp data has error")
                return
            img_dict = {int(page):dict_data.get('data')[page] for page in dict_data.get('data').keys() - 'page'}
            current_page = max(img_dict.keys())

            self._image_dict |= img_dict

            if (int(current_page) < int(preview_page)):
                params['page'] = str(current_page + 1)
                # print(params.get('page'))
                time.sleep(self.timeout)
                self.fetch_pic_url(url, params, preview_page)

    def save_images(self):
        if os.path.exists(self.save_path):
            pass
        else:
            os.mkdir(self.save_path)

        images_path = OrderedDict()

        for page, url in self._image_dict.items():
            url = f"https:{url}"
            image_content = requests.get(url).content
            img_path = f'{self.save_path}/{page}.png'
            with open(img_path, 'wb') as f:
                f.write(image_content)
                images_path[page] = img_path
            logging.info(f"[*] Save Image {page}.png")
        

def convert_img_to_pdf(img_file_path, filename='save_file.pdf'):
    img_file_path = save_path
    img_files = os.listdir(img_file_path)
    sort_by_page = lambda x: int(x.split('.')[0])
    img_files = sorted(img_files, key=sort_by_page)
    try:
        with open(filename, "wb") as f:
            f.write(img2pdf.convert([f'{img_file_path}/{img_file}' for img_file in img_files]))
        logging.info(f"[*] Successfully convert to pdf -> {filename}")
    except Exception as e:
        logging.error(f"[!] convert process has error.")
        raise
    [os.remove(f'{img_file_path}/{img_file}') for img_file in img_files]



if __name__ == '__main__':
    args = SetParser()
    print(args._get_args)
    Crawl = Crawler(args.url, base_api, base_path, timeout=int(timeout))

    Crawl.fetch_mata_info()
    Crawl.crawl_image()
    # print(Crawl._image_dict)
    Crawl.save_images()

    if args.output_file:
        convert_img_to_pdf(save_path, args.output_file)
    else:
        convert_img_to_pdf(save_path)
    

