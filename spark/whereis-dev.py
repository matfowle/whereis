#!/usr/bin/python
from itty import *
from datetime import datetime
from requests_toolbelt import MultipartEncoder
import urllib2, json, requests, os, sys, pickle
import grequests as async


bearer = "blah"
bot_email = "blah"
ldap_url = "blah"
cmx_script_url = "http://127.0.0.1:11111/"
#cmx_script_url2 = "http://127.0.0.1/cgi-bin/see-em-x-mse.py"
#cmx_script_url3 = "http://127.0.0.1/cgi-bin/see-em-x-wng.py"
#cmx_script_url4 = "http://127.0.0.1/cgi-bin/see-em-x-ebc.py"

cmx_script_urls = [
    cmx_script_url#,
#    cmx_script_url3,
#    cmx_script_url4
]

input_file = "/var/www/html/spark/stats.json"
optout = "/var/www/html/spark/optout"


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

def sendSparkLocation(url, source, person, async_dict, startTime, webhook):
    data = async_dict[url]
    text = data['text']
    filepath = data['image']
    clientCount = int(data['clientCount'])
    clientList = data['clientList']
    clientCurrent = 0
    clientNext = clientCurrent + 1
    filetype = 'image/png'
    print text
    sys.stdout.flush()

    if filepath == False:
        print (str(datetime.now() - startTime)+ "Sending not found")
        sys.stdout.flush()
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text})
        print (str(datetime.now() - startTime)+ "Finished sending not found")
        sys.stdout.flush()
        with open(input_file, "r+") as data_file:    
            stats = json.loads(data_file.read())
            data_file.seek(0)
            stats["notFound"] += 1
            data_file.write(json.dumps(stats))
            data_file.truncate()
        print (str(datetime.now() - startTime)+ "Finished not found")
        sys.stdout.flush()
        return "true"

    with open(input_file, "r+") as data_file:    
        stats = json.loads(data_file.read())
        data_file.seek(0)
        stats[source] += 1
        data_file.write(json.dumps(stats))
        data_file.truncate()

    if clientCount > 1:
        print (str(datetime.now() - startTime)+ "Sending " +source+ " multi client")
        sys.stdout.flush()
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": person +" has "+ str(clientCount) +" devices. I'll get their locations for you."})
        print (str(datetime.now() - startTime)+ "Sending " +source+ " first client")
        sys.stdout.flush()
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location.png', open(filepath, 'rb'), filetype)})
        print (str(datetime.now() - startTime)+ "Finished "+source+ " sending first client")
        sys.stdout.flush()
        os.remove(filepath)
        
        while clientNext < clientCount:
            payload = json.JSONEncoder().encode({'person':person, 'clientCurrent':str(clientNext), 'source':'spark', 'clientList':json.JSONEncoder().encode(clientList)})
            headers = {'User-Agent': 'Mozilla/5.0'}
            msg = requests.post(url, headers=headers, data=payload)
            data = json.loads(msg.content)
            text = data['text']
            filepath = data['image']
            filetype = 'image/png'
            print text
            sys.stdout.flush()
            print (str(datetime.now() - startTime)+ "Sending "+source+" next client")
            sys.stdout.flush()
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location.png', open(filepath, 'rb'), filetype)})
            print (str(datetime.now() - startTime)+ "Finished "+source+" sending client")
            sys.stdout.flush()
            os.remove(filepath)
            clientNext += 1
        
        print (str(datetime.now() - startTime)+ "Finished sending "+source)
        sys.stdout.flush()
        return "true"

    print (str(datetime.now() - startTime)+ "Sending "+source)
    sys.stdout.flush()
    sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": text, "files": ('location.png', open(filepath, 'rb'), filetype)})
    print (str(datetime.now() - startTime)+ "Finished sending "+source)
    sys.stdout.flush()
    os.remove(filepath)
    return "true"

def exception_handler(request, exception):
    return None

