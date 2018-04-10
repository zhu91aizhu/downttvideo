""" 今日头条视频下载
Usage:
    downttvideo [-im] [-c=<thread_count>] <video>
    downttvideo (-h | --help)
    downttvideo (-v | --version)

Options:
    -h --help                   显示帮助
    -v --version                显示版本号
    -i --id                     启用ID，参数为头条视频ID，默认为头条视频URL
    -m --multi                  开启多线程
    -c --threadcount=<count>    多线程数量，默认为计算机核心数

Examples:
    使用头条视频URL进行下载
    downttvideo http://www.365yg.com/item/6526784250472038919

    使用头条视频ID进行下载
    downttvideo -i 6526784250472038919

    开启多线程，并设置8个线程下载
    downttvideo -imc 8 6526784250472038919
"""

import os
import os.path
import sys
import math
import random
import base64
import logging
import binascii
import threading
import urllib.parse
import multiprocessing

import requests
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from docopt import docopt
from tqdm import tqdm


BASE_URL = "http://www.365yg.com/item/"

# 默认多线程数量
DEFAULT_THREAD_COUNT = multiprocessing.cpu_count

# 程序参数及视频下载地址
class Config(object):
    # 实际线程数量
    thread_count = 1
    # 开启多线程
    enable_multi = False
    # 启用ID
    enable_id = False
    # 视频下载地址
    video_url = ""

# 程序路径
APP_PATH, APP_FILE_NAME = os.path.split(os.path.abspath(sys.argv[0]))
# 默认视频下载路径
DEFAULT_OUT_PATH = os.path.join(APP_PATH, "videos")

ARTICLE_URL = "http://www.toutiao.com/c/user/article/"

VIDEO_ITEM_URL = "http://www.toutiao.com/item/"

LOGGER = logging.getLogger('main')
LOGGER.setLevel(logging.ERROR)
FIL_HANDLER = logging.FileHandler(
    os.path.join(os.path.join(APP_PATH, "logs"), "main.log")
)
FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
FIL_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(FIL_HANDLER)


class VideoDownloader(object):
    """视频下载器"""

    def __init__(self, url, video_info, filepath=None, multi=False, thread_count=DEFAULT_THREAD_COUNT):
        self._url = url
        self._video_info = video_info
        self._filepath = filepath
        self._multi = multi
        self._thread_count = thread_count
        self._downloader = None

    def download(self):
        """视频下载"""

        if self._multi:
            self._downloader = MultiThreadDownloader(
                self._url, self._video_info, self._filepath, self._thread_count
            )
        else:
            self._downloader = SingleThreadDownloader(
                self._url, self._video_info, self._filepath
            )

        self._downloader.download()


class SingleThreadDownloader(object):
    """单线程视频下载器"""

    def __init__(self, url, video_title, filepath=None):
        super(SingleThreadDownloader, self).__init__()
        self._url = url
        self._video_title = video_title
        self._filepath = filepath

    def download(self):
        response = requests.get(self._url, stream=True)
        if response.status_code == 200:
            title = self._video_title + ".mp4"

            if self._filepath:
                filename = os.path.join(self._filepath, title)
            else:
                filename = os.path.join(DEFAULT_OUT_PATH, title)

            filesize = int(response.headers["Content-Length"])

            with open(filename, "wb") as file:
                with tqdm(total=filesize, desc="下载中", unit_scale=True) as pbar:
                    for chunk in response.iter_content(chunk_size=4096):
                        if chunk:
                            file.write(chunk)
                            file.flush()
                            pbar.update(len(chunk))
                    LOGGER.info("下载完成")
        else:
            LOGGER.error("获取视频失败")


