from flask import Flask, jsonify, request, redirect
from flasgger import Swagger

import ee

import config

# Initialize the EE API.
# Use our App Engine service account's credentials.
EE_CREDENTIALS = ee.ServiceAccountCredentials(config.EE_ACCOUNT, config.EE_PRIVATE_KEY_FILE)
ee.Initialize(EE_CREDENTIALS)

app = Flask(__name__)
swagger = Swagger(app, template_file='api.yaml')

band_names = {
    's2': ['B2', 'B3', 'B4', 'B8', 'B12'],
    'readable': ['blue', 'green', 'red', 'nir', 'swir']
}


def get_sentinel_image(region, dateBegin, dateEnd, bands):
    images = ee.ImageCollection('COPERNICUS/S2') \
        .select(band_names['s2'], band_names['readable']) \
        .filterBounds(region)

    if dateBegin:
        if not dateEnd:
            dateEnd = dateBegin.advance(1, 'day')

        images = images.filterDate(dateBegin, dateEnd)

    image = ee.Image(images.mosaic()).divide(10000)

    vis = {'min': 0.05, 'max': [0.35, 0.35, 0.45], 'gamma': 1.4, 'bands': bands}

    image = image.visualize(**vis)

    return image


def get_ndvi(region, dateBegin, dateEnd):
    pass


def get_landuse(region, dateBegin, dateEnd):
    pass


def get_landuse_vs_legger(region, dateBegin):
    pass


maps = {
    'satellite': get_sentinel_image,
    'ndvi': get_ndvi,
    'landuse': get_landuse,
    'landuse-vs-legger': get_landuse_vs_legger
}


@app.route('/map/<string:id>/', methods=['POST'])
def get_map(id):
    """
    Returns maps processed by Google Earth Engine
    """

    json = request.get_json()

    region = json['region']

    dateBegin = json['dateBegin']
    dateEnd = json['dateEnd']

    dateBegin = dateBegin or ee.Date(dateBegin)
    dateEnd = dateEnd or ee.Date(dateEnd)

    bands = json['bands']

    image = maps[id](region, dateBegin, dateEnd, bands)

    map = image.getMapId()
    map_id = map['mapid']
    token = map['token']

    url = 'https://earthengine.googleapis.com/map/' \
          '{0}/{{z}}/{{x}}/{{y}}?token={1}' \
        .format(map_id, token)

    results = {'url': url}

    return jsonify(results)


@app.route('/')
def root():
    return redirect(request.url + 'apidocs')


if __name__ == '__main__':
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
