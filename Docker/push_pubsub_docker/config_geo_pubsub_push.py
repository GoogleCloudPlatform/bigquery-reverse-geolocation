#!/usr/bin/env python
# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This script reads traffic sensor data from a set of csv files,  adding vehicle id, geo encodes the files  and publishes that data
to PubSub.  If you run it on a GCE instance, this instance must be
created with the "Cloud Platform" Project Access enabled. Click on
"Show advanced options" when creating the image to find this setting.

Before you run the script, create one PubSub topic, in the same project as the
GCE instance you will run on, to publish to. Edit the TRAFFIC_TOPIC or you can
pass in the names as a command-line argument.

Before you run this script, download some demo  data files (~2GB):
curl -O \
http://storage.googleapis.com/aju-sd-traffic/unzipped/Freeways-5Minaa2010-01-01_to_2010-02-15.csv
Or, for a smaller test file, you can use:
http://storage.googleapis.com/aju-sd-traffic/unzipped/Freeways-5Minaa2010-01-01_to_2010-02-15_test2.csv
These files contain real traffic sensor data from San Diego freeways.
See this file for copyright info:
http://storage.googleapis.com/aju-sd-traffic/freeway_detector_config/Freeways-Metadata-2010_01_01/copyright(san%20diego).txt

Usage:

Run the script passing in the location of the folder that contains the csv files
% python geo_pubsub.py --fileloc 'your_folder_location'
Run 'python traffic_pubsub_generator.py -h' for more information.
"""
import argparse
import base64
import csv
import datetime
import random
import sys
import time
import os
import datetime
import yaml
import googlemaps

from apiclient import discovery
from dateutil.parser import parse
import httplib2
from oauth2client import client as oauth2client

with open("/tmp/creds/setup.yaml", 'r') as  varfile:
    cfg = yaml.load(varfile)

# default; set to your traffic topic. Can override on command line.
TRAFFIC_TOPIC = cfg["env"]["PUBSUB_TOPIC"]
PUBSUB_SCOPES = ['https://www.googleapis.com/auth/pubsub']
NUM_RETRIES = 3
ROOTDIR = cfg["env"]["ROOTDIR"]


def create_pubsub_client(http=None):
    credentials = oauth2client.GoogleCredentials.get_application_default()
    if credentials.create_scoped_required():
        credentials = credentials.create_scoped(PUBSUB_SCOPES)
    if not http:
        http = httplib2.Http()
    credentials.authorize(http)
    return discovery.build('pubsub', 'v1', http=http)


def publish(client, pubsub_topic, data_line, msg_attributes=None):
    """Publish to the given pubsub topic."""
    data = base64.b64encode(data_line)
    msg_payload = {'data': data}
    if msg_attributes:
        msg_payload['attributes'] = msg_attributes
    body = {'messages': [msg_payload]}
    resp = client.projects().topics().publish(
        topic=pubsub_topic, body=body).execute(num_retries=NUM_RETRIES)
    return resp

def create_timestamp(hms,dmy):
    """Format two time/date columns as a datetime object"""
    h = int(hms[0:2])
    m = int(hms[2:4])
    s = int(hms[4:6])
    #print "{0} {1} {2}".format(h,m,s)
    d= int(dmy[0:2])
    m = int(dmy[2:4])
    y = int(dmy[4:6]) + 2000
    #print "{0} {1} {2}".format(d,m,y)
    return (str(datetime.datetime(y,m,d,h,m,s)))


def main(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument("--fileloc", default=ROOTDIR, help="input folder with csv files")
    parser.add_argument("--topic", default=TRAFFIC_TOPIC,
                        help="The pubsub 'traffic' topic to publish to. " +
                        "Should already exist.")

    args = parser.parse_args()

    pubsub_topic = args.topic
    print "Publishing to pubsub 'traffic' topic: %s" % pubsub_topic

    rootdir = args.fileloc
    print "Folder to process: %s" % rootdir


    client = create_pubsub_client()

    for subdir, dirs, files in os.walk(rootdir):
        for file in files:
            #San Diego data file names include trip ID, use this to identify each journey
            name_ext = file.split(".")
            vehicleID = name_ext[0][15:]
            
            myfile = os.path.join(subdir,file)
            print myfile
            line_count = 0
            with open(myfile) as data_file:
                reader = csv.reader(data_file)
                for line in reader:
                    line_count += 1
 #                   print "%s lines processed" % line_count
                    if line_count > 1:
                        #Convert NMEA GPS format to decimal degrees
                        #see http://www.gpsinformation.org/dale/nmea.htm#position for NMEA GPS format details
                        lat = float(line[3][0:2])
                        lng = float(line[5][0:3])
                        lng_minutes = float(line[5][3:])/60
                        lat_minutes = float(line[3][2:])/60
                        latitude = lat + lat_minutes
                        longitude =  0 - (lng + lng_minutes)
                        ts = create_timestamp(line[1],line[9])
                        msg_attributes = {'timestamp': ts}
                        print "Vehicle ID: {0}, location: {1}, {2}; speed: {3} mph, bearing: {4} degrees".format(vehicleID, latitude,longitude, line[7], line[8])
                        proc_line =  "{0}, {1}, {2}, {3} ,{4} ".format(vehicleID, latitude,longitude, line[7], line[8])
                        publish(client, pubsub_topic, proc_line, msg_attributes)

if __name__ == '__main__':
        main(sys.argv)
