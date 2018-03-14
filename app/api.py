from flask import Flask, jsonify, redirect, request
import flask_cors
from flasgger import Swagger
import ee

# import connexion

# app = connexion.App(__name__, specification_dir='.')
# app.add_api('api.yaml')

import flasgger

# create app
app = Flask(__name__)

from errors import errors

app.register_blueprint(errors)

# register specs
flasgger.Swagger(app, template_file='api.yaml')

band_names = {
    's2': ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B9', 'B10',
           'B11', 'B12'],
    'readable': ['coastal', 'blue', 'green', 'red', 'red2', 'red3', 'red4',
                 'nir', 'nir2', 'water_vapour', 'cirrus', 'swir', 'swir2']
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


def add_vis_parameter(vis, param, value):
    """
    Adds parameter to vis dictionary if not exsit
    :param vis:
    :param param:
    :param value:
    :return:
    """
    if not param in vis:
        vis[param] = value

    return vis

def visualize_image(image, vis):
    min = 0.05
    max = [0.35, 0.35, 0.45]
    gamma = 1.4

    vis = add_vis_parameter(vis, 'min', min)
    vis = add_vis_parameter(vis, 'min', max)
    vis = add_vis_parameter(vis, 'gamma', gamma)

    return image.visualize(**vis)


def get_sentinel_image(region, date_begin, date_end, vis):
    images = get_sentinel_images(region, date_begin, date_end)

    image = ee.Image(images.mosaic()).divide(10000)

    image = visualize_image(image, vis)

    return image


def get_ndvi(region, date_begin, date_end, vis):
    images = get_sentinel_images(region, date_begin, date_end) \
        .map(lambda i: i.resample('bilinear'))

    image = ee.Image(images.mosaic()).divide(10000)

    ndvi = image.normalizedDifference(['nir', 'red'])

    # set default vis parameters if not provided

    palette = ['000000', '252525', '525252', '737373', '969696', 'bdbdbd',
               'd9d9d9', 'f0f0f0', 'ffffff', 'f7fcf5', 'e5f5e0', 'c7e9c0',
               'a1d99b', '74c476', '41ab5d', '238b45', '006d2c', '00441b']
    min = -1
    max = 1

    vis = add_vis_parameter(vis, 'palette', palette)
    vis = add_vis_parameter(vis, 'min', min)
    vis = add_vis_parameter(vis, 'max', max)

    return ndvi.visualize(**vis)


def get_landuse(region, date_begin, date_end):
    training_asset_id = 'users/gertjang/trainingsetWaal25012018_UTM'
    validation_asset_id = 'users/gertjang/validationsetWaal25012018_UTM'
    training_image_id = 'COPERNICUS/S2/20170526T105031_20170526T105518_T31UFT'
    bounds_asset_id = 'users/cindyvdvries/vegetatiemonitor/beheergrens'

    bounds = ee.FeatureCollection(bounds_asset_id)

    # get an image given region and dates
    images = get_sentinel_images(region, date_begin, date_end) \
        .map(lambda i: i.resample('bilinear'))

    image = ee.Image(images.mosaic()).divide(10000)

    # train classifier using specific image
    imageTraining = ee.Image(training_image_id) \
        .select(band_names['s2'], band_names['readable']) \
        .map(lambda i: i.resample('bilinear')) \
        .divide(10000)

    trainingSet = ee.FeatureCollection(training_asset_id)

    # sample image values
    training = imageTraining.sampleRegions(
        collection=trainingSet,
        properties=['GrndTruth'],
        scale=10)

    # train random forest classifier
    classifier = ee.Classifier.randomForest(10) \
        .train(training, 'GrndTruth')

    # classify image
    classified = image.classify(classifier) \
        .clip(bounds) \
        .focal_mode(10, 'circle', 'meters')

    original_classes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]

    legger_classes = [8, 8, 8, 8, 8, 8, 8, 9, 8, 8, 8, 8, 8, 8, 10,
                      9, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 3, 3, 10]

    classified = classified.remap(original_classes, legger_classes)

    # TODO: return as additional info in reply
    # get confusion matrix and training accurracy
    # trainAccuracy = classifier.confusionMatrix()

    # print('Resubstitution error matrix: ', trainAccuracy);
    # print('Training overall accuracy: ', trainAccuracy.accuracy());

    # replace color by SLD
    # style = '\
    #  <RasterSymbolizer>\
    #    <ColorMap  type="intervals" extended="false" >\
    #      <ColorMapEntry color="#cef2ff" quantity="-200" label="-200m"/>\
    #      <ColorMapEntry color="#9cd1a4" quantity="0" label="0m"/>\
    #      <ColorMapEntry color="#7fc089" quantity="50" label="50m" />\
    #      <ColorMapEntry color="#9cc78d" quantity="100" label="100m" />\
    #      <ColorMapEntry color="#b8cd95" quantity="250" label="250m" />\
    #      <ColorMapEntry color="#d0d8aa" quantity="500" label="500m" />\
    #      <ColorMapEntry color="#e1e5b4" quantity="750" label="750m" />\
    #      <ColorMapEntry color="#f1ecbf" quantity="1000" label="1000m" />\
    #      <ColorMapEntry color="#e2d7a2" quantity="1250" label="1250m" />\
    #      <ColorMapEntry color="#d1ba80" quantity="1500" label="1500m" />\
    #      <ColorMapEntry color="#d1ba80" quantity="10000" label="10000m" />\
    #    </ColorMap>\
    #  </RasterSymbolizer>';
    # classified = classified.sldStyle(style)

    return classified.randomVisualizer()


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
@flask_cors.cross_origin()
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

    vis = json['vis']

    image = maps[id](region, date_begin, date_end, vis)

    url = get_image_url(image)

    results = {'url': url}

    return jsonify(results)


@app.route('/image/', methods=['POST'])
@flask_cors.cross_origin()
def get_image_by_id():
    id = request.args.get('id')

<<<<<<< HEAD
    vis = request.get_json()

=======
>>>>>>> a4d9a221459b687cbd34c947d7a702694ada3cc9
    image = ee.Image(id) \
        .select(band_names['s2'], band_names['readable']) \
        .divide(10000)

    image = visualize_image(image, vis)

    url = get_image_url(image)

    return jsonify(url)


@app.route('/map/<string:id>/times/', methods=['POST'])
@flask_cors.cross_origin()
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
@flask_cors.cross_origin()
def root():
    """
    Redirect default page to API docs.
    :return:
    """

    print('redirecting ...')
    return redirect(request.url + 'apidocs')
