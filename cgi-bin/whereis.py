#!/usr/local/bin/python
############################################################################
#                                                                          #
#   Module:         whereis.py                                             #
#   Author:         Matthew Fowler 2017                                    #
#   Company:        Cisco Systems                                          #
#   Description:    Python Spark Bot that listens for input in a Spark     #
#                   room and then submits the input as a username to       #
#                   the main python script that gets the users location    #
#                   from CMX. It then posts the returned info back to the  #
#                   room.                                                  #
#                                                                          #
############################################################################

############################################################################
#                       Dependancy Imports                                 #
############################################################################

from itty import *
from requests_toolbelt import MultipartEncoder
import urllib2, json, requests, os, sys

############################################################################
#                       Environment Settings                               #
############################################################################

####CHANGE THESE VALUES#####
bearer = ""
bot_email = ""
cmx_script_url = ""

############################################################################
#                       Function Definitions                               #
############################################################################

def sendSparkGET(url):
    request = urllib2.Request(url,
                            headers={"Accept" : "application/json",
                                     "Content-Type":"application/json"})
    request.add_header("Authorization", "Bearer "+bearer)
    contents = urllib2.urlopen(request).read()
    return contents

def sendSparkPOST(url, data):
    m = MultipartEncoder(fields=data)
    request = requests.post(url, data=m,
                            headers={"Content-Type": m.content_type,
                            "Authorization": "Bearer "+bearer})
    return request

############################################################################
#                         Main Execution                                   #
############################################################################

@post('/')
def index(request):
    webhook = json.loads(request.body)
    #print webhook['data']['id']
    result = sendSparkGET('https://api.ciscospark.com/v1/messages/{0}'.format(webhook['data']['id']))
    result = json.loads(result)
    #print result
    msg = None
    if webhook['data']['personEmail'] != bot_email:
        person = result.get('text', '').lower()
        if "whereis" in person:
            person = person.split("whereis ",1)[1]
        payload = {'person':person, 'clientCurrent':'0', 'source':'spark'}
        headers = {'User-Agent': 'Mozilla/5.0'}
        msg = requests.post(cmx_script_url, headers=headers, data=payload)
        data = json.loads(msg.content)
        text = data['text']
        filepath = data['image']
        clientCount = int(data['clientCount'])
        clientCurrent = 0
        clientNext = clientCurrent
        filetype = 'image/png'
        #print text
        if filepath == False:
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text})
            return "true"
        if clientCount > 1:
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": person +" has "+ str(clientCount) +" devices. I'll get their locations for you."})
            os.remove(filepath)
            while clientNext <= clientCount:
                payload = {'person':person, 'clientCurrent':str(clientNext), 'source':'spark'}
                headers = {'User-Agent': 'Mozilla/5.0'}
                msg = requests.post(cmx_script_url, headers=headers, data=payload)
                data = json.loads(msg.content)
                text = data['text']
                filepath = data['image']
                filetype = 'image/png'
                sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location', open(filepath, 'rb'), filetype)})
                os.remove(filepath)
                clientNext += 1
            return "true"
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location', open(filepath, 'rb'), filetype)})
        os.remove(filepath)

    return "true"


run_itty(server='wsgiref', host='127.0.0.1', port=10010)