<!--


-->

This tutorial shows how to use Google Cloud Platform to build an app that
receives telemetric data about geolocation, processes it, and then stores the
processed and transformed data for further analysis. 

The instructions in this readme show you how to run the tutorial by using
Google Cloud Shell with Docker. You can find a version of this tutorial that
uses your own development environment, without Docker, [on the Google Cloud
Platform website](https://cloud.google.com/solutions/reverse-geocoding-geolocation-telemetry-cloud-maps-api).

Cloud Shell provides a ready runtime environment and can save you several steps
and some time. However, Cloud Shell times out after 60 minutes of inactivity
and can cost you some repeated work, if that happens. For example, anything
copied to the <code>/tmp</code> directory will be lost.

Docker provides some automation in deployment that can also make the tutorial
easier to run and save you time. However, if you're not familiar with Docker,
or simply want to see every step in action, you might prefer to run through the
full, manual tutorial steps yourself. 

The tutorial:

  * Starts with traffic data stored in CSV files.
  * Processes messages in a Google Cloud Pub/Sub queue.
  * Reverse geocodes latitude and longitude to convert the coordinates to a street
address.
  * Calculates the elevation above sea level.
  * Converts from Coordinated Universal Time (UTC) to local time by querying which
timezone each location is in. 
  * Writes the data, with the added geographic contextual information, to a
BigQuery dataset for your analysis.
  * Visualizes the data as heat maps superimposed over a map of the San Diego metro
area.

# Costs

This tutorial uses billable components of Google Cloud Platform, including:

  * 1 Compute Engine virtual machine (g1-small)
  * Google Cloud Storage Standard (5 GB)
  * Google BigQuery (5 GB storage, 5 GB streaming inserts)
  * Google Cloud Pub/Sub (< 200k operations)
  * Google Maps API

The cost of running this tutorial will vary depending on run time. Use the [pricing calculator estimate](https://cloud.google.com/products/calculator/#id=11387bdd-be66-4083-b814-01176faa20a0) to see a cost estimate based on your projected usage. New Cloud Platform users
may be eligible for a [free trial](https://cloud.google.com/free-trial).

The Maps API standard plan offers a free quota and pay-as-you-go billing after
the quota has been exceeded. If you have an existing license for the Maps API
or have a Maps APIs Premium Plan, [see the documentation first](https://developers.google.com/maps/documentation/javascript/get-api-key#premium-auth) for some important notes. You can purchase a Maps APIs Premium Plan for higher
quotas.  

You must have a Maps for Work license for any application that restricts
access, such as behind a firewall or on a corporate intranet. For more details
about Google Maps API pricing and plans, see [the online documentation](https://developers.google.com/maps/pricing-and-plans/).

# Before you begin

  1. [Select or create a Cloud Platform Console project](https://console.cloud.google.com/project).
  2. [Enable billing for your project](https://console.cloud.google.com/billing).
  3. Click the following link to enable the required Cloud Platform APIs. If
prompted, be sure to select the project you created in step 1.

  [Enable APIs](https://console.developers.google.com/start/api?target=%22console%22&id=bigquery,pubsub,storage_component,storage_api,geocoding_backend,elevation_backend,timezone_backend,maps_backend)

  

  These APIs include:

     * BigQuery API
     * Pubsub API
     * Google Cloud Storage
     * Google Maps Geocoding API
     * Google Maps Elevation API
     * Google Maps Time Zone API
     * Google Maps Javascript API

# Creating credentials

For this tutorial, you'll need the following credentials:

  * A Google Maps API<em> server key</em>.
  * A Maps API <em>browser key</em>.
  * A credentials file for the <em>service account key</em>.
  * An OAuth 2.0 <em>client ID</em>.

## Google Maps API credentials

If you don't already have them, you'll need Google Maps API keys. 

### Get a server key

  1. Click the following link to open the Cloud Console in the <strong>Credentials</strong> page. If you have more than one project, you might be prompted to select a
project. 

 [Create credentials](https://console.developers.google.com/apis/credentials?target=%22console%22)

  2. Click <strong>Create credentials</strong> > <strong>API key</strong> > <strong>Server key</strong>.
  3. Name the key "Maps tutorial server key".
  4. Click <strong>Create</strong>.
  5. Click <strong>Ok</strong> to dismiss the dialog box that shows you the new key. You can retrieve your
keys from the Cloud Console anytime.
  6. Stay on the page.

### Get a browser key

The browser key is a requirement for using the Maps Javascript API. Follow
these steps:

  1. Click <strong>Create credentials</strong> and then select <strong>API key</strong>.
  2. Click <strong>Browser key</strong>.
  3. Name the key "Maps tutorial browser key".
  4. Click <strong>Create</strong>.
  5. Click <strong>Ok</strong> to dismiss the dialog box that shows you the new key.
  6. Stay on the page.

<strong>Important:</strong> Keep your API keys secure. Publicly exposing your credentials can result in
your account being compromised, which could lead to unexpected charges on your
account. To keep your API keys secure, [follow these best practices](https://support.google.com/cloud/answer/6310037).

## Service account credentials

Create service account credentials and download the JSON file. Follow these
steps:

  1. Click <strong>Create credentials</strong> and then select <strong>Service account key</strong>.
  2. Select <strong>New service account</strong>.
  3. Name the account "Maps tutorial service account".
  4. The key type is <strong>JSON</strong>.
  5. Click <strong>Create</strong>.
  6. The Cloud Console automatically downloads to your computer the JSON file that
contains the service account key. Note the location of this file.
  7. Click <strong>Close</strong> to dismiss the dialog box that shows you the new key. If you need to, you can
retrieve the key file later.

### Upload the JSON file

You must upload the service account credential file to a Google Cloud Storage
bucket so that you can transfer it to Cloud Shell in an upcoming step.

  1. In the Cloud Platform Console, <strong>[go to the Cloud Storage browser.](https://console.cloud.google.com/storage/browser)</strong>
  2. Click <strong>Create bucket</strong>.
  3. In the <strong>Create bucket</strong> dialog, specify the following attributes:
     1. A unique bucket name, subject to the [bucket name requirements](https://cloud-dot-devsite.googleplex.com/storage/docs/bucket-naming#requirements).
     2. A [storage class](https://cloud-dot-devsite.googleplex.com/storage/docs/storage-classes).
     3. A location where bucket data will be stored.
  4. Click <strong>Create</strong>.
  5. In the Cloud Console, click the name of your new bucket.
  6. Click <strong>Upload files</strong>.
  7. Browse to the JSON file and confirm the upload.

## OAuth 2.0 client ID

Create a client ID that you can use to authenticate end-user requests to
BigQuery. Follow these steps:

  1. Find the IPv4 address of your computer. For example, in your browser, view a
page such as [http://ip-lookup.net](http://ip-lookup.net). If your computer is on a corporate intranet, you need to get the address from
your operating system. For example, run <code>ifconfing</code> on Linux or <code>ipconfig -all</code> on Windows.
  1. In the Cloud Console, click <strong>Create credentials</strong> and then select <strong>OAuth client ID</strong>.
  2. Select <strong>Web application</strong>.
  3. In the <strong>Name</strong> field, enter "Maps API client ID".
  4. In the <strong>Restrictions</strong> section, in <strong>Authorized JavaScript origins</strong>, add the following two origin URLs. Replace [YOUR\_IP\_ADDRESS] with the IPv4
address of your computer.


```
http://[YOUR_IP_ADDRESS]:8000
https://[YOUR_IP_ADDRESS]:8000
```
  Adding these URLs enables an end user to access BigQuery data through
JavaScript running in a browser. You need this authorization for an upcoming
section of the tutorial, when you display a visualization of data on a map in
your web browser.

  5. Click <strong>Save</strong> to generate the new client ID.

# Setting up Cloud Pub/Sub

Cloud Pub/Sub is the messaging queue that handles moving the data from CSV
files to BigQuery. You'll need to create a <em>topic</em>, which publishes the messages, and a <em>subscription</em>, which receives the published messages. 

## Create a Cloud Pub/Sub topic

The topic publishes the messages. Follow these steps to create the topic:

  1. Browse to the Pub/Sub topic list page in the Cloud Console:

[Open the Pub/Sub page](https://console.developers.google.com/cloudpubsub/topicList)

  2.  Click <strong>Create topic</strong>. A dialog box opens.
  3.  In the <strong>Name</strong> field, add "traffic" to the end of the path that is provided for you. The path
is determined by the system. You can provide only a name for the topic.
  4. Click <strong>Create</strong>. The dialog box closes.
  5. Stay on the page.

## Creating a Cloud Pub/Sub subscription

The subscription receives the published messages. Follow these steps to create
the subscription:

  1. In the topic list, in the row that contains the <code>traffic</code> topic, click the downward arrow  on the right-hand end of the row.
  2. Click <strong>New subscription</strong> to open the <strong>Create a new subscription</strong> page.  
  3. In the <strong>Subscription name</strong> field, add "mysubscription" to the end of the path that is provided for you.
  4. Set the <strong>Delivery Type</strong> to <strong>Pull</strong>, if it isn't already set by default.
  5. Click <strong>Create</strong>.

# Preparing to run the code

Follow these steps to prepare to run the code.

  1. Open Cloud Shell. In the Cloud Platform console, in the upper-right corner,
click the <strong>Activate Google Cloud Shell</strong> icon.
  2. In Cloud Shell, clone this repository.
  3. Change directory to <code>resources</code>:

  <code>cd geo\_bq/resources</code>

  1.  Edit <code>setup.yaml</code>. Use your favorite command-line text editor. 

  1. For <code>PROJECT\_ID</code>, replace <code>your-project-id</code> with your project's ID string. Keep the single quotation marks in this and all
other values that you replace.
  2. For <code>DATASET\_ID</code>, don't change <code>sandiego\_freeways</code>.
  3. For <code>TABLE\_ID</code>, don't change <code>geocoded\_journeys.</code>
  4. For <code>PUBSUB\_TOPIC</code>, replace <code>your-project-id</code> with your project's ID string.
  5. For <code>ROOTDIR</code>, replace the provided path with <code>/tmp/creds/data</code>.
  6. For <code>SUBSCRIPTION</code>, replace <code>your-project-id</code> with your project's ID string.
  7. For <code>MAPS\_API\_KEY</code>, replace <code>Your-server-key </code>with the server key you created. You can see your credentials by clicking the
following link:

[View credentials](https://console.developers.google.com/apis/credentials?target=%22console%22)

  8. Save and close the file.

  1. Run the following command:


```
bash setup.sh
```
The <code>setup.sh</code> script performs the following steps for you:

  * Creates a BigQuery dataset and a table schema to receive the traffic data.
  * Creates a directory structure, <code>/tmp/creds/data</code>, that you use to store your service account credentials (the JSON file you
uploaded to your bucket) and the traffic data.
  * Copies the data files from your GitHub clone to the data directory.

  1. Change directory to <code>/tmp/creds</code>:

  <code>cd /tmp/creds</code>

  1. Copy your credentials file. Run the following command. Replace [YOUR\_BUCKET]
with the name of your Cloud Storage bucket and [YOUR\_CREDENTIALS\_FILE] with
the name of the file:

gsutil cp gs://[YOUR\_BUCKET]/[YOUR\_CREDENTIALS\_FILE].json .

# Pushing data to Cloud Pub/Sub

Next, run the code to push the traffic data to Cloud Pub/Sub. Run the following
command. Replace [YOUR\_CREDENTIALS\_FILE] with the name of the file.

docker run -e
"GOOGLE\_APPLICATION\_CREDENTIALS=/tmp/creds/[YOUR\_CREDENTIALS\_FILE].json"
--name
map-push -v /tmp/creds:/tmp/creds
gcr.io/cloud-solutions-images/map-pushapp

After Docker finishes initializing, you should see repeated lines of output
like this one:


```
Vehicle ID: 1005, location: 33.2354833333, -117.387343333; speed: 44.698 mph,
bearing: 223.810 degrees
```
It can take some time to push all the data to Pub/Sub.

# Loading the data into BigQuery

BigQuery pulls the data by using the Cloud Pub/Sub subscription. To get it
going, run the following command. Replace [YOUR\_CREDENTIALS\_FILE] with the
name of the file. 

docker run -e
"GOOGLE\_APPLICATION\_CREDENTIALS=/tmp/creds/[YOUR\_CREDENTIALS\_FILE].json"
--name
map-app -v /tmp/creds:/tmp/creds
gcr.io/cloud-solutions-images/map-pullapp

After Docker finishes initializing, you should see repeated lines of output
like this one:


```
Appended one row to BigQuery. Address: 11th St, Oceanside, CA 92058, USA
```
It can take some to pull all the data from the topic. When it’s done, the
terminal window will stop showing lines of output as it waits for further data.
You can exit the process at any time by pressing Control+C. If Cloud Shell
times out, you can simply click the <strong>reconnect</strong> link.

# Analyzing the data

Now that the you have transcoded and loaded the data into BigQuery, you can use
BigQuery to gain insights. This section of the tutorial shows you how to use
the BigQuery console run a few simple queries against this data.

  1. Open the [BigQuery Console](https://bigquery.cloud.google.com/queries/).
  2. Select the <strong>sandiego\_freeways</strong> database.
  1. Click the <strong>Compose Query</strong> button.
  2. In the <strong>New Query</strong> text box, enter the following query that produces average speed by zip code:


```
SELECT AVG(Speed) avg_speed, Zipcode FROM [sandiego_freeways.geocoded_journeys] 
WHERE Zipcode &lt;> ''
GROUP BY Zipcode ORDER BY avg_speed DESC
```
# Visualizing the data

You can use Google Maps to visualize the data you stored in BigQuery. This
tutorial shows you how to superimpose a heat map visualization onto a map of
the region. The heat map shows the volume of traffic activity captured in the
data in BigQuery.

To keep the tutorial straightforward, the provided example uses OAuth 2.0 to
authenticate the user for the BigQuery service. You could choose another
approach that might be better-suited for your scenario.  For example, you could
export query results from BigQuery and create a static map layer that doesn’t
require the end user to authenticate against BigQuery, or you could set up
authentication by using a service account and a proxy server. 

To show the data visualization, follow these steps.

## Modify <code>bqapi.html</code>

For these modifications, you need to use keys and credentials you created
earlier. You can see these values in the Cloud Console on the <strong>[Credentials](https://console.developers.google.com/apis/credentials)</strong> page.

  1. Make a copy of the file named <code>bqapi.html</code>. You can find the file in the following directory where you installed the
source code:

    


```
geo_bq/web/
```
  2. Open the file in a text editor.
  3. In the following <code>script</code> element, in the <code>src</code> attribute, replace <code>Your-Maps-API-Key</code> with your Google Maps API browser key:


```
&lt;script src="<a href="https://maps.googleapis.com/maps/api/js?libraries=visualization,drawing&key=Your-Maps-Api_browser-key">https://maps.googleapis.com/maps/api/js?libraries=visualization,drawing&key=</a>Your-Maps-API-Key"
```
  1. For the <code>clientId </code>variable, replace Your-Client-ID with the[ OAuth 2.0 client ID](https://docs.google.com/document/d/1AwDrzSgIgzEFj1Se5q3CsPKups8UTgKzPv4jNc3z0ic/edit#heading=h.cbxggavwji9j) you created earlier.  
  2. For the projectId variable, replace the value string, <code>Your-Project-ID</code>, with the your project ID.
  3. Save the file.

## Viewing the web page

You can use Cloud Shell to view the web page. Follow these steps:

  1. From the <code>geo\_bq/web</code> directory, run the following command to start the server:

  python -m SimpleHTTPServer 8080

  When the server is running, Cloud Shell prints the following message:

  <code>Serving HTTP on 0.0.0.0 port 8080 ...</code>

  1. In the top-left corner of Cloud Shell, click <strong>Web preview</strong> and then click <strong>Preview on port 8080</strong>. Cloud Shell opens a new browser tab that connects to the web server.
  2. In the new browser tab, note the origin URL. The origin URL has a format
similar to the following example, where [RANDOM\_NUMBER] could be any value:

  <u>https://8080-dot-[RANDOM\_NUMBER]-dot-devshell.appspot.com</u>

  1. In the Cloud Console, return to the <strong>[Credentials](https://console.developers.google.com/apis/credentials)</strong> page;

  1. Click the name of your OAuth 2.0 client ID.
  2. In the <strong>Restrictions</strong> section, add the origin URL you noted in the previous step. Do not add a port
number.

  The origin URL that you provide in this step tells OAuth 2.0 that it's safe to
accept requests from the Cloud Shell browser. Without this step, the web page
can't use script to access the data you loaded into BigQuery.

  3. Click <strong>Save</strong>.
  4. In the browser tab that Cloud Shell opened, click the link for <strong>bqapi.html</strong>. If your browser has a pop-up blocker, turn it off for this site. 
  5. In the pop-up window, follow the OAuth 2.0 authentication prompts. You won't
have to repeat this flow in this session if, for example, you reload the web
page.
  6. After the map has loaded, select the rectangle tool in the upper-left corner of
the map.
  7. Use the tool to draw a rectangle around the entire currently visible land mass
on the map.

The page shows a heat map. Exactly where the heat map regions display on the
map depends on the data you loaded into BigQuery.

For details about how the code works, see the tutorial on the Google Cloud
Platform site.

