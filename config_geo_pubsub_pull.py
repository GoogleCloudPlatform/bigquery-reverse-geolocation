#!/usr/bin/env python
# Copyright 2015 Google Inc. All Rights Reserved.
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
 This script reverse geocodes mesages pulled from a Google Cloud Pub/Sub queue (converts latitude & longitude to a street address),
 calculates the elevation above sea level,
 and converts from UTC time to local time by querying which timezone the locations fall in.
 It then writes the data plus this added geographic context to the BigQuery table.
"""
import sys
import base64
from apiclient import discovery
from dateutil.parser import parse
import httplib2
import yaml
import googlemaps
import time
import datetime
import uuid
import json
import signal
import sys
# from oauth2client.client import GoogleCredentials
from oauth2client import client as oauth2client

with open("resources/setup.yaml", 'r') as  varfile:
    cfg = yaml.load(varfile)

# Uses an environment variable by default. Change this value to the name of your traffic topic.
# Can override on the command line.
TRAFFIC_TOPIC = cfg["env"]["PUBSUB_TOPIC"]
PUBSUB_SCOPES = ['https://www.googleapis.com/auth/pubsub']
running_proc = True

def signal_term_handler(signal, frame):
    global running_proc
    print "Exiting application"
    running_proc = False
    sys.exit(0)



def create_pubsub_client(http=None):
    credentials = oauth2client.GoogleCredentials.get_application_default()
    if credentials.create_scoped_required():
        credentials = credentials.create_scoped(PUBSUB_SCOPES)
    if not http:
        http = httplib2.Http()
    credentials.authorize(http)
    return discovery.build('pubsub', 'v1', http=http)

def create_bigquery_client():
    credentials = oauth2client.GoogleCredentials.get_application_default()
    # Construct the service object for interacting with the BigQuery API.
    return discovery.build('bigquery', 'v2', credentials=credentials)

def stream_row_to_bigquery(bigquery, row,
                           num_retries=5):
    # Generate a unique row ID so retries
    # don't accidentally insert duplicates.
    insert_all_data = {
        'insertId': str(uuid.uuid4()),
        'rows': [{'json': row}]
    }
    return bigquery.tabledata().insertAll(
        projectId=cfg["env"]["PROJECT_ID"],
        datasetId=cfg["env"]["DATASET_ID"],
        tableId=cfg["env"]["TABLE_ID"],
        body=insert_all_data).execute(num_retries=num_retries)

# Use Maps API Geocoding service to convert lat,lng into a human readable address.
def reverse_geocode(gmaps, latitude, longitude):
    return gmaps.reverse_geocode((latitude, longitude))

# Extract a named property, e.g. formatted_address, from the Geocoding API response.
def extract_address(list, property):
    address = ""
    if(list[0] is not None):
        address = list[0][property]
    return address

# Extract a structured address component, e.g. postal_code, from a Geocoding API response.
def extract_component(list, property):
    val = ""
    for address in list:
        for component in address["address_components"]:
            if component["types"][0] == property:
                val = component["long_name"]
                break
    return val

# Calculate elevation using Google Maps Elevation API.
def get_elevation(gmaps, latitude, longitude):
    elevation = gmaps.elevation((latitude, longitude))
    elevation_metres = None
    if(len(elevation)>0):
        elevation_metres = elevation[0]["elevation"]
    return elevation_metres

# Get the timezone including any DST offset for the time the GPS position was recorded.
def get_timezone(gmaps, latitude, longitude, posix_time):
    return gmaps.timezone((latitude, longitude), timestamp=posix_time)

def get_local_time(timezone_response):
    # get offset from UTC
    rawOffset = float(timezone_response["rawOffset"])
    # get any daylight savings offset
    dstOffset = float(timezone_response["dstOffset"])

    # combine for total offset from UTC
    return rawOffset + dstOffset

# [START maininit]
def main(argv):

    client = create_pubsub_client()

    # You can fetch multiple messages with a single API call.
    batch_size = 100

    # Options to limit number of geocodes e.g to stay under daily quota.
    geocode_counter = 0
    geocode_limit = 10

    # Option to wait for some time until daily quotas are reset.
    wait_timeout = 2
# [END maininit]    
# [START createmaps]
    # Create a Google Maps API client.
    gmaps = googlemaps.Client(key=cfg["env"]["MAPS_API_KEY"])
    subscription = cfg["env"]["SUBSCRIPTION"]

    # Create a POST body for the Cloud Pub/Sub request.
    body = {
        # Setting ReturnImmediately to False instructs the API to wait
        # to collect the message up to the size of MaxEvents, or until
        # the timeout.
        'returnImmediately': False,
        'maxMessages': batch_size,
    }
# [END createmaps]
    signal.signal(signal.SIGINT, signal_term_handler)
    #[START pullmsgs]
    while running_proc:
        # Pull messages from Cloud Pub/Sub
        resp = client.projects().subscriptions().pull(
            subscription=subscription, body=body).execute()

        received_messages = resp.get('receivedMessages')
    # [END pullmsgs]


        if received_messages is not None:
            ack_ids = []
            bq = create_bigquery_client()
            for received_message in received_messages:
                pubsub_message = received_message.get('message')
                if pubsub_message:
                    # process messages
                    msg = base64.b64decode(str(pubsub_message.get('data')))

                    # We stored time as a message attribute.
                    ts = pubsub_message["attributes"]["timestamp"]

                    # Create a datetime object so we can get a POSIX timestamp for TimeZone API.
                    utc_time = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    posix_time = time.mktime(utc_time.timetuple())

                    # Our messages are in a comma-separated string.
                    #Split into a list
                    data_list = msg.split(",")
                    #[START extract]
                    # Extract latitude,longitude for input into Google Maps API calls.
                    latitude = float(data_list[1])
                    longitude = float(data_list[2])

                    # Construct a row object that matches the BigQuery table schema.
                    row = { 'VehicleID': data_list[0], 'UTCTime': None, 'Offset': 0, 'Address':"", 'Zipcode':"", 'Speed':data_list[3], 'Bearing':data_list[4], 'Elevation':None, 'Latitude':latitude, 'Longitude': longitude }

                    # Maps API Geocoding has a daily limit - this lets us limit API calls during development.
                    if geocode_counter <= geocode_limit:

                        # Reverse geocode the latitude, longitude to get street address, city, region, etc.
                        address_list = reverse_geocode(gmaps, latitude, longitude)
                    # [END extract]
                        #Save the formatted address for insert into BigQuery.
                        if(len(address_list) > 0):
                            row["Address"] = extract_address(address_list, "formatted_address")
                            #extract the zip or postal code if one is returned
                            row["Zipcode"] = extract_component(address_list, "postal_code")

                        # Increment counter - in case you want to limit daily geocodes.
                        geocode_counter += 1

                        # get elevation
                        row["Elevation"] = get_elevation(gmaps, latitude, longitude)

                        # Get the timezone, pass in original timestamp in case DST applied at that time.
                        timezone = get_timezone(gmaps, latitude, longitude, posix_time)

                        # Store DST offset so can display/query UTC time as local time.
                        if(timezone["rawOffset"] is not None):
                            row["Offset"] = get_local_time(timezone)

                        row["UTCTime"] = ts
                        # [START saverow]
                        # save a row to BigQuery
                        result = stream_row_to_bigquery(bq, row)
                        # [END saverow]

                        # Addresses can contain non-ascii characters, for simplicity we'll replace non ascii characters.
                        # This is just for command line output.
                        addr = row['Address'].encode('ascii', 'replace')
                        msg = "Appended one row to BigQuery."
                        print msg
                        msg = "Address: {0}".format(addr)
                        print msg
                        msg = "Elevation: {0} metres".format(row["Elevation"])
                        print msg
                        msg = "Timezone: {0}".format(timezone["timeZoneId"])
                        print msg
                        print " "
                    else:
                        time.sleep(wait_timeout)
                        geocode_counter = 0
                        print "counter reset"

                    # Get the message's ack ID.
                    ack_ids.append(received_message.get('ackId'))

            # Create a POST body for the acknowledge request.
            ack_body = {'ackIds': ack_ids}

            # Acknowledge the message.
            client.projects().subscriptions().acknowledge(
                subscription=subscription, body=ack_body).execute()



if __name__ == '__main__':
            main(sys.argv)
