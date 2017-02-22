#!/usr/local/bin/python
############################################################################
#                                                                          #
#   Module:         see-em-x.py                                            #
#   Author:         Matthew Fowler 2017                                    #
#   Company:        Cisco Systems                                          #
#   Description:    Python CGI script to find user locations via           #
#                   the CMX REST API and display it on a map.              #
#                                                                          #
############################################################################

############################################################################
#                       Dependancy Imports                                 #
############################################################################

import cgi, requests, json, base64, PIL, re, uuid, os, sys
import matplotlib.pyplot as plt
requests.packages.urllib3.disable_warnings()
from requests.auth import HTTPBasicAuth
from PIL import Image
from cStringIO import StringIO

############################################################################
#                       Environment Settings                               #
############################################################################

####CHANGE THESE VALUES#####
# CMX address and credentials.
cmxAddr = ""
cmxUser = ""
cmxPass = ""

# These aren't needed, just here for testing.
cmxAuthString = cmxUser +':'+ cmxPass
cmxEncodedAuthString = base64.b64encode(cmxAuthString)

# API URLs
urlClientByUsername = cmxAddr +"/api/location/v2/clients?username="
urlAllClients = cmxAddr +"/api/location/v2/clients"
urlFloorImage = cmxAddr +"/api/config/v1/maps/imagesource/"

# Get values from the form that is POST to this script.
form = cgi.FieldStorage()
person = form.getvalue('person')
clientCurrent = int(form.getvalue('clientCurrent'))
searchedBuilding = form.getvalue('searchedBuilding')
source = form.getvalue('source')

clientNext = clientCurrent + 1

# Sometimes the username used to connect to the network has the domain as a prefix. This defines the prefix.
domain = r"CISCO\\"

# Used for the storeMemory function.
buff = StringIO()

# This is the path for the floorplan image files should be stored.
image_path = "../images/"


############################################################################
#                       Function Definitions                               #
############################################################################

def cmxContent(url):

    # GET request to CMX based on the url you provide.
    request = requests.get(url = url,auth = HTTPBasicAuth(cmxUser,cmxPass),verify=False)
    return request.content

def storeMemory(item):

    # Use cStringIO to write the item to memory.
    buff.write(item)

    # Go back to the start of the item.
    buff.seek(0)

    # Return the item we just stored.
    return buff.getvalue()

def is_json(myjson):
    
    # Checks if the content is json.
    try:
        json_object = json.loads(myjson)
    except ValueError, e:
        return False
    return json_object


############################################################################
#                         Main Execution                                   #
############################################################################

