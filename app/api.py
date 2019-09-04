import json
from flask import Flask, jsonify, redirect, request
import flask_cors
from flasgger import Swagger
import ee
from datetime import datetime, timedelta

import error_handler

# import connexion

# app = connexion.App(__name__, specification_dir='.')
# app.add_api('api.yaml')

# create app
app = Flask(__name__)

app.register_blueprint(error_handler.error_handler)

# register specs
Swagger(app, template_file='api.yaml')

band_names = {
    's2': ['B11', 'B8', 'B3', 'B2', 'B4', 'B5', 'B6', 'B7',
           'B8A', 'B9', 'B10'],
    'readable': ['swir', 'nir', 'green', 'blue', 'red', 'red2', 'red3', 'red4',
                 'nir2', 'water_vapour', 'cirrus']
}

# style using legger colors
legger_style = '\
  <RasterSymbolizer>\
    <ColorMap  type="intervals" extended="false" >\
      <ColorMapEntry color="#BDEEFF" quantity="1" label="Water"/>\
      <ColorMapEntry color="#FF817E" quantity="2" label="Verhard oppervlak"/>\
      <ColorMapEntry color="#EEFAD4" quantity="3" label="Gras en Akker"/>\
      <ColorMapEntry color="#DEBDDE" quantity="4" label="Riet en Ruigte"/>\
      <ColorMapEntry color="#73BF73" quantity="5" label="Bos"/>\
      <ColorMapEntry color="#D97A36" quantity="6" label="Struweel"/>\
      <ColorMapEntry color="#000000" quantity="10" label="Unknown"/>\
    </ColorMap>\
  </RasterSymbolizer>'

legger_classes = {
    'Water': 1,
    'Verhard oppervlak': 2,
    'Gras en Akker': 3,
    'Riet en Ruigte': 4,
    'Bos': 5,
    'Struweel': 6,
    '': 0
}

legger_classes = ee.Dictionary(legger_classes)

classes_legger = ee.Dictionary.fromLists(
    legger_classes.values().map(lambda o: ee.Number(o).format('%d')),
    legger_classes.keys()
)


def to_date_time_string(millis):
    return ee.Date(millis).format('YYYY-MM-dd HH:mm')


def get_satellite_images(region, date_begin, date_end):
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
    if param not in vis:
        vis[param] = value

    return vis


def visualize_image(image, vis):
    if not vis:
        vis = {}

    min = 0.05
    max = [0.35, 0.35, 0.45]
    gamma = 1.4

    vis = add_vis_parameter(vis, 'min', min)
    vis = add_vis_parameter(vis, 'max', max)
    vis = add_vis_parameter(vis, 'gamma', gamma)

    return image.visualize(**vis)


def get_satellite_image(region, date_begin, date_end, vis):
    images = get_satellite_images(region, date_begin, date_end)

    image = ee.Image(images.mosaic()).divide(10000)

    image = visualize_image(image, vis)

    return image


def _get_ndvi(date_begin, date_end, region):
    images = get_satellite_images(region, date_begin, date_end) \
        .map(lambda i: i.resample('bilinear'))
    image = ee.Image(images.mosaic()).divide(10000)
    ndvi = image.normalizedDifference(['nir', 'red'])

    return ndvi


def get_ndvi(region, date_begin, date_end, vis):
    ndvi = _get_ndvi(date_begin, date_end, region)

    if not vis:
        vis = {}

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


def _get_landuse(region, date_begin, date_end):
    """
    Computes landuse image using random forest algorithm given a (composite) image.
    Uses RWS Legger classification as a ground-truth.
    :param region:
    :param date_begin:
    :param date_end:
    :return:
    """

    legger_id = 'users/gertjang/FI_Rijn_Maas_merged_2012_numfdls'

    legger = ee.FeatureCollection(legger_id)

    class_property = "Legger"

    legger = legger \
        .filter(ee.Filter.neq(class_property, None)) \
        .map(lambda f: f.set(class_property, ee.Number(f.get(class_property)))) \
        .remap([8, 9, 1, 2, 3, 4], [1, 2, 3, 4, 5, 6], class_property)

    legger_image = ee.Image().int().paint(legger, class_property) \
        .rename(class_property)

    # get an image given region and dates
    images = get_satellite_images(region, date_begin, date_end) \
        .map(lambda i: i.resample('bilinear'))

    image = ee.Image(images.mosaic()).divide(10000)

    # add AHN for classification
    ahn = ee.Image('AHN/AHN2_05M_RUW')

    # sample values using stratified sampling
    number_of_points = 500
    options = {
        'numPoints': number_of_points,
        'classBand': class_property,
        'region': region,
        'scale': 10,
        'tileScale': 8,
        'dropNulls': True
    }

    samples = image \
        .addBands(legger_image) \
        .addBands(ahn.divide(100)) \
        .stratifiedSample(**options)

    # train random forest classifier
    number_of_trees = 15

    classifier = ee.Classifier.randomForest(number_of_trees) \
        .train(samples, class_property, image.bandNames())

    # classify current image
    classified = image.classify(classifier)

    classified = classified \
        .updateMask(legger_image.mask()) \
        .clip(region)

    return classified \
        .focal_mode(1)


