#!/usr/bin/env python
#coding:utf-8
'''
    collect from agent server and send data to influxdb

'''

import  os
from influxdb import  InfluxDBClient
from threading import Thread
import  re
import  commands
import logging
import ConfigParser
import sys
import getopt

def log(logname,loglevel=logging.INFO ,filename="zg_ping.log"):
    logger = logging.getLogger(logname)
    logger.setLevel(loglevel)
    path = "xx"
    filename = path+filename
    #print filename
    fh = logging.FileHandler(filename=filename)
    fh.setLevel(loglevel)
    fmt = "%(asctime)s, %(levelname)s, %(lineno)d, %(funcName)s, %(message)s"
    formatter = logging.Formatter(fmt)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info(filename)
    return logger

logger = log("ping",loglevel=logging.ERROR)

def ping(addr, count=10, timeout=2, interval=1, pksize=56):
    '''
    :param addr:
    :param count:
    :param timeout:   sec ,in mac millsec
    :param interval: send time interval sec
    :param pksize:
    :return: loss,max,avg,min rtt
    '''
    cmd = "ping -c %s -W %s -i %s -s %s -q  %s"%(count,timeout,interval,pksize,addr)
    status ,result = commands.getstatusoutput(cmd)
    #  result
    if status == 0:
        pattern_loss = re.compile(r'received,\s([0-9|\.]+)%')
        pattern_rtt = re.compile(r'dev\s=\s(.*)\sms')
        loss  = pattern_loss.search(result).groups()[0]
        loss =  float(loss)

        rtt = pattern_rtt.search(result).groups()[0]
        rtt = [float(f) for f in rtt.split("/")]
        minrtt, avgrtt, maxrtt = rtt[0],rtt[1],rtt[2]
        return  loss,minrtt,avgrtt,maxrtt

    else:
        logger.error("ping %s error,timeout or refused"%(addr))
        return 100.0,-1.0,-1.0,-1.0

def multiPing(filename):
    '''
     collect data and report to db
    :param config_file:
    :return: none
    '''
    result = []
    thread_list=[]
    config = ConfigParser.ConfigParser()
    config.read(filename)
    sections = config.sections()
    source_ip  = config.get(section="monitor",option="ip")
    source_area = config.get(section="monitor",option="area")
    source_isp = config.get(section="monitor",option="isp")
    measurement = config.get(section="monitor",option="measurement")
    for section in sections:
        if section == "monitor":
            continue
        for unit in config.items(section=section):
            remote_iplist = unit[1].split(",")
            isp = unit[0]
            for remote_ip in remote_iplist:
                args = { "remote_ip":remote_ip,
                         "remote_area":section,
                         "source_ip":source_ip,
                         "source_area":source_area,
                         'isp':isp,
                         'measurement':measurement,
                         'source_isp':source_isp,
                         }
                t = Mythread(func=pack,kwargs=args)
                thread_list.append(t)
                t.start()
                logger.debug("create thread %s"%(remote_ip))

    for th in thread_list:
        th.join()
        result +=th.get_result()

    report(result)

def pack(remote_ip,remote_area,source_ip,source_area,isp,source_isp,measurement="icmp"):
    '''
    :param ip:
    :return: influxdb list
    '''
    percent_lost, minrtt, artt, maxrtt = ping(remote_ip)
    data = [
        {
            "measurement":measurement,
            'tags':{
                "src":source_ip,
                "dest":remote_ip,
                "remote_area":remote_area,
                "source_area":source_area,
                "isp":isp,
                "source_isp":source_isp,
            },
            'fields':{
                'loss': percent_lost,
                'max': maxrtt,
                'min': minrtt,
                'avg': artt,
            }
        }
    ]
    logger.debug("collect data success")
    return data

#multi thread
class Mythread(Thread):
    def __init__(self,func,kwargs):
        super(Mythread,self).__init__()
        self.func = func
        self.kwargs = kwargs

    def run(self):
        self.result = self.func(**self.kwargs)

    def get_result(self):
        #   logger.debug("get thread result")
        return  self.result



def report(data):
    try:

        influx = InfluxDBClient(
            host = "xx",
            port = "xx",
            username = "monitor",
            password = 'xxx',
            database = 'netmonitor',
        )
        influx.write_points(data)
        logger.info("send to db success")

    except Exception,e:
        logger.exception("write to db error")

def usage():
    print '''
     -c filename ,--config=filename  #config file,default current directory config.ini

     -h ,--help #print this helpful info
     '''
    exit(-1)

def main():
    config=None
    try:
        options,args = getopt.getopt(sys.argv[1:],'hc:',['help','config='])
    except:
        logger.exception("get optiions error")
        exit(-1)
    for name,value in options:
        if name in ("-h","--help"):
            usage()
        elif name in ("-c","--config"):
            config = value
        else:
            print "no such option"
            usage()
    if config == None:
        config = "config.ini"
    logger.debug(config)
    if os.path.exists(config):
        logger.info("start ping")
        multiPing(config)
    else:
        print "config file not exist"
        exit(-1)
if __name__ == "__main__":
    main()


