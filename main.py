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
DISTRICTS_FILE = 'DC_Districts.yaml'
SCRIPT_FILE = 'scripts.yaml'


TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']


COUNTRY_PREFIX = os.environ.get('RC_COUNTRY_PREFIX', '+852')
DEBUG_DIAL_NUMBER = os.environ.get('RC_DEBUG_DIAL_NUMBER')


app = Flask(__name__)
random.seed()


name_dir = None
district_dir = None
district_alias_dir = None
script_map = dict()
speech_context = []


def _recognize(recording_url):
    content = None
    wav = None

    try:
        for i in range(4):
            try:
                content = urllib2.urlopen(recording_url)
            except urllib2.HTTPError as e:
                app.logger.warn("evt=fetch_recording_error sid=%s recording_url=%s err=%s", request.form['CallSid'], recording_url, e)
                time.sleep(0.5)
        if content is None:
            raise ValueError("Fetch recording failed")

        wav = wave.open(content, 'r')
        encoding = 'LINEAR16'
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

        client = speech.Client()
        sample = client.sample(encoding=encoding, sample_rate=sample_rate, content=frames)
        results = sample.sync_recognize(max_alternatives=1, language_code='zh-HK', speech_context=speech_context)
        app.logger.info("evt=recognize_success sid=%s recording_url=%s transcript=%s confidence=%s", request.form['CallSid'], recording_url, results[0].transcript, results[0].confidence)

        return results[0].transcript
    except Exception as e:
        app.logger.warn("evt=recognize_fail sid=%s recording_url=%s err=%s", request.form['CallSid'], recording_url, e)
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
    if message in script_map:
        script_info = script_map[message]
        if 'audio' in script_info:
            r.play(url_for('static', filename='audios/' + script_info['audio']))
        elif 'text' in script_info:
            r.say(script_info['text'], voice='alice', language='zh-HK')
        else:
            app.logger.warn("evt=script_missing message=%s", message)
            r.say(message, voice='alice', language='zh-HK')
    else:
        r.say(message, voice='alice', language='zh-HK')

def _lookup_name(text):
    return filter(lambda key: key in text, name_dir)


def _lookup_district(text):
    return filter(lambda key: key in text, district_dir) +\
        [value for key, value in district_alias_dir.items() if key in text]


@app.route('/', methods=['POST'])
def hello():
    r = twiml.Response()
    _say(r, u'HELLO')
    r.record(action=url_for('accept'), maxLength=6, playBeep=True, timeout=2)
    r.redirect(url_for('retry'))
    app.logger.info("evt=hello sid=%s from=%s", request.form['CallSid'], request.form['From'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/retry', methods=['POST'])
def retry():
    r = twiml.Response()
    _say(r, 'TRY_AGAIN')
    r.record(action=url_for('accept'), maxLength=6, playBeep=True, timeout=2)
    r.hangup()

    app.logger.info("evt=retry sid=%s", request.form['CallSid'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/accept', methods=['POST'])
def accept():
    recording_url = request.form['RecordingUrl']
    r = twiml.Response()
    _say(r, 'PLEASE_WAIT')
    r.redirect(url_for('recognize', RecordingUrl=recording_url))

    app.logger.info("evt=accept sid=%s", request.form['CallSid'])

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/recognize', methods=['POST'])
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
            _say(r, 'NO_MOTHER')

        if len(name_matches) > 0:
            name = name_matches[0]
            app.logger.info("evt=match_name sid=%s name=%s", request.form['CallSid'], name)
            _say(r, 'WILL_CALL')
        elif len(district_matches) > 0:
            district = district_matches[0]
            name = random.choice(district_dir[district])
            app.logger.info("evt=match_district sid=%s district=%s name=%s", request.form['CallSid'], district, name)
            _say(r, 'WILL_CALL')
            _say(r, district)
            _say(r, 'FROM_DISTRICT')

        if name is not None:
            attr = name_dir[name]
            desc = attr.get('desc', name)
            tel = attr.get('tel')

            _say(r, desc)
            _say(r, 'DONT_HANG_UP')

            if tel is not None and type(tel) is list and len(tel) > 0:
                if DEBUG_DIAL_NUMBER is None:
                    tel = tel[0]
                else:
                    tel = DEBUG_DIAL_NUMBER

                _say(r, 'THE_NUMBER_IS')
                _say(r, ''.join([' ' + d for d in tel]))
                tel_with_prefix = COUNTRY_PREFIX + tel
                app.logger.info("evt=dial_start sid=%s name=%s tel=%s", request.form['CallSid'], name, tel_with_prefix)
                r.dial(tel_with_prefix, action=url_for('goodbye'))
            else:
                app.logger.info("evt=tel_not_found sid=%s name=%s", request.form['CallSid'], name)
                _say(r, 'TEL_NOT_FOUND')
                r.redirect(url_for('retry'))

            r.hangup()
        else:
            app.logger.warn("evt=match_miss sid=%s text=%s", request.form['CallSid'], text)
            _say(r, 'PLACE_NOT_FOUND')
            r.redirect(url_for('retry'))
    except ValueError:
        _say(r, 'CANNOT_HEAR')
        r.redirect(url_for('retry'))

    return str(r), 200, {'Content-Type': 'text/xml'}


@app.route('/goodbye', methods=['POST'])
def goodbye():
    status = request.form['DialCallStatus']
    duration = request.form.get('DialCallDuration', '0')
    app.logger.info("evt=dial_end sid=%s status=%s duration=%s", request.form['CallSid'], status, duration)
    r = twiml.Response()
    r.hangup()
    return str(r), 200, {'Content-Type': 'text/xml'}


@app.errorhandler(500)
def server_error(e):
    # Log the error and stacktrace.
    app.logger.exception('evt=error err=%s', e)
    r = twiml.Response()
    _say(r, 'ERROR_OCCURRED')
    r.hangup()
    return str(r), 200, {'Content-Type': 'text/xml'}


@app.before_first_request
def setup_logging():
    if not app.debug:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] {%(pathname)s:%(lineno)d} [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


@app.before_first_request
def load_script():
    global script_map
    with open(SCRIPT_FILE, 'r') as f:
        script_map = yaml.load(f)
    app.logger.info("evt=load_script scripts=%d", len(script_map))


@app.before_first_request
def load_directory():
    global name_dir, district_dir, district_alias_dir, speech_context
    with open(DIRECTORY_FILE, 'r') as f:
        name_dir = yaml.load(f)
        district_dir = dict()
        district_alias_dir = dict()
        for name, attr in name_dir.iteritems():
            speech_context.append(name)
            district = attr['district']
            if district in district_dir:
                district_dir[district].append(name)
            else:
                speech_context.append(district)
                district_dir[district] = [name]
    with open(DISTRICTS_FILE, 'r') as f:
        districts = yaml.load(f)
        for district, attr in districts.iteritems():
            for alt in attr['alt']:
                speech_context.append(alt)
                district_alias_dir[alt] = district
    speech_context = speech_context[:500]
    app.logger.info("evt=load_directory names=%d districts=%d district_aliases=%d", len(name_dir), len(district_dir), len(district_alias_dir))


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)