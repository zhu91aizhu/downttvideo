# 今日头条视频下载

## Usage:

​    downttvideo [-im] [-c=<thread_count>] <video>

​    downttvideo (-h | --help)

​    downttvideo (-v | --version)

## Options:

​    -h --help					显示帮助

​    -v --version				显示版本号

​    -i --id	启					用ID，参数为头条视频ID，默认为头条视频URL

​    -m --multi					开启多线程

​    -c --threadcount=count		多线程数量，默认为计算机核心数

## Examples:

​    使用头条视频URL进行下载

​    downttvideo http://www.365yg.com/item/6526784250472038919

​    使用头条视频ID进行下载

​    downttvideo -i 6526784250472038919

​    开启多线程，并设置8个线程下载

​    downttvideo -imc 8 6526784250472038919