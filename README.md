# 真・WeConnect [![Build Status](https://travis-ci.org/FrontlineTechWorkers/real-connect.svg?branch=master)](https://travis-ci.org/FrontlineTechWorkers/real-connect)

Developed by [前線科技人員](https://www.facebook.com/FrontlineTechWorkersConcernGroup/photos/a.907682852604782.1073741829.907020282671039/1450926928280369/)

> 今個星期日就係特首選舉，部分區議員身兼選委所以會有份投票。區議員嘅職責之一係聽市民意見，咁到底佢地會唔會投你想投個位呢？即刻打 5819 2689，講出你住係邊區，語音辨識系統就會幫你搵出你嗰區有邊個區議員係選委，再將你嘅電話駁去佢個度，等你親自問下佢、同佢傾下啦。

## Setup

Before you can run or deploy the app, you will need to do the following:

1. Use the [Google Developers Console](https://console.developer.google.com) to create a project/app id. (App id and project id are identical)

2. Enable [Cloud Speech API](https://cloud.google.com/speech/docs/getting-started).

3. [Create a Twilio Account](http://ahoy.twilio.com/googlecloudplatform).

4. Install the [Google Cloud SDK](https://cloud.google.com/sdk/), including the [gcloud tool](https://cloud.google.com/sdk/gcloud/), and [gcloud app component](https://cloud.google.com/sdk/gcloud-app).

5. Setup the gcloud tool.

   ```
   gcloud init
   ```

6. [Install ngork](https://www.twilio.com/blog/2015/09/6-awesome-reasons-to-use-ngrok-when-testing-webhooks.html)

## Run Locally

1. Get credentials used in calling Google APIs.

   ```
   gcloud auth application-default login
   ```

2. Configure your Twilio settings in the environment variables.

    ```
    export TWILIO_ACCOUNT_SID=[your-twilio-accoun-sid]
    export TWILIO_AUTH_TOKEN=[your-twilio-auth-token]
    ```

3. Create a virtualenv, install dependencies, and run the sample:

   ```
   virtualenv env
   source env/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

4. Start ngrok to allow Twilio to connect webhooks on your local server.

   ```
   ngrok http 8080
   ```

5. Create a number on Twilio, if you haven't already. Configure the voice request URL to be `http://random-name.ngrok.io/`.

## Deploying (Google App Engine)

1. Copy `app.yaml.sample` to `app.yaml`. Configure your Twilio settings in the environment variables section in `app.yaml`.

   ```
   cp app.yaml.sample app.yaml
   ```

2. Use gcloud to deploy your app.

   ```
   gcloud app deploy
   ```

3. Create a number on Twilio, if you haven't already. Configure the voice request URL to be `https://your-app-id.appspot.com/`.