@post('/')
def index(request):
    sys.stdout.flush()
    startTime = datetime.now()
    print (str(startTime)+ " Starting")
    sys.stdout.flush()
    webhook = json.loads(request.body)

    result = sendSparkGET('https://api.ciscospark.com/v1/messages/{0}'.format(webhook['data']['id']))
    result = json.loads(result)

    msg = None
    
    if webhook['data']['personEmail'] != bot_email and "@cisco.com" in webhook['data']['personEmail']:
        print ("Request from " +webhook['data']['personEmail'])
        sys.stdout.flush()
        person = result.get('text', '').lower().strip()
        #global cmx_script_url
        requester = webhook['data']['personEmail'].split("@")[0]

        with open(optout, "rb") as fp:
            optoutlist = pickle.load(fp)

        if "whereis" in person:
            person = person.split("whereis ",1)[1]
        
        print ("Looking for " +person)

        if " " in person:
			print (str(datetime.now() - startTime)+ " Looks like a full name, checking LDAP")
			sys.stdout.flush()
			person = person.replace(' ', '+')
			headers = {'Accept': 'application/json'}
			r = ldap_url+ "/ldap/?have=description&values=" +person+ "&want=cn"
			ldap_request = requests.get(url = r, headers=headers)
			ldap_result = json.loads(ldap_request.content)
			if ldap_result['responseCode'] == 0:
				person = person.replace('+', ' ').title()
				person = ldap_result['results'][person]['cn']
				print (str(datetime.now() - startTime)+ " Found them in LDAP - "+ person)
				sys.stdout.flush()
			else:
				print (str(datetime.now() - startTime)+ " Didn't find in LDAP - "+ person)
				sys.stdout.flush()
				sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "It looks like you tried to enter a full name but I can't find that person. Please check the spelling and try again."})
				return "true"        

        if person == "optout":
            
            if requester in optoutlist:
                reply = requester +", you have already opted out. Type **optin** if you want to opt back in."
                sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
                return "true"
            
            optoutlist.append(requester)

            with open(optout, "wb") as fp:
                pickle.dump(optoutlist, fp)
            reply = "Thanks, "+ requester +", you have now opted out. Type **optin** if you want to opt back in."
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
            return "true"

        if person == "optin":
            try:
                optoutlist.remove(requester)
                with open(optout, "wb") as fp:
                    pickle.dump(optoutlist, fp)
                reply = "Thanks, "+ requester +", you have now opted back in!"
                sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
                return "true"
            except:
                reply = requester +", you are already opted in..."
                sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
                return "true"


        if person == "stats":
            with open(input_file, "r+") as data_file:    
                stats = json.loads(data_file.read())
                reply = "**IT CMX:** "+ str(stats['cmx']) +"\n"
                reply += "**IT MSE:** "+ str(stats['mse']) +"\n"
                reply += "**Building 24:** "+ str(stats['wng']) +"\n"
                reply += "**Nortech:** "+ str(stats['ebc']) +"\n"
                reply += "**Not Found:** "+ str(stats['notFound']) +"\n"
                reply += "**Not Cisco:** "+ str(stats['notCisco'])
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
            return "true"
        if person == "help":
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": "**Usage:** Enter the CEC user ID of the person you are looking for and I will check Cisco IT's CMX for that user. If found, I will return their location. If I am in a room with other people, make sure you mention me first! Feel free to reach out to Matt Fowler (matfowle) for any feedback/questions."})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": "*Unfortunately, not all sites are synced with CMX yet so feel free to lobby IT to sync your location :).*"})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": "**NEW:** You can now use full names! e.g. 'matt fowler'"})
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": "If you wish to opt out, type **optout**"})
            with open(input_file, "r+") as data_file:    
                stats = json.loads(data_file.read())
                data_file.seek(0)
                stats["help"] += 1
                data_file.write(json.dumps(stats))
                data_file.truncate()
            return "true"

        if person in optoutlist:
            reply = "Sorry, "+ person +" has opted out of whereis."
            sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "markdown": reply})
            return "true"

        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Sure, looking for "+ person +". I'll check and be back soon!"})

        payload = json.JSONEncoder().encode({'person':person, 'clientCurrent':'0', 'source':'spark', 'clientList':'[]'})
        headers = {'User-Agent': 'Mozilla/5.0'}

        async_dict = {}
        print (str(datetime.now() - startTime)+ "Starting async")
        sys.stdout.flush()
        request = (async.post(url = u, headers=headers, data=payload) for u in cmx_script_urls)
        responses = async.map(request, exception_handler=exception_handler)
        print (str(datetime.now() - startTime)+ "Finished async")
        sys.stdout.flush()
        
        for result in responses:
            if result:
            	#print (str(datetime.now() - startTime)+ " "+ result.content)
                sys.stdout.flush()
                async_dict[result.url] = json.loads(result.content)
        print (str(datetime.now() - startTime)+ "Finished dictionary")
        sys.stdout.flush()
        print async_dict

        if not async_dict.get(cmx_script_url, {}).get('image'):
            print (str(datetime.now() - startTime)+ "Not CMX")
            sys.stdout.flush()
    
            if not async_dict.get(cmx_script_url3, {}).get('image'):
                print (str(datetime.now() - startTime)+ "Not WNG")
                sys.stdout.flush()
                
                if not async_dict.get(cmx_script_url4, {}).get('image'):
                    print (str(datetime.now() - startTime)+ "Not EBC")
                    sys.stdout.flush()
                    result = requests.post(url = cmx_script_url2, headers=headers, data=payload)
                    
                    if result:
                        async_dict[result.url] = json.loads(result.content)
                        print (str(datetime.now() - startTime)+ "Finished adding MSE to dictionary")
                        sys.stdout.flush()
                    
                        sendSparkLocation(cmx_script_url2, "mse", person, async_dict, startTime, webhook)
                        return "true"

                    else:
                        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Sorry, "+ person +" could not be found... \n\n  Type *help* if you need assistance."})
                        return "true"

                sendSparkLocation(cmx_script_url4, "ebc", person, async_dict, startTime, webhook)
                return "true"

            sendSparkLocation(cmx_script_url3, "wng", person, async_dict, startTime, webhook)
            return "true"

        sendSparkLocation(cmx_script_url, "cmx", person, async_dict, startTime, webhook)
        return "true"

    elif webhook['data']['personEmail'] != bot_email and "@cisco.com" not in webhook['data']['personEmail']:
        sendSparkPOST("https://api.ciscospark.com/v1/messages", {"roomId": webhook['data']['roomId'], "text": "Sorry, this bot is only for Cisco staff. Please use a Cisco account or contact your local Cisco representative if you want to see the bot in action."})
        with open(input_file, "r+") as data_file:    
            stats = json.loads(data_file.read())
            data_file.seek(0)
            stats["notCisco"] += 1
            data_file.write(json.dumps(stats))
            data_file.truncate()
        return "true"
    return "true"


run_itty(server='wsgiref', host='127.0.0.1', port=10011)