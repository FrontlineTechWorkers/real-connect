# -*- coding: utf-8 -*-
import logging
import os
import urllib2
import wave

from flask import Flask, app, request, url_for
from twilio import twiml
from google.cloud import speech


TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']


app = Flask(__name__)


def _recognize(recording_url):
    content = None
    wav = None
    try:
        content = urllib2.urlopen(recording_url)
        wav = wave.open(content, 'r')
        encoding = 'LINEAR16'
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

        client = speech.Client()
        sample = client.sample(encoding=encoding, sample_rate=sample_rate, content=frames)
        results = sample.sync_recognize(max_alternatives=1, language_code='zh-HK')
        app.logger.info("even=recognize_success recording_url=%s transcript=%s confidence=%f", recording_url, results[0].transcript, results[0].confidence)
        return results[0].transcript
    except Exception as e:
        app.logger.info("evt=recognize_fail sid=%s recording_url=%s err=%s", request.form['CallSid'], recording_url, e)
        raise
    finally:
        if content != None:
            content.close()
        if wav != None:
            wav.close()


def _delete_recording(recording_url):
    sid = recording_url[recording_url.rindex('/') + 1:]
    client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.recordings.delete(sid)
    logging.debug("evt=recording_deleted sid=%s", sid)


def _say(r, message):
    r.say(message, voice='alice', language='zh-HK')


@app.route('/hello', methods=['POST', 'GET'])
def hello():
    r = twiml.Response()
    _say(r, u'歡迎致電前線科技人員，真 Connect。請讀出你既區議會分區')
    r.record(action=url_for('recognize'), maxLength=10, playBeep=False, timeout=3)
    _say(r, u'請讀出你既區議會分區')
    r.record(action=url_for('recognize'), maxLength=10, playBeep=False, timeout=3)
    r.hangup()

    app.logger.info("evt=hello sid=%s from=%s", request.form['CallSid'], request.form['From'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/recognize', methods=['POST', 'GET'])
def recognize():
    recording_url = request.form['RecordingUrl']

    r = twiml.Response()
    try:
        result = _recognize(recording_url)
        _say(r, u'你講既係' + result)
        r.hangup()
    except ValueError:
        _say(r, u'我唔係好知你講乜野，請試多次。')
        r.redirect(url_for('hello', intro=False))

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('evt=error err=%s', e)
    r = twiml.Response()
    _say(r, u'唔好意思，系統發生咗啲故障，請遲啲再打過黎啦。')
    r.hangup()
    return str(r), 200, {'Content-Type': 'text/xml'}


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)