class MultiThreadDownloader(object):
    """多线程视频下载器"""

    def __init__(self, url, video_title, filepath, thread_count):
        super(MultiThreadDownloader, self).__init__()
        self._url = url
        self._video_title = video_title

        if filepath:
            self._filepath = filepath
        else:
            self._filepath = DEFAULT_OUT_PATH

        self._thread_count = thread_count

    def __action(self, index, filesize):
        persize = math.ceil(filesize / self._thread_count)
        start_pos = (index - 1) * persize
        end_pos = start_pos + persize - 1
        if end_pos > filesize - 1:
            end_pos = filesize - 1

        content_range = "bytes=%s-%s" % (start_pos, end_pos)
        headers = {"Range" : content_range}
        response = requests.get(self._url, stream=True, headers=headers)

        if response.status_code == 206:
            title = self._video_title + ".mp4.pack%s" % index
            filename = os.path.join(self._filepath, title)
            total = int(response.headers["Content-Length"])

            current_size = 0
            pbar = tqdm(
                total=total, desc="#%s下载中" % index, unit_scale=True,
                position=(index-1), ncols=60
            )

            with open(filename, "wb") as part_file:
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        part_file.write(chunk)
                        part_file.flush()
                        current_size = current_size + len(chunk)
                        pbar.update(len(chunk))

                LOGGER.info("#%s 下载完成" % index)

            pbar.close()
        else:
            LOGGER.error("#%s 下载视频失败" % index)

    def download(self):
        """下载文件"""
        filesize = 0

        response = requests.get(self._url, stream=True)
        if response.status_code == 200:
            filesize = int(response.headers["Content-Length"])
        else:
            LOGGER.error("获取视频文件大小失败")
            return

        if filesize == 0:
            LOGGER.error("未能正确获取视频文件大小")
            return

        for i in range(self._thread_count):
            thread = threading.Thread(
                target=self.__action, kwargs={"index":i+1, "filesize":filesize}
            )
            thread.setDaemon(True)
            thread.start()

        main_thread = threading.current_thread()
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            thread.join()

        self.__merge_file(filesize)

    def __merge_file(self, filesize):
        """合并文件"""
        fullfilepath = os.path.join(self._filepath, self._video_title+".mp4")
        fullfile = open(fullfilepath, "w+b")

        pbar = tqdm(
            total=filesize, desc="合并中", unit_scale=True,
            position=self._thread_count, ncols=60
        )

        for i in range(1, self._thread_count+1):
            with open(fullfilepath + ".pack%s" % i, "rb") as part_file:
                while True:
                    chunk = part_file.read(4096)
                    if chunk:
                        fullfile.write(chunk)
                        fullfile.flush()
                        pbar.update(len(chunk))
                    else:
                        break
                part_file.close()

            os.remove(fullfilepath + ".pack%s" % i)

        pbar.close()
        fullfile.close()
        LOGGER.info("文件合并完毕")


def down_video(video_url):
    """视频下载"""
    driver = webdriver.PhantomJS()
    driver.get(video_url)

    video_detail_ele = WebDriverWait(driver, 60, 0.5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".video_detail"))
    )
    video_id = video_detail_ele.get_attribute("videoid")

    video_title_ele = WebDriverWait(driver, 60, 0.5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".abs-title"))
    )
    video_title = video_title_ele.text
    print(video_title)

    url = "http://ib.365yg.com/video/urls/v/1/toutiao/mp4/%s" % video_id
    r_param = str(random.random())[2:]
    request_path = urllib.parse.urlparse(url).path + "?r=" + r_param
    crc = binascii.crc32(bytes(request_path, encoding="utf8"))
    s_param = right_shift(crc, 0)

    url = url + '?r=%s&s=%s' % (r_param, s_param)

    resp = requests.get(url)
    if resp.status_code == 200:
        json_data = resp.json()

        data = json_data["data"]
        video_list = data["video_list"]
        videos = []
        for key in video_list:
            video_info = video_list[key]

            main_url = video_info["main_url"]
            rel_url = base64.standard_b64decode(main_url)
            definition = video_info["definition"]
            size = video_info["size"]

            videos.append({"size": size, "definition": definition, "rel_url": rel_url})

        video = max(videos, key=lambda x: x["size"])
        downloader = VideoDownloader(
            video["rel_url"], video_title, None, Config.enable_multi, Config.thread_count)
        downloader.download()
    else:
        LOGGER.error("获取视频真实地址失败")


def right_shift(val, n):
    """数据移位"""
    return val >> n if val >= 0 else (val + 0x100000000) >> n


def main():
    down_video(Config.video_url)


def parseArguments(arguments):
    if arguments["--threadcount"]:
        Config.thread_count = int(arguments["--threadcount"])
    else:
        Config.thread_count = DEFAULT_THREAD_COUNT

    Config.enable_multi = arguments["--multi"]
    
    enable_id = arguments["--id"]
    if enable_id:
        Config.video_url = urllib.parse.urljoin(BASE_URL, arguments["<video>"])
    else:
        if arguments["<video>"].startswith("http://"):
            Config.video_url = arguments["<video>"]
        else:
            Config.video_url = "http://" + arguments["<video>"]


if __name__ == "__main__":
    arguments = docopt(__doc__, version="tt video downloader V0.1")
    parseArguments(arguments)

    main()
