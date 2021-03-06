# -*- coding:utf8 -*-

################################################################################		
#		
# Copyright (c) 2017 linzhi. All Rights Reserved		
#		
################################################################################		

"""
Created on 2017-04-08
Author: qilinzhi@gmail.com
"""

import os
import sys
import Queue
import thriftpy
import hashlib


from conf import constant
from lib import log
from lib import utils
from thriftpy.rpc import make_server

                 
class DispatchSpider(object):
    """
    spider dispatcher
    """

    CLIENT_TIMEOUT = 50000

    def __init__(self):

        self.redis_db = utils.RedisHandler(host=constant.REDIS_SERVER_HOST,
                                           port=constant.REDIS_SERVER_PORT)

        # 将种子url写到redis队列
        self.seed_url = constant.SEED_URL.DIANPING
        res = self.redis_db.rpush(constant.LIST_URL_QUEUE, self.seed_url)
        if isinstance(res, dict) and 'errno' in res and res['errno'] != 0 and 'errmsg' in res:
            errmsg = res['errmsg']
            log.error("初始化种子url :{} 失败, error msg: {}".format(self.seed_url, errmsg))

    def send_url(self):
        """
        @brief: 被slave调用，发送待抓取的url给slave节点
        @return: 如果获取的url已经抓取过，那么返回 "", 否则返回url
        """

        # 从redis队列中获取要抓取的url
        res = self.redis_db.lpop(constant.LIST_URL_QUEUE) 
        if isinstance(res, dict) and 'errno' in res and res['errno'] == 0 and \
            'data' in res and res['data'] is not None:
            url = res['data']
        elif 'errmsg' in res:
            errmsg = res['errmsg']
            log.error("从redis队列中获取待取的url失败, errmsg: {}".format(errmsg))
            raise RuntimeError("从redis队列中获取待抓取的url失败")

        # 判断非种子url是否已经抓取过，如果抓取过返回空，没有则写入redis的去重队列
        key = constant.CRAWLED_URL_SET
        value = hashlib.md5(url).hexdigest()

        if url != self.seed_url:
            res = self.redis_db.sismember(key, value)
            if isinstance(res, dict) and res.get("errno") == 0 and res.get("data") > 0:
                log.info("url: {} 已经抓取过，不再返回".format(url))
                return ""

        res = self.redis_db.sadd(key, value)
        if isinstance(res, dict) and res.get("errno") == 0 and res.get("data") > 0:
            log.info("已经抓取的url: {} 写入redis".format(url))
        elif isinstance(res, dict) and res.get("errmsg") is not None:
            errmsg = res.get('errmsg')
            log.error("已经抓取的url: {} 写入redis异常, errmsg: {}".format(url, errmsg))
            raise RuntimeError("抓取过的url写入redis异常")

        return url

    def receive_url(self, urls=None):
        """
        @brief: 被slave调用，接收待抓取的url，并保存在Queue
        @return: Bool
        """

        # 需要return Ture，否则thriftpy会报Missing result
        if not urls: return True

        for url in urls:
            url = url.strip().encode('utf8')
            res = self.redis_db.rpush(constant.LIST_URL_QUEUE, url)
            if isinstance(res, dict) and 'errno' in res and res.get('errno') != 0 and 'errmsg' in res:
                errmsg = res.get('errmsg')
                log.error("写url :{} 到redis队列失败, error msg: {}".format(url, errmsg))

        return True

    def main(self):
        """
        @brief: Main
        """

        spider = thriftpy.load(constant.THRIFT_FILE, module_name="spider_thrift")
        server = make_server(spider.SpiderService, DispatchSpider(), constant.RPC_HOST, 
                             constant.RPC_PORT, client_timeout=self.CLIENT_TIMEOUT)
        server.serve()


if __name__ == "__main__":
    master = DispatchSpider()
    master.main()



