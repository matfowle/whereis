#!/usr/bin/python
from itty import *
from requests_toolbelt import MultipartEncoder
import urllib2, json, requests, os, sys
import grequests as async

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

@post('/')
def index(request):
    webhook = json.loads(request.body)
    print webhook['data']['id']
    result = sendSparkGET('https://api.ciscospark.com/v1/messages/{0}'.format(webhook['data']['id']))
    result = json.loads(result)
    print result
    msg = None
    if webhook['data']['personEmail'] != bot_email and "@cisco.com" in webhook['data']['personEmail']:
        person = result.get('text', '').lower()
        global cmx_script_url
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Sure, looking for "+ person +". I'll check and be back soon!"})
        if "whereis" in person:
            person = person.split("whereis ",1)[1]
        if person == "help":
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Usage: Enter the CEC user ID of the person you are looking for and I will check Cisco IT's Singapore CMX for that user. If found, I will return their location. If I am in a room with other people, make sure you mention me first!"})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Unfortunately, not all sites in APJ are synced with CMX yet so feel free to lobby IT to sync your location :)."})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "If you want to make your own bot, here is my code - https://github.com/matfowle/whereis"})
            return "true"

        payload = {'person':person, 'clientCurrent':'0', 'source':'spark', 'clientList':'[]'}
        headers = {'User-Agent': 'Mozilla/5.0'}

        async_dict = {}

        request = (async.post(url = u, headers=headers, data=payload) for u in cmx_script_urls)
        responses = async.map(request)
      
        for result in responses:
            if result:
                async_dict[result.url] = json.loads(result.content)

        if async_dict[cmx_script_url]['image'] == False:
            data = async_dict[cmx_script_url2]
            text = data['text']
            filepath = data['image']
            clientCount = int(data['clientCount'])
            clientCurrent = 0
            clientNext = clientCurrent
            filetype = 'image/png'
            print text
            if filepath == False:
                sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text})
                return "true"
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location', open(filepath, 'rb'), filetype)})
            os.remove(filepath)
            return "true"
        if async_dict[cmx_script_url2]['image'] is not False:
            os.remove(async_dict[cmx_script_url2]['image'])
        data = async_dict[cmx_script_url]
        text = data['text']
        filepath = data['image']
        clientCount = int(data['clientCount'])
        clientList = data['clientList']
        clientCurrent = 0
        clientNext = clientCurrent + 1
        filetype = 'image/png'
        print text

        if clientCount > 1:
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": person +" has "+ str(clientCount) +" devices. I'll get their locations for you."})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location', open(filepath, 'rb'), filetype)})
            os.remove(filepath)
            while clientNext < clientCount:
                payload = {'person':person, 'clientCurrent':str(clientNext), 'source':'spark', 'clientList':clientList}
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
    elif webhook['data']['personEmail'] != bot_email and "@cisco.com" not in webhook['data']['personEmail']:
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Sorry, this bot is only for Cisco staff. Please use a Cisco account."})
        return "true"
    return "true"

####CHANGE THIS VALUE#####
bearer = "blah"
bot_email = "blah"
cmx_script_url = "http://127.0.0.1/cgi-bin/see-em-x.py"
cmx_script_url2 = "http://127.0.0.1/cgi-bin/see-em-x-mse.py"
cmx_script_urls = [
    cmx_script_url,
    cmx_script_url2
]

run_itty(server='wsgiref', host='127.0.0.1', port=10010)