def _get_landuse_old(region, date_begin, date_end):
    training_asset_id = 'users/gertjang/trainingsetWaal25012018_UTM'
    validation_asset_id = 'users/gertjang/validationsetWaal25012018_UTM'
    training_image_id = 'COPERNICUS/S2/20170526T105031_20170526T105518_T31UFT'
    # bounds_asset_id = 'users/cindyvdvries/vegetatiemonitor/beheergrens'
    bounds_asset_id = 'users/gena/beheergrens-geo'

    bounds = ee.FeatureCollection(bounds_asset_id)

    # get an image given region and dates
    images = get_satellite_images(region, date_begin, date_end) \
        .map(lambda i: i.resample('bilinear'))

    image = ee.Image(images.mosaic()).divide(10000)

    # train classifier using specific image
    imageTraining = ee.Image(training_image_id) \
        .select(band_names['s2'], band_names['readable']) \
        .resample('bilinear') \
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
        # .focal_mode(10, 'circle', 'meters')

    original_classes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]

    legger_classes = [1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 0, 2, 3, 3,
                      3, 4, 4, 4, 5, 5, 5, 6, 5, 5, 0]

    classified = classified.remap(original_classes, legger_classes)

    # mask = classified \
    #    .eq([1, 2, 3, 4, 5, 6]) \
    #    .reduce(ee.Reducer.anyNonZero())

    return classified \
        #    .updateMask(mask)

    # TODO: return as additional info in reply
    # get confusion matrix and training accurracy
    # trainAccuracy = classifier.confusionMatrix()

    # print('Resubstitution error matrix: ', trainAccuracy);
    # print('Training overall accuracy: ', trainAccuracy.accuracy());


def get_landuse(region, date_begin, date_end, vis):
    # get classified as raster
    classified = _get_landuse(region, date_begin, date_end)

    return classified \
        .sldStyle(legger_style)


def _get_landuse_vs_legger(date_begin, date_end, region):
    legger = _get_legger_image()
    mask = legger.eq([1, 2, 3, 4, 5, 6]).reduce(ee.Reducer.anyNonZero())
    legger = legger.updateMask(mask)
    # classification
    landuse = _get_landuse(region, date_begin, date_end)
    diff = landuse.subtract(legger)
    return diff


def get_landuse_vs_legger(region, date_begin, date_end, vis):
    diff = _get_landuse_vs_legger(date_begin, date_end, region)

    # use RWS legger colors
    palette = ['1a9850', '91cf60', 'd9ef8b', 'ffffbf', 'fee08b', 'fc8d59',
               'd73027']

    diff = diff.visualize(**{'min': -5, 'max': 5, 'palette': palette})

    return diff


def _get_legger_image():
    legger_features = ee.FeatureCollection('users/gena/vegetatie-vlakken-geo')

    legger_features = legger_features \
        .map(lambda f: f.set('type', legger_classes.get(f.get('VL_KLASSE'))))

    legger = ee.Image().int().paint(legger_features, 'type')

    return legger


def get_legger(region, date_begin, date_end, vis):
    leger = _get_legger_image()

    return leger \
        .sldStyle(legger_style)


maps = {
    'satellite': get_satellite_image,
    'ndvi': get_ndvi,
    'landuse': get_landuse,
    'landuse-vs-legger': get_landuse_vs_legger,
    'legger': get_legger
}


def export_satellite_image(region, date_begin, date_end, vis):
    return get_satellite_image(region, date_begin, date_end, vis)


def export_ndvi(region, date_begin, date_end, vis):
    return _get_ndvi(date_begin, date_end, region)


def export_landuse(region, date_begin, date_end, vis):
    return _get_landuse(region, date_begin, date_end)


def export_landuse_vs_legger(region, date_begin, date_end, vis):
    return _get_landuse_vs_legger(date_begin, date_end, region)


exports = {
    'satellite': export_satellite_image,
    'ndvi': export_ndvi,
    'landuse': export_landuse,
    'landuse-vs-legger': export_landuse_vs_legger
}


def _get_zonal_info(features, image, scale):
    area = ee.Image.pixelArea().rename('area')

    image = area.addBands(image)

    # for every input feature, compute area

    def get_feature_info(f):
        f = ee.Feature(f)

        reducer = ee.Reducer.sum().group(**{
            "groupField": 1,
            "groupName": 'type',
        })

        geom = f.geometry()

        area = image.reduceRegion(reducer, geom, scale)

        def format_area(o):
            o = ee.Dictionary(o)

            t = ee.Number(o.get('type')).format('%d')
            area = o.get('sum')

            return {
                "type": t,
                "area": area
            }

        area = ee.List(area.get('groups')).map(format_area)

        return {
            "id": f.get('id'),
            "area_per_type": area
        }

    return features.toList(5000).map(get_feature_info)


