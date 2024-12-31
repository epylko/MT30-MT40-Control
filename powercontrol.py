#/usr/bin/env python3

#
# This app uses flask to take webhooks from the Meraki Dashboard,
# specifically an MT30 button press to control an MT40 power sensor
#

import ipaddress
import json
import meraki
import time
from flask import Flask, request

#
# Meraki webhooks can come from:
# 209.206.48.0/20, 216.157.128.0/20, 158.115.128.0/19
#
# Convert them into a a network list
WEBHOOK_NETLIST=['209.206.48.0/20','216.157.128.0/20','158.115.128.0/19']
WEBHOOK_NETS=[]

for net in WEBHOOK_NETLIST:
    WEBHOOK_NETS.append (ipaddress.ip_network(net))

#
# local IP address and port for flask to listen on
# my use case gets the request forwarded from a nginx reverse proxy
#
HOSTIP='192.168.255.101'
HOSTPORT=8772

#
# this keeps track of which buttons control which sensors
#
# format is MT30 serial number: (MT40 serial number, shared secret)
#
# I did it this way in case I have other MT30s I want to control things
#
validSNs={'<MT-30 SN>' : ('<MT-40 SN>','<WebHook PW>')}

#
# MT40 commands - just shorter commands
#
turnOn="enableDownstreamPower"
turnOff="disableDownstreamPower"

#
# Meraki dashboard key
#
API_KEY = '<put your API key here>'

#
# Used to keep track of double long presses of the button
# i.e. I want a double long press to turn off the power
#
LONGPRESSINTERVAL=10.0
lastPress=time.time()
pressCount=0

#
# basic flask app starts here
#
app = Flask(__name__)

@app.route('/MT30',methods=['POST'])
def MT30():
    global lastPress
    global pressCount

    now = time.time()

    req = request.get_json()
    # Get the original IP address (in case there's a proxy in the way)
    src_ip = request.headers.get("X-Real-Ip")

    # make sure the webhook came from a Meraki IP address
    MERAKI_SOURCE = False
    for net in WEBHOOK_NETS:
        MERAKI_SOURCE = MERAKI_SOURCE or (ipaddress.ip_address(src_ip))

    if not MERAKI_SOURCE:
        print("Request not from Meraki!")
        return("OK")

    sn = req["deviceSerial"]
    ss = req["sharedSecret"]
    press = req["alertData"]["trigger"]["button"]["pressType"]

    # make sure it's one of our serial numbers
    if sn not in validSNs:
        print ("Not a valid serial number")
        return ("OK")

    # get our MT40 sn and webhook shared secret
    (mt40, whss) = validSNs[sn]

    # make sure the shared secret is correct
    if whss != ss:
        print ("Shared secrets don't match")
        return ("OK")

    # this logic isn't quite right, but the double long-press needs
    # to be within 10 seconds
    if press == "long":
        print("Long press")
        pressCount += 1

        if (now - lastPress) > LONGPRESSINTERVAL:
            print("  First long press. Doing nothing")
            lastPress = now
            return("OK")

        if pressCount % 2 == 0:
            print ("  Second long press. Turning off")
            lastPress = now
            operation=turnOff
        else:
            return("OK")
    elif press == "short":
        print ("Turning on")
        operation=turnOn
    else:
        print ("No button press received")
        return("OK")

    # OK, we can instantiate the dashboard and act on the press length
    dashboard = meraki.DashboardAPI(API_KEY,output_log=False,suppress_logging=True)

    response = dashboard.sensor.createDeviceSensorCommand(mt40, operation)

    return("OK")

if __name__ == '__main__':
    app.run(debug=False, host=HOSTIP, port=HOSTPORT)
