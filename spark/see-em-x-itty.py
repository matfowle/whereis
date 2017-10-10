#!/usr/bin/python
#!/usr/local/bin/python
############################################################################
#                                                                          #
#   Module:         see-em-x.py                                            #
#   Author:         Matthew Fowler 2017                                    #
#   Company:        Cisco Systems                                          #
#   Description:    Python CGI script to find user locations via           #
#                   the CMX REST API and display it on a map. Accepts      #
#                   input from a web form or a Spark Bot.                  #
#                                                                          #
############################################################################

############################################################################
#                       Dependancy Imports                                 #
############################################################################

from itty import *
import cgi, requests, json, base64, PIL, re, uuid, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
requests.packages.urllib3.disable_warnings()
from requests.auth import HTTPBasicAuth
from PIL import Image
from cStringIO import StringIO
import grequests as async
from systemd import journal
from datetime import datetime

############################################################################
#                       Environment Settings                               #
############################################################################

####CHANGE THESE VALUES#####
# CMX address and credentials.
cmxAddr1 = "blah"
cmxAddr2 = "blah"
cmxAddr3 = "blah"
cmxAddr4 = "blah"
cmxUser = "blah"
cmxPass = "blah"

urls = [
    cmxAddr1#,
#    cmxAddr2,
#    cmxAddr3,
#    cmxAddr4
]

# API URLs
urlClientByUsername = "/api/location/v2/clients?username="
urlFloorImage = "/api/config/v1/maps/imagesource/"

# Sometimes the username used to connect to the network has the domain as a prefix. This defines the prefix.
domain = r"CISCO\\"

prefixes = ['', r"CISCO\\", r"cisco\\"]

# This is the path for the floorplan image files should be stored.
image_path = "/var/www/html/images/"

buff = StringIO()


############################################################################
#                       Function Definitions                               #
############################################################################


def cmxContent(url):

    # GET request to CMX based on the url you provide.
    try:
      request = requests.get(url = url,auth = HTTPBasicAuth(cmxUser,cmxPass),verify=False, timeout=2)
      return request.content
    except requests.exceptions.RequestException as e:
      return "[]"

def storeMemory(item):
    
    s = StringIO() 
    # Use cStringIO to write the item to memory.
    s.write(item)

    # Go back to the start of the item.
    s.seek(0)

    # Return the item we just stored.
    return s.getvalue()

def is_json(myjson):
    
    # Checks if the content is json.
    try:
        json_object = json.loads(myjson)
    except ValueError, e:
        return False
    return json_object

def exception_handler(request, exception):
    return None

############################################################################
#                         Main Execution                                   #
############################################################################

