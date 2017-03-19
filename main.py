# -*- coding: utf-8 -*-
import random
import logging
import os
import time
import threading
import urllib2
import wave
import yaml


from flask import Flask, app, request, url_for
from twilio import twiml, TwilioRestException
from twilio.rest import TwilioRestClient
from google.cloud import speech


DIRECTORY_FILE = 'DC_EC_Members.yaml'


TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']


app = Flask(__name__)
random.seed()


name_dir = None
district_dir = None
speech_context = []


def _load_directory():
    global name_dir, district_dir
    with open(DIRECTORY_FILE, 'r') as f:
        name_dir = yaml.load(f)
        district_dir = dict()
        for name, attr in name_dir.iteritems():
            speech_context.append(name)
            district = attr['district']
            if district in district_dir:
                district_dir[district].append(name)
            else:
                speech_context.append(district)
                district_dir[district] = [name]
        app.logger.error("evt=load_directory loaded=%d", len(name_dir))


def _recognize(recording_url):
    content = None
    wav = None


    try:
        for i in range(4):
            try:
                content = urllib2.urlopen(recording_url)
            except HTTPError as e:
                app.logger.warn("even=fetch_recording_error sid=%s recording_url=%s err=%s", request.form['CallSid'], recording_url, e)
                time.sleep(0.5)

        wav = wave.open(content, 'r')
        encoding = 'LINEAR16'
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

        client = speech.Client()
        sample = client.sample(encoding=encoding, sample_rate=sample_rate, content=frames)
        results = sample.sync_recognize(max_alternatives=1, language_code='zh-HK', speech_context=speech_context)
        app.logger.info("even=recognize_success sid=%s recording_url=%s transcript=%s confidence=%s", request.form['CallSid'], recording_url, results[0].transcript, results[0].confidence)

        return results[0].transcript
    except Exception as e:
        app.logger.info("evt=recognize_fail sid=%s recording_url=%s err=%s", request.form['CallSid'], recording_url, e)
        raise
    finally:
        # Clean up
        t = threading.Thread(target=_delete_recording, args=(recording_url,))
        t.start()

        if content != None:
            content.close()
        if wav != None:
            wav.close()


def _delete_recording(recording_url):
    sid = recording_url[recording_url.rindex('/') + 1:]
    client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        client.recordings.delete(sid)
        app.logger.info("evt=delete_recording_success sid=%s", sid)
    except TwilioRestException as e:
        app.logger.warn("evt=delete_recording_fail sid=%s", sid)


def _say(r, message):
    r.say(message, voice='alice', language='zh-HK')


def _lookup_name(text):
    return filter(lambda key: key in text, name_dir)


def _lookup_district(text):
    return filter(lambda key: key in text, district_dir)


@app.route('/', methods=['POST', 'GET'])
def hello():
    r = twiml.Response()
    _say(r, u'你好！呢度係前線科技人員設立嘅 真 WeConnect 熱線。請講出你喺18區入面，係屬於邊一區，或者講一個區議員嘅名字。')
    r.record(action=url_for('recognize'), maxLength=10, playBeep=False, timeout=3)
    r.redirect(url_for('retry'))
    app.logger.info("evt=hello sid=%s from=%s", request.form['CallSid'], request.form['From'])

    return str(r), 200, {'Content-Type': 'text/xml'}

@app.route('/retry', methods=['POST', 'GET'])
def retry():
    _say(r, u'請講出你區名，或者一個區議員嘅名。')
    r.record(action=url_for('recognize'), maxLength=10, playBeep=False, timeout=3)
    r.hangup()

    app.logger.info("evt=retry sid=%s", request.form['CallSid'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/recognize', methods=['POST', 'GET'])
def recognize():
    recording_url = request.form['RecordingUrl']

    r = twiml.Response()
    try:
        text = _recognize(recording_url)
        name_matches = _lookup_name(text)
        district_matches = _lookup_district(text)
        name = None
        if len(name_matches) > 0:
            _say(r, u'收到。而家我會幫你打比')
            name = name_matches[0]
        elif len(district_matches) > 0:
            _say(r, u'收到。而家我會幫你打比其中一位屬於特首選委既')
            _say(r, district_matches[0])
            _say(r, u'區議員')
            name = random.choice(district_dir[district_matches[0]])

        if name is not None:
            attr = name_dir[name]
            desc = attr.get('desc', name)
            tel = attr.get('tel')

            _say(r, desc)
            _say(r, u'咁你就可以盡情同佢connect番夠本啦，記住唔好收線啊！')

            # Debug
            if tel is not None and type(tel) is list and len(tel) > 0:
                tel = tel[0]
            else:
                tel = u'找不到'

            _say(r, u'佢既電話係：{}'.format(tel))
            r.hangup()
        else:
            _say(r, u'我搵唔到呢個名，請試多次。')
            r.redirect(url_for('retry'))
    except ValueError:
        _say(r, u'我唔係好知你講乜野，請試多次。')
        r.redirect(url_for('retry'))

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    app.logger.exception('evt=error err=%s', e)
    r = twiml.Response()
    _say(r, u'唔好意思，系統發生咗啲故障，請遲啲再打過黎啦。')
    r.hangup()
    return str(r), 200, {'Content-Type': 'text/xml'}


_load_directory()

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)