def main():
    
    # The form returns "all" if the user click on List All Users. This if statement is for that scenario.
    if person == "all":
        
        # Get the list of client info from the CMX API and sort by username.
        allClientsList = is_json(cmxContent(urlAllClients))

        # Sometimes the CMX API might fail to respond with anything so this keeps trying until it does.
        while (allClientsList == False):
          allClientsList = is_json(cmxContent(urlAllClients))

        # If the API responds with json, but it is empty, there are no users in CMX so we notify the user.
        if not allClientsList:
          print ('Content-type: text/html\n\n'
                 '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
                 '<div class="form">'
                 '<p class="message">'
                 'There are no users... <a href=../>Search again</a>'
                 '</p>'
                 '<br>'
                 '</div>')
          return

        # Get the number of users and print it.
        allClientsCount = len(allClientsList)
        print ('Content-type: text/html\n\n'
               '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
               '<div id="loading" class="form"></div>'
               '<div id="content" class="login-page">'
               '<div class="form">'
               'Here are all the users that were found!'
               '<p class="message">Click on the user to see their location or... <a href=../>Search again</a></p>'
               '<p class="message">This may take some time to fully load...</p>')

        
        # Make a button for every user detected and when clicked on, sumbit that username back to the script.
        for client in allClientsList:
          searchedClient = re.escape(client["userName"])
          hierarchy = client["mapInfo"]["mapHierarchyString"].split('>')
          if client["userName"] != "" and hierarchy[1] == searchedBuilding:
            print ('<p class="message">'
                   '<form action="see-em-x.py" method="POST" class="login-form">'
                   '<input type="hidden" value="0" name="clientCurrent"/>'
                   '<input type="hidden" value="'+ searchedClient +'" name="person"/>'
                   '<button type="submit" value="Submit" onclick="loading();">'+ client["userName"] +'</button>'
                   '</form>'
                   '</p>')
        
        # The CMX API has a maximum page size of 1000 so if 1000 results are returned then we want to get the next page.
        if allClientsCount == 1000:
          currentCount = allClientsCount - 1000
          page = 2

          # When there are less than 1000 results we know it is the last page so we end the while loop.
          while (currentCount >= 0):
            allClientsList = is_json(cmxContent(urlAllClients+"?page="+str(page)))
            
            # Again, sometimes the API fails to respond with json so this keeps trying.
            while (allClientsList == False):
              allClientsList = is_json(cmxContent(urlAllClients+"?page="+str(page)))

            allClientsCount = len(allClientsList)

            # Make a button for every user detected and when clicked on, sumbit that username back to the script.
            for client in allClientsList:
              searchedClient = re.escape(client["userName"])
              hierarchy = client["mapInfo"]["mapHierarchyString"].split('>')
              if client["userName"] != "" and hierarchy[1] == searchedBuilding:
                print ('<p class="message">'
                       '<form action="see-em-x.py" method="POST" class="login-form">'
                       '<input type="hidden" value="0" name="clientCurrent"/>'
                       '<input type="hidden" value="'+ searchedClient +'" name="person"/>'
                       '<button type="submit" value="Submit" onclick="loading();">'+ client["userName"] +'</button>'
                       '</form>'
                       '</p>')
            page += 1
            currentCount = allClientsCount - 1000  

        print('</p></div></div>'
              '<script src="//cdnjs.cloudflare.com/ajax/libs/jquery/2.1.3/jquery.min.js"></script>'
              '<script type="text/javascript">'
              'function loading(){'
              '    $("#loading").show();'
              '    $("#content").hide();'     
              '}'
              '</script>')

        return

    # First, get the data from CMX.
    # Get the client location data by username.
    clientList = json.loads(cmxContent(urlClientByUsername+person))
    
    # If the client isn't found, try it again but with the domain as a prefix for the username.
    if not clientList:
      clientList = json.loads(cmxContent(urlClientByUsername+domain+person))

    # Check if the user exists in CMX. This is done by checking if the json list is empty.
    if not clientList:

      # If the request came from a post from the Spark Bot, send json with the error message and quit.
      if source == "spark":
        print "Content-type: application/json"
        print
        response = {'text': 'Sorry, '+ person +' could not be found...', 'image': False, 'clientCount': '0'}
        print (json.JSONEncoder().encode(response))
        return 
      
      # If not from Spark, print it out in HTML and quit.
      print ('Content-type: text/html\n\n'
             '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
             '<div class="form">'
             '<p class="message">'
             'Sorry, '+ person +' could not be found... <a href=../>Search again</a>'
             '</p>'

             '<br>'
             '</div>')
      return
    
    # Get number of clients with this username.
    clientCount = len(clientList)

    # Get the first client with this username.
    client = clientList[clientCurrent]
    
    if os.path.isfile(image_path + client["mapInfo"]["image"]["imageName"]) == True:
      file = image_path + client["mapInfo"]["image"]["imageName"]
      fh = open(file, "rb")
      image = storeMemory(fh.read()).encode("base64").strip()
      fh.close()
      
    
    else:
    # Get the image file of the floor the client is on from CMX and save it in memory with the storeMemory function.
      image = cmxContent(urlFloorImage + client["mapInfo"]["image"]["imageName"])
      file = image_path + client["mapInfo"]["image"]["imageName"]
      fh = open(file, "w+")
      fh.write(image)
      fh.close()
      fh = open(file, "rb")
      image = storeMemory(fh.read()).encode("base64").strip()
      

    # Split the Campus>Building>Floor string into it's components. 
    # This is useful if you want to print out the location, particularly the floor as floor plans may be similar and hard to distinguish via the image alone.
    hierarchy = client["mapInfo"]["mapHierarchyString"].split('>')

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

    # Get the new image.
    newimage = buff.getvalue().encode("base64").strip()

    # If the request came from Spark, save the image to a file so that the Spark Bot can send it as a file. It also sends some text about the user and their location.
    if source == "spark":
      file = "/var/www/html/images/"+ str(uuid.uuid4()) +".png"
      fh = open(file, "w+")
      fh.write(newimage.decode('base64'))
      fh.close()
      print "Content-type: application/json"
      print
      response = {'text': client["userName"] + ' is '+ client["dot11Status"] +' to '+ client["ssId"] +' in '+ hierarchy[1] +' on level '+ hierarchy[2], 'image': file, 'clientCount': clientCount}
      print (json.JSONEncoder().encode(response))
      return

    # If not from Spark, print what you want to show in HTML.
    print ('Content-type: text/html\n\n'
           '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
           '<div class="form">'
           '<p class="message-a" style="text-align:center">'
           '<b>'+ client["userName"] + '</b> is <b>'+ client["dot11Status"] +'</b> to <b>'+ client["ssId"] +'</b> in <b>'+ hierarchy[1] +'</b> on level <b>'+ hierarchy[2] +'</b>.'
           '<br>'
           '<br>'
           'Click and hold on the image to expand'
           '<br>'
           '<img src="data:image/png;base64,'+ newimage +'"/>'
           '</p>')

    # This adds an additional message if there is more than one device with the requested username.
    if clientCount > 1:
        print ('<p class="message">'
             '<b>!!!This username is being used by '+ str(clientCount) +' devices!!!</b>'
               '<br>'
               'This is device ' + str(clientNext) +' of '+ str(clientCount) +
               '</p>')

        # This adds a hidden form with a button that runs the search again for the next device in the list.
        # As you can see it runs the script again - this is done because the device may be on another floor so we may need a new image.
        if clientNext < clientCount:
            print ('<br>'
                 '<form action="see-em-x.py" method="POST" class="login-form">'
                   '<input type="hidden" value="'+ str(clientNext) +'" name="clientCurrent"/>'
                   '<input type="hidden" value="'+ person +'" name="person"/>'
                   '<button type="submit" value="Submit">Click here to see the next device</button>'
                   '</form> ')

    print ('<p class="message">'
           'Do you want to look for another user? <a href=../>Search again</a>'
           '</p>'
           '<p class="message" style="text-align:center">'
           'Some extra details that you may want:'
           '<br>'
           '<b>MAC address:</b> '+ client["macAddress"] + '')
    if client["ipAddress"] != None:
      print ('<br>'
             '<b>IP address:</b> '+ client["ipAddress"][0] +'') 
    print ('<br>'
           '<b>Coordinates:</b> x='+ str(client["mapCoordinate"]["x"]) +' y='+ str(client["mapCoordinate"]["y"]) + 
           '<br>'
           '<b>Last heard:</b> '+ str(client["statistics"]["maxDetectedRssi"]["lastHeardInSeconds"]) +' seconds ago'+  
           '<br>'
           '</p>'
           '</div>')

try: 
    # Check that the username isn't empty.
    if person == None:
        print ('Content-type: text/html\n\n'
               '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
               '<div class="form">'
               '<p class="message">You did not enter anything... <a href=../>Search again</a>'
               '</p>'
               '<br>'
               '</div>')

    else:
        if __name__ == "__main__":
            main()

except:
    cgi.print_exception()