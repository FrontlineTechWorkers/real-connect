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

DEBUG_DIAL_NUMBER = os.environ.get('DEBUG_DIAL_NUMBER')


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
    _say(r, u'你好！呢度係前線科技人員嘅，真 We Connect 熱線。請問喺十八區入面，你喺屬於邊一區？另外你亦可以講出區議員嘅名字')
    r.record(action=url_for('accept'), maxLength=6, playBeep=True, timeout=2)
    r.redirect(url_for('retry'))
    app.logger.info("evt=hello sid=%s from=%s", request.form['CallSid'], request.form['From'])

    return str(r), 200, {'Content-Type': 'text/xml'}

@app.route('/retry', methods=['POST', 'GET'])
def retry():
    r = twiml.Response()
    _say(r, u'請試多次，請讀出你嘅地區或者區議員名稱')
    r.record(action=url_for('accept'), maxLength=6, playBeep=True, timeout=2)
    r.hangup()

    app.logger.info("evt=retry sid=%s", request.form['CallSid'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/accept', methods=['POST', 'GET'])
def accept():
    recording_url = request.form['RecordingUrl']
    r = twiml.Response()
    _say(r, u'等等')
    r.redirect(url_for('recognize', RecordingUrl=recording_url))

    app.logger.info("evt=accept sid=%s", request.form['CallSid'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/recognize', methods=['POST', 'GET'])
def recognize():
    if 'RecordingUrl' in request.args:
        recording_url = request.args['RecordingUrl']
    else:
        recording_url = request.form['RecordingUrl']

    r = twiml.Response()
    try:
        text = _recognize(recording_url)
        name_matches = _lookup_name(text)
        district_matches = _lookup_district(text)
        name = None
        if u'老母' in text:
            _say(r, u'講還講唔好講粗口')
        if len(name_matches) > 0:
            name = name_matches[0]
            app.logger.info("evt=recognize_name sid=%s name=%s", request.form['CallSid'], name)
            _say(r, u'而家我會幫你打比')
        elif len(district_matches) > 0:
            district = district_matches[0]
            name = random.choice(district_dir[district])
            app.logger.info("evt=recognize_district sid=%s district=%s name=%s", request.form['CallSid'], district, name)
            _say(r, u'而家我會幫你打比')
            _say(r, district)
            _say(r, u'其中一位屬於特首選委既區議員')

        if name is not None:
            attr = name_dir[name]
            desc = attr.get('desc', name)
            tel = attr.get('tel')

            _say(r, desc)
            _say(r, u'咁你就可以盡情同佢 connect 番夠本啦，記住唔好收線啊！')

            if tel is not None and type(tel) is list and len(tel) > 0:
                if DEBUG_DIAL_NUMBER is None:
                    tel = tel[0]
                else:
                    tel = DEBUG_DIAL_NUMBER

                _say(r, u'佢既電話係：{}'.format(''.join([' ' + d for d in tel])))
                r.dial(tel)
            else:
                _say(r, u'找不到電話號碼')

            r.hangup()
        else:
            _say(r, u'我搵唔到呢個名')
            r.redirect(url_for('retry'))
    except ValueError:
        _say(r, u'我聽唔到你講乜野')
        r.redirect(url_for('retry'))

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    app.logger.exception('evt=error err=%s', e)
    r = twiml.Response()
    _say(r, u'唔好意思，系統發生咗啲故障，請遲啲再打過黎啦')
    r.hangup()
    return str(r), 200, {'Content-Type': 'text/xml'}


_load_directory()

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)