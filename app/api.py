from flask import Flask, jsonify, redirect, request
from flasgger import Swagger
import ee

# create app
app = Flask(__name__)

# register specs
Swagger(app, template_file='api.yaml')

band_names = {
    's2': ['B2', 'B3', 'B4', 'B8', 'B12'],
    'readable': ['blue', 'green', 'red', 'nir', 'swir']
}


def to_date_time_string(millis):
    return ee.Date(millis).format('YYYY-MM-dd HH:mm')


def get_sentinel_images(region, date_begin, date_end):
    images = ee.ImageCollection('COPERNICUS/S2') \
        .select(band_names['s2'], band_names['readable']) \
        .filterBounds(region)

    if date_begin:
        if not date_end:
            date_end = date_begin.advance(1, 'day')

        images = images.filterDate(date_begin, date_end)

    return images

def visualize_image(image, bands):
    vis = {'min': 0.05, 'max': [0.35, 0.35, 0.45], 'gamma': 1.4,
           'bands': bands}

    return image.visualize(**vis)


def get_sentinel_image(region, date_begin, date_end, bands):
    images = get_sentinel_images(region, date_begin, date_end)

    image = ee.Image(images.mosaic()).divide(10000)

    image = visualize_image(image, bands)

    return image


def get_ndvi(region, date_begin, date_end):
    pass


def get_landuse(region, date_begin, date_end):
    pass


def get_landuse_vs_legger(region, date_begin):
    pass


maps = {
    'satellite': get_sentinel_image,
    'ndvi': get_ndvi,
    'landuse': get_landuse,
    'landuse-vs-legger': get_landuse_vs_legger
}


def get_image_url(image):
    map_id = image.getMapId()

    id = map_id['mapid']
    token = map_id['token']

    url = 'https://earthengine.googleapis.com/map/' \
          '{0}/{{z}}/{{x}}/{{y}}?token={1}' \
        .format(id, token)

    return url


@app.route('/map/<string:id>/', methods=['POST'])
def get_map(id):
    """
    Returns maps processed by Google Earth Engine
    """

    json = request.get_json()

    region = json['region']

    date_begin = json['dateBegin']
    date_end = json['dateEnd']

    date_begin = date_begin or ee.Date(date_begin)
    date_end = date_end or ee.Date(date_end)

    bands = json['bands']

    image = maps[id](region, date_begin, date_end, bands)

    url = get_image_url(image)

    results = {'url': url}

    return jsonify(results)


@app.route('/image/', methods=['GET'])
def get_image_by_id():
    id = request.args.get('id')
    bands = request.args.get('bands')

    image = ee.Image(id)\
        .select(band_names['s2'], band_names['readable'])\
        .divide(10000)

    image = visualize_image(image, bands)

    url = get_image_url(image)

    return jsonify(url)


@app.route('/map/<string:id>/times/', methods=['POST'])
def get_map_times(id):
    """
    Returns maps processed by Google Earth Engine
    """

    if id != 'satellite':
        return 'Error: times can be requested only for satellite images'

    json = request.get_json()

    region = json['region']

    date_begin = json['dateBegin']
    date_end = json['dateEnd']

    date_begin = date_begin or ee.Date(date_begin)
    date_end = date_end or ee.Date(date_end)

    images = get_sentinel_images(region, date_begin, date_end)

    image_times = ee.List(images.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()
    image_ids = images.aggregate_array('system:id').getInfo()

    return jsonify({'image_times': image_times, 'image_ids': image_ids})


@app.route('/')
def root():
    """
    Redirect default page to API docs.
    :return:
    """

    print('redirecting ...')
    return redirect(request.url + 'apidocs')