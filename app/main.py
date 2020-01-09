import sys, os
import base64

sys.path.append(os.getcwd())

import ee


def initialize_google_earth_engine():
    EE_ACCOUNT = 'vegetatie-monitor@appspot.gserviceaccount.com'
    EE_PRIVATE_KEY_FILE = 'privatekey.json'

    # if 'privatekey.json' is defined in environmental variable - write it to file
    if 'key' in os.environ:
        print('Writing privatekey.json from environmental variable ...')
        content = base64.b64decode(os.environ['key']).decode('ascii')

        with open(EE_PRIVATE_KEY_FILE, 'w') as f:
            f.write(content)

    # Initialize the EE API.
    # Use our App Engine service account's credentials.
    EE_CREDENTIALS = ee.ServiceAccountCredentials(EE_ACCOUNT,
                                                  EE_PRIVATE_KEY_FILE)
    ee.Initialize(EE_CREDENTIALS)

    # delete temporary private key file
    if 'key' in os.environ:
        os.unlink(EE_PRIVATE_KEY_FILE)
 

initialize_google_earth_engine()


FIREBASE_PRIVATE_KEY_FILE = 'privatekey-firestore.json'

# write Firebase service account file
if 'key_firebase' in os.environ:
    print('Writing privatekey-firestore.json from environmental variable ...')
    content = base64.b64decode(os.environ['key_firebase']).decode('ascii')

    with open(FIREBASE_PRIVATE_KEY_FILE, 'w') as f:
        f.write(content)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = FIREBASE_PRIVATE_KEY_FILE


# from . import api  # initialize EE first
from api import app

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    # app.run(host='127.0.0.1', port=8081, debug=True, ssl_context='adhoc')
    app.run(host='127.0.0.1', port=8081, debug=True)