@post('/')
def index(request):    
    startTime = datetime.now()
    journal.send(str(startTime)+ " see-em-x Starting")
    StringIO().truncate(0)
    form = json.loads(request.body)
    person = form['person']
    clientCurrent = int(form['clientCurrent'])
    source = form['source']
    clientList = json.loads(form['clientList'])
   
    clientNext = clientCurrent + 1
    
    ############ New code section that does parallel API calls to the list of CMX servers. ############
    if not clientList: 
        # List where the urls for each request are stored.
        urlClientByUsernameWithDomain = []

        # Add each CMX URL with each username, domain prefix combination to the list.
        for u in urls:
            urlClientByUsernameWithDomain.extend((u+urlClientByUsername+p) for p in prefixes)

        # Dictionary where we will store the responses from CMX in a format of URL:JSON.
        async_dict = {}

        # Use the grequests module to send requests to all the CMX servers at the same time with all domain prefix and username combinations.
        journal.send(str(datetime.now() - startTime)+ ' Starting async to CMX')
        
        request = (async.get(url = u+person, auth = HTTPBasicAuth(cmxUser,cmxPass),verify=False, timeout=1) for u in urlClientByUsernameWithDomain)
        responses = async.map(request, exception_handler=exception_handler)
        
        journal.send(str(datetime.now() - startTime)+ ' Finshed async to CMX')

        journal.send(str(datetime.now() - startTime)+ ' Checking results')
        # Check that the returned responses are all valid and if so, put them in the list in the format of URL:JSON.
        for result in responses:
            if result:
              async_dict[result.url] = json.loads(result.content)

        journal.send(str(datetime.now() - startTime)+ ' Finding the CMX server')
        # From the dictionary, find which server responded and set that as the CMX server so that we can do the image call.
        for k in async_dict:
            if async_dict[k]:
              for u in urls:
                if u in k:
                  cmxAddr = u
              clientList = async_dict[k]
              break
            else:
              clientList = async_dict[k]
        journal.send(str(datetime.now() - startTime)+ ' Finished finding the CMX server')
      
      # Check if the user exists in CMX. This is done by checking if the json list is empty.
        if not clientList:
        
        # If the request came from a post from the Spark Bot, send json with the error message and quit.
            if source == "spark":
                journal.send(str(datetime.now() - startTime)+ ' Not found - replying to bot')
                print "Content-type: application/json"
                print
                response = {'text': "Sorry, "+ person +" could not be found... \n\n  Type *help* if you need assistance.", 'image': None, 'clientList': '', 'clientCount': '0', 'cmxServer': ''}  
                journal.send(str(datetime.now() - startTime)+ ' Finished replying')      
                return json.JSONEncoder().encode(response) 
    
    journal.send(str(datetime.now() - startTime)+ ' Got the client list')
    # Get number of clients with this username.
    clientCount = len(clientList)

    # Get the first client with this username.
    client = clientList[clientCurrent]
    
    # Check if we have already got the floor image file stored locally.
    if os.path.isfile(image_path + client["mapInfo"]["image"]["imageName"]) == True:
        file = image_path + client["mapInfo"]["image"]["imageName"]
        fh = open(file, "rb")
        image = storeMemory(fh.read()).encode("base64").strip()
        fh.close()
        journal.send(str(datetime.now() - startTime)+ ' Already have the image')
      
    
    else:
    # Get the image file of the floor the client is on from CMX, save it to a file, then load it in StingIO so we can work with it in memory. 
    # We save it to a file first so that next time we don't have to pull an image from CMX. Speed things up and reduces load on CMX.
        journal.send(str(datetime.now() - startTime)+ ' No image - getting')
        image = cmxContent(cmxAddr+urlFloorImage + client["mapInfo"]["image"]["imageName"])
        journal.send(str(datetime.now() - startTime)+ ' Got it')
        file = image_path + client["mapInfo"]["image"]["imageName"]
        fh = open(file, "w+")
        fh.write(image)
        fh.close()
        fh = open(file, "rb")
        image = storeMemory(fh.read()).encode("base64").strip()
      

    # Split the Campus>Building>Floor string into it's components. 
    # This is useful if you want to print out the location, particularly the floor as floor plans may be similar and hard to distinguish via the image alone.
    hierarchy = client["mapInfo"]["mapHierarchyString"].split('>')

    journal.send(str(datetime.now() - startTime)+ ' Rendering the location')
    # Now, plot the user's location on the image.
    # Read the floor image from memory with pyplot. Pyplot uses PIL to support jpeg.
    im = plt.imread(StringIO(image.decode('base64')), format='jpeg')
    
    # Some images were showing red like http://stackoverflow.com/questions/21641822/ and this seems to fix it.
    convertedim=Image.open(StringIO(image.decode('base64'))).convert('P')

    # Draw a plot over the image that is the same size as the image.
    implot = plt.imshow(convertedim, extent=[0, client["mapInfo"]["floorDimension"]["width"], 0, client["mapInfo"]["floorDimension"]["length"]], origin='lower', aspect=1)

    # Mark the client's coordinates that we received from CMX. 
    # The first line will draw a dot at the x,y location and the second and third lines will draw circles around it.
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])], facecolor='r', edgecolor='r')
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])], s=1000, facecolors='none', edgecolor='r')
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])], s=2000, facecolors='none', edgecolor='r')
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])], s=3500, facecolors='none', edgecolor='r')

    # Currently the plot is the same size as the image, but the scale is off so we need to correct that.
    ax = plt.gca()
    ax.set_ylim([0,client["mapInfo"]["floorDimension"]["length"]])
    ax.set_xlim([0,client["mapInfo"]["floorDimension"]["width"]])

    # The plot starts 0,0 from the bottom left corner but CMX uses the top left. 
    # So, we need to invert the y-axis and, to make it easier to read, move the x axis markings to the top (if you choose to show them).
    ax.set_ylim(ax.get_ylim()[::-1])
    ax.xaxis.tick_top()

    # Use this to decide whether you want to show or hide the axis markings.
    plt.axis('off')

    # Save our new image with the plot overlayed to memory. The dpi option here makes the image larger.
    plt.savefig(buff, format='png', dpi=500)
    plt.gcf().clear()

    # Get the new image.
    newimage = buff.getvalue().encode("base64").strip()
    buff.seek(0)
    journal.send(str(datetime.now() - startTime)+ ' Done with the image')

    # If the request came from Spark, save the image to a file so that the Spark Bot can send it as a file. It also sends some text about the user and their location.
    if source == "spark":
        journal.send(str(datetime.now() - startTime)+ ' Saving file')
        file = image_path + str(uuid.uuid4()) +".png"
        fh = open(file, "w+")
        fh.write(newimage.decode('base64'))
        fh.close()
        journal.send(str(datetime.now() - startTime)+ ' Sending location to bot')
        print "Content-type: application/json"
        print
        response = {'text': client["userName"] + ' is '+ client["dot11Status"] +' to '+ client["ssId"] +' in '+ hierarchy[1] +' on level '+ hierarchy[2], 'image': file, 'clientCount': clientCount, 'clientList': clientList}
        #print (json.JSONEncoder().encode(response))
        journal.send(str(datetime.now() - startTime)+ ' Done')
        return (json.JSONEncoder().encode(response))
    return "true"

run_itty(server='wsgiref', host='127.0.0.1', port=11111)