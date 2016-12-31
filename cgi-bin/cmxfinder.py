#!/usr/local/bin/python
#####################################################################
#                                                                   #
#   Module:         cmxfinder.py                                    #
#   Author:         Matthew Fowler 2016                             #
#   Company:        Cisco Systems                                   #
#   Description:    Python CGI script to find user location via     #
#                   the CMX REST API and display it on a map        #
#                                                                   #
#####################################################################

#####################################################################
#                       Dependancy Imports                          #
#####################################################################

import cgi, requests, json, base64, PIL
import matplotlib.pyplot as plt
requests.packages.urllib3.disable_warnings()
from requests.auth import HTTPBasicAuth
from PIL import Image
from cStringIO import StringIO

#####################################################################
#                       Environment Settings                        #
#####################################################################

# CMX address and credentials.
cmxAddr = "blah"
cmxUser = "blah"
cmxPass = "blah"

# These aren't needed, just here for testing.
cmxAuthString = cmxUser +':'+ cmxPass
cmxEncodedAuthString = base64.b64encode(cmxAuthString)

# API URLs
urlClientByUsername = cmxAddr +"/api/location/v2/clients?username="
urlFloorImage = cmxAddr +"/api/config/v1/maps/imagesource/"

# Get values from the HTML form that is POST to this script.
form = cgi.FieldStorage()
person = form.getvalue('person')
clientCurrent = int(form.getvalue('clientCurrent'))
clientNext = clientCurrent + 1

# Used for the storeMemory function.
buff = StringIO()


#####################################################################
#                       Function Definitions                        #
#####################################################################

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


#####################################################################
#                         Main Execution                            #
#####################################################################

def main():
    
    # First, get the data from CMX.
	# Get the client location data by username.
    clientList = json.loads(cmxContent(urlClientByUsername+person))

    # Check if the user exists in CMX. This is done by checking if the json list is empty.
    if not clientList:
		print ('Content-type: text/html\n\n'
        	   '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
        	   '<div class="form">'\
        	   '<p class="message">Sorry, '+ person +' could not be found... <a href=../>Search again</a></p><br>'
        	   '</div>')
		return
    
    # Get number of clients with this username.
    clientCount = len(clientList)

    # Get the first client with this username.
    client = clientList[clientCurrent]

    # Get the image file of the floor the client is on from CMX and save it in memory with the storeMemory function.
    image = storeMemory(cmxContent(urlFloorImage + client["mapInfo"]["image"]["imageName"])).encode("base64").strip()

    # Split the Campus>Building>Floor string into it's components. 
    # This is useful if you want to print out the location, particularly the floor as floor plans may be similar and hard to distinguish via the image alone.
    hierarchy = client["mapInfo"]["mapHierarchyString"].split('>')

    # Now, plot the user's location on the image.
    # Read the floor image from memory with pyplot. Pyplot uses PIL to support jpeg.
    im = plt.imread(StringIO(image.decode('base64')), format='jpeg')

    # Draw a plot over the image that is the same size as the image.
    implot = plt.imshow(im, extent=[0, client["mapInfo"]["floorDimension"]["width"], 0, client["mapInfo"]["floorDimension"]["length"]], origin='lower', aspect=1)

    # Mark the client's coordinates that we received from CMX. 
    # The first line will draw a dot at the x,y location and the second line will draw a circle around it.
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])])
    plt.scatter([str(client["mapCoordinate"]["x"])], [str(client["mapCoordinate"]["y"])], s=1000, facecolors='none')

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
    plt.savefig(buff, format='png', dpi=100)

    # Get the new image.
    buff.seek(0)
    newimage = buff.getvalue().encode("base64").strip()

    # Finally, print what you want to show.
    print ('Content-type: text/html\n\n'
           '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
    	   '<div class="result">'
           + person + ' has been found!'
           '<p class="message" style="text-align:center">')
   
    # This adds an additional message if there are more than one device with the username.
    if clientCount > 1:
    	print ('This username is being used by '+ clientCount +' devices'
    		   '<br>This is device ' + clientNext +' of '+ clientCount +'')

        # This adds a hidden form with a button that runs the search again for the next device in the list.
        # As you can see it runs the script again - this is done because the device may be on another floor so we may need a new image.
    	if clientNext <= clientCount:
    		print ('<br><form action="cgi-bin/cmxfinder.py" method="POST" class="login-form">'
    			'<input type="hidden" value="'+ clientNext +'" name="clientCurrent"/>'
    			'<button type="submit" value="Submit">Click here to see the next device</button>'
    			'</form> ')

    print ('<br>MAC address: '+ client["macAddress"] + 
           '<br>IP address: '+ client["ipAddress"][0] + 
           '<br>Connected to: '+ client["ssId"] + 
           '<br>Campus: '+ hierarchy[0] + 
           '<br>Building: '+ hierarchy[1] + 
           '<br>Floor: '+ hierarchy[2] + 
           '<br>Coordinates: x='+ str(client["mapCoordinate"]["x"]) +' y='+ str(client["mapCoordinate"]["y"]) + 
           '<br>Last heard: '+ str(client["statistics"]["maxDetectedRssi"]["lastHeardInSeconds"]) +' seconds ago'+  
           '<img src="data:image/png;base64,'+ newimage +'"/>'
           '<br>Click on the image to expand'
           '</p>'
           '</div><center>'
           '<div class="form">'
           '<p class="message">Do you want to look for another? <a href=../>Search again</a></p><br>'
           '</div>')


try: 
    # Check that the username isn't empty.
    if person == None:
    	print ('Content-type: text/html\n\n'
    		   '<link rel="stylesheet" type="text/css" href="../mystyle.css">'
               '<div class="form">'
               '<p class="message">You did not enter anything... <a href=../>Search again</a></p><br>'
               '</div>')

    else:
    	if __name__ == "__main__":
    		main()

except:
    cgi.print_exception()


