# -*- coding: utf-8 -*-
import logging
import os
import urllib2
import wave

from flask import Flask, app, request
from twilio import twiml
from twilio.rest import TwilioRestClient
from google.cloud import speech


app = Flask(__name__)


def _fetch_sample(speech_client, recording_url):
    content = urllib2.urlopen(recording_url)
    wav = wave.open(content, 'r')
    encoding = 'LINEAR16'
    sample_rate = wav.getframerate()
    frames = wav.readframes(wav.getnframes())
    return speech_client.sample(encoding=encoding, sample_rate=sample_rate, content=frames)


@app.route('/hello', methods=['POST', 'GET'])
def hello():
    app.logger.info("action=hello")

    r = twiml.Response()
    r.say(u'歡迎致電前線科技人員，真 Connect。請讀出你既區議會分區', voice='alice', language='zh-HK')
    r.record(action="/recognize", maxLength=20, playBeep=False)
    r.redirect("/hello", method='POST')

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/recognize', methods=['POST', 'GET'])
def recognize():
    recording_url = request.form['RecordingUrl']
    app.logger.info("action=recognize recording_url=%s", recording_url)

    r = twiml.Response()
    client = speech.Client()
    try:
        sample = _fetch_sample(client, recording_url)
        results = sample.sync_recognize(max_alternatives=1, language_code='zh-HK')
        app.logger.info("action=recognize transcript=%s confidence=%f", results[0].transcript, results[0].confidence)
        result = results[0].transcript
        r.say(u'你講既係' + result, voice='alice', language='zh-HK')
        r.hangup()
    except ValueError:
        r.say(u'唔好意思，我唔係好知你講乜野，請試多次。', voice='alice', language='zh-HK')
        r.record(action="/recognize", maxLength=20, playBeep=False)
        r.say(u'唔好意思，請遲啲再打過黎啦。', voice='alice', language='zh-HK')
        r.hangup()

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    r.say
    r = twiml.Response()

    r.say(u'唔好意思，我地發生咗錯誤，請遲啲再打過黎啦。', voice='alice', language='zh-HK')
    r.hangup()

    return str(r), 200, {'Content-Type': 'text/xml'}


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)