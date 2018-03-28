import ee

def initialize_google_earth_engine():
    EE_ACCOUNT = 'vegetatie-monitor@appspot.gserviceaccount.com'
    EE_PRIVATE_KEY_FILE = 'privatekey.json'

    # Initialize the EE API.
    # Use our App Engine service account's credentials.
    EE_CREDENTIALS = ee.ServiceAccountCredentials(EE_ACCOUNT,
                                                  EE_PRIVATE_KEY_FILE)
    ee.Initialize(EE_CREDENTIALS)


initialize_google_earth_engine()

from . import api  # initialize EE first

if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    api.app.run(host='127.0.0.1', port=8080, debug=True)