def get_zonal_info_landuse(region, date_begin, date_end, scale):
    features = ee.FeatureCollection(region["features"])

    image = _get_landuse(features.geometry(), date_begin, date_end)

    info = _get_zonal_info(features, image, scale)

    return info.getInfo()


def get_zonal_info_landuse_vs_legger(region, date_begin, date_end, scale):
    pass


def get_zonal_info_ndvi(region, date_begin, date_end, scale):
    pass


def get_zonal_info_legger(region, date_begin, date_end, scale):
    features = ee.FeatureCollection(region["features"])

    image = _get_legger_image()

    info = _get_zonal_info(features, image, scale)

    return info.getInfo()


zonal_info = {
    'landuse': get_zonal_info_landuse,
    'landuse-vs-legger': get_zonal_info_landuse_vs_legger,
    'ndvi': get_zonal_info_ndvi,
    'legger': get_zonal_info_legger
}


def get_image_url(image):
    map_id = image.getMapId()

    id = map_id['mapid']
    token = map_id['token']

    url = 'https://earthengine.googleapis.com/map/' \
          '{0}/{{z}}/{{x}}/{{y}}?token={1}' \
        .format(id, token)

    return url


@app.route('/map/<string:id>/export/', methods=['POST'])
@flask_cors.cross_origin()
def export_map(id):
    """
    Returns URL to the image file
    """

    j = request.get_json()

    region = j['region']

    date_begin = j['dateBegin']
    if 'dateEnd' not in j:
        date_end = ee.Date(date_begin).advance(1, 'day')
    else:
        date_end = j['dateEnd']
    date_begin = date_begin or ee.Date(date_begin)
    date_end = date_end or ee.Date(date_end)

    vis = None
    if 'vis' in j:
        vis = j['vis']

    scale = 10
    if 'scale' in j:
        scale = j['scale']

    image = exports[id](region, date_begin, date_end, vis)

    format = 'tif'
    if id == 'satellite':
        format = 'png'

    url = image.getDownloadURL({
        "format": format,
        "name": id,
        "scale": scale,
        "region": json.dumps(region)})

    results = {'url': url}

    return jsonify(results)


@app.route('/map/<string:id>/', methods=['POST'])
@flask_cors.cross_origin()
def get_map(id):
    """
    Returns maps processed by Google Earth Engine
    """

    json = request.get_json()
    region = json['region']
    date_begin = json['dateBegin']
    if 'dateEnd' not in json:
        date_end = ee.Date(date_begin).advance(1, 'day')
    else:
        date_end = json['dateEnd']
    date_begin = date_begin or ee.Date(date_begin)
    date_end = date_end or ee.Date(date_end)

    vis = None
    if 'vis' in json:
        vis = json['vis']

    image = maps[id](region, date_begin, date_end, vis)

    url = get_image_url(image)

    results = {'url': url}

    return jsonify(results)


@app.route('/map/<string:id>/zonal-info/', methods=['POST'])
@flask_cors.cross_origin()
def get_map_zonal_info(id):
    """
    Returns zonal statistics per input feature (region)
    """

    if id not in ['landuse', 'ndvi', 'landuse-vs-legger', 'legger']:
        return 'Error: zonal statistics for {0} is not supported yet' \
            .format(id)

    json = request.get_json()

    region = json['region']

    date_begin = None
    date_end = None

    if 'dateBegin' in json:
        date_begin = ee.Date(json['dateBegin'])

    if 'dateEnd' in json:
        date_end = ee.Date(json['dateEnd'])

    scale = json['scale']

    info = zonal_info[id](region, date_begin, date_end, scale)

    return jsonify(info)


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

    date_end = datetime.today()
    date_begin = date_end - timedelta(days=365)

    # date_begin = json['dateBegin']
    # date_end = json['dateEnd']

    date_begin = date_begin or ee.Date(date_begin)
    date_end = date_end or ee.Date(date_end)

    images = get_satellite_images(region, date_begin, date_end)

    image_times = ee.List(images.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()
    image_ids = images.aggregate_array('system:id').getInfo()

    image_info_list = []
    for time, id in zip(image_times, image_ids):
        image_info_list.append({
            "datetime": time,
            "datetimeFormat": 'YYYY-MM-DD HH:mm',
            "imageId": id
        })

    return jsonify(image_info_list)


@app.route('/image/', methods=['POST'])
@flask_cors.cross_origin()
def get_image_by_id():
    id = request.args.get('id')

    vis = request.get_json()

    image = ee.Image(id) \
        .select(band_names['s2'], band_names['readable']) \
        .divide(10000)

    image = visualize_image(image, vis)

    url = get_image_url(image)

    return jsonify(url)


@app.route('/')
@flask_cors.cross_origin()
def root():
    """
    Redirect default page to API docs.
    :return:
    """

    print('redirecting ...')
    return redirect(request.url + 'apidocs')
