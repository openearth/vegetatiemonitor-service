import os
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, redirect, request
import flask_cors
from flasgger import Swagger
import ee
from google.cloud import firestore

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

class_names = list(legger_classes.keys())

legger_classes = ee.Dictionary(legger_classes)

classes_legger = ee.Dictionary.fromLists(
    legger_classes.values().map(lambda o: ee.Number(o).format('%d')),
    legger_classes.keys()
)


def to_date_time_string(millis):
    return ee.Date(millis).format('YYYY-MM-dd HH:mm')


def get_satellite_images(region, date_begin, date_end, cloud_filtering):
    images = ee.ImageCollection('COPERNICUS/S2') \
        .select(band_names['s2'], band_names['readable']) \
        .filterBounds(region)

    if date_begin:
        if not date_end:
            date_end = date_begin.advance(1, 'day')

        images = images.filterDate(date_begin, date_end)

    filter_options = {
        'score_percentile': 95
    }

    if cloud_filtering:
        images = get_mostly_clean_images(images, region, options=filter_options)

    return images


def get_image_collection(collection, region, date_begin, date_end):
    images = ee.ImageCollection(collection) \
        .filterBounds(region)

    if date_begin:
        if not date_end:
            date_end = date_begin.advance(1, 'day')

        images = images.filterDate(date_begin, date_end)

    return images


def add_quality_score(images, g, score_percentile, scale):
    """
    Adds quality score to images based on clouds
    :param images:
    :param g:
    :param score_percentile:
    :param scale:
    :return:
    """
    quality_band = 'green'

    def cloud_score(i):
        score = i.select(quality_band)
        score = score.reduceRegion(reducer=ee.Reducer.percentile([score_percentile]), geometry=ee.Geometry(g),
                                   scale=scale, tileScale=4).values().get(0)

        return i.set('quality_score', score)

    return images.map(cloud_score)


def get_mostly_clean_images(images, g, options=None):
    geometry = ee.Geometry(g)
    scale = 1000
    score_percentile = 85
    cloud_frequency_threshold_delta = None

    if options:
        if 'scale' in options:
            scale = options['scale']
        if 'score_percentile' in options:
            score_percentile = options['score_percentile']
        if 'cloud_frequency_threshold_delta' in options:
            cloud_frequency_threshold_delta = options['cloud_frequency_threshold_delta']

    cloud_frequency = 0.9  # Calculated for the Netherlands, hardcoded for speed

    cloud_frequency = ee.Number(cloud_frequency)

    if cloud_frequency_threshold_delta:
        cloud_frequency = cloud_frequency.add(cloud_frequency_threshold_delta)

    images = images.filterBounds(geometry)

    images = add_quality_score(images, geometry, score_percentile, scale)

    max_image_count = images.size().multiply(ee.Number(1).subtract(cloud_frequency)).toInt()
    images = images.sort('quality_score').limit(max_image_count)

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
    images = get_satellite_images(region, date_begin, date_end, False)
    image = ee.Image(images.mosaic()).divide(10000)
    image = visualize_image(image, vis)

    return image


def _get_ndvi(date_begin, date_end, region):
    images = get_satellite_images(region, date_begin, date_end, False) \
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
    class_property = 'Legger'
    image_path = 'projects/deltares-rws/vegetatiemonitor/fotointerpretatie-rijn-maas-merged-2017-image-10m'
    landuse_legger = ee.Image(image_path).rename(class_property)

    # get an image given region and dates
    images = get_satellite_images(region, date_begin, date_end, False) \
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
        .addBands(landuse_legger) \
        .addBands(ahn.divide(100)) \
        .stratifiedSample(**options)

    # train random forest classifier
    number_of_trees = 15

    classifier = ee.Classifier.randomForest(number_of_trees) \
        .train(samples, class_property, image.bandNames())

    # classify current image
    classified = image.classify(classifier)

    classified = classified \
        .updateMask(landuse_legger.mask()) \
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
    images = get_satellite_images(region, date_begin, date_end, False) \
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


def _get_landuse_vs_legger(region, date_begin, date_end):
    legger = _get_legger_image()
    # classification
    landuse = _get_landuse(region, date_begin, date_end)
    diff = landuse.subtract(legger)
    return diff


def get_landuse_vs_legger(region, date_begin, date_end, vis):
    diff = _get_landuse_vs_legger(region, date_begin, date_end)

    # use RWS legger colors
    palette = ['1a9850', '91cf60', 'd9ef8b', 'ffffbf', 'fee08b', 'fc8d59',
               'd73027']

    diff = diff.visualize(**{'min': -5, 'max': 5, 'palette': palette})

    return diff


def _get_legger_image():
    legger = ee.Image('projects/deltares-rws/vegetatiemonitor/legger-2012-6-class-10m')\
        .rename('type')

    return legger


def get_legger(region, date_begin, date_end, vis):
    legger = _get_legger_image()

    return legger \
        .sldStyle(legger_style)


maps = {
    'satellite': get_satellite_image,
    'ndvi': get_ndvi,
    'landuse': get_landuse,
    'landuse-vs-legger': get_landuse_vs_legger,
    'legger': get_legger
}


def export_satellite_image(region, date_begin, date_end, vis, asset_type):
    if asset_type == 'day':
        image = get_satellite_image(region, date_begin, date_end, vis)
    else:
        images = get_image_collection(yearly_collections["satellite"], region, date_begin, date_end)
        image = ee.Image(images.first())
        image = visualize_image(image, vis)

    return image


def export_ndvi(region, date_begin, date_end, vis, asset_type):
    if asset_type == 'day':
        image = _get_ndvi(date_begin, date_end, region)
    else:
        images = get_image_collection(yearly_collections["satellite"], region, date_begin, date_end)
        image = ee.Image(images.first())

    return image


def export_landuse(region, date_begin, date_end, vis, asset_type):
    if asset_type == 'day':
        image = _get_landuse(region, date_begin, date_end)
    else:
        images = get_image_collection(yearly_collections["landuse"], region, date_begin, date_end)
        image = ee.Image(images.first())

    return image


def export_landuse_vs_legger(region, date_begin, date_end, vis, asset_type):
    if asset_type == 'day':
        image = _get_landuse_vs_legger(region, date_begin, date_end)
    else:
        images = get_image_collection(yearly_collections["landuse_vs_legger"], region, date_begin, date_end)
        image = ee.Image(images.first())

    return image


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
            area = ee.Number(o.get('sum')).round()

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


def get_zonal_info_landuse(region, date_begin, date_end, scale, asset_type, map_extent):
    features = ee.FeatureCollection(region["features"])
    if asset_type == 'day':
        image = _get_landuse(map_extent, date_begin, date_end)
    else:
        images = get_image_collection(yearly_collections['landuse'], features.geometry(), date_begin, date_end)
        image = ee.Image(images.first())

    info = _get_zonal_info(features, image, scale)

    return info.getInfo()


def get_zonal_info_landuse_vs_legger(region, date_begin, date_end, scale, asset_type, map_extent):
    pass


def get_zonal_info_ndvi(region, date_begin, date_end, scale, asset_type, map_extent):
    pass


def get_zonal_info_legger(region, date_begin, date_end, scale, asset_type, map_extent):
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

yearly_collections = {
    'satellite': 'users/rogersckw9/vegetatiemonitor/satellite-yearly',
    'ndvi': 'users/rogersckw9/vegetatiemonitor/satellite-yearly',
    'landuse': 'users/rogersckw9/vegetatiemonitor/yearly-classified-images',
    'landuse-vs-legger': 'users/rogersckw9/vegetatiemonitor/classificatie-vs-legger'
}


def _get_zonal_timeseries(features, images, scale):
    images = ee.ImageCollection(images)
    image_times = ee.List(images.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()

    area = ee.Image.pixelArea().rename('area')

    images = images.map(lambda i: area.addBands(i.rename('type')))

    # for every input feature, compute area
    def get_feature_info(f):
        f = ee.Feature(f)

        reducer = ee.Reducer.sum().group(**{
            "groupField": 1,
            "groupName": 'type',
        })

        geom = f.geometry()

        def reduce_image(i):
            area = i.reduceRegion(reducer, geom, scale)
            area = ee.Feature(None).set({
                'area': ee.List(ee.Dictionary(area).get('groups'))
            })
            return area

        info = images.map(reduce_image)
        area = ee.List(info.aggregate_array("area"))

        return {
            "id": f.get('id'),
            "area": area,
            "times": image_times
        }

    return features.toList(5000).map(get_feature_info)


legend_remap = {
    "1": {
        "name": "Water",
        "color": "#BDEEFF"
    },
    "2": {
        "name": "Verhard oppervlak",
        "color": "#FF817E"
    },
    "3": {
        "name": "Gras en Akker",
        "color": "#EEFAD4"
    },
    "4": {
        "name": "Riet en Ruigte",
        "color": "#DEBDDE"
    },
    "5": {
        "name": "Bos",
        "color": "#73BF73"
    },
    "6": {
        "name": "Struweel",
        "color": "#D97A36"
    }
}

legend_remap = {
    "1": {
        "name": "Water",
        "color": "#BDEEFF"
    },
    "2": {
        "name": "Verhard oppervlak",
        "color": "#FF817E"
    },
    "3": {
        "name": "Gras en Akker",
        "color": "#EEFAD4"
    },
    "4": {
        "name": "Riet en Ruigte",
        "color": "#DEBDDE"
    },
    "5": {
        "name": "Bos",
        "color": "#73BF73"
    },
    "6": {
        "name": "Struweel",
        "color": "#D97A36"
    }
}


def get_zonal_timeseries_landuse(region, date_begin, date_end, scale):
    features = ee.FeatureCollection(region["features"])
    # Add empty image for 2012
    empty = ee.Image().set("system:time_start", ee.Date("2012-06-01").millis()).rename("remapped")
    collection = yearly_collections["landuse"]
    images = get_image_collection(collection, features.geometry(), date_begin, date_end) \
        .merge(ee.ImageCollection([empty])).sort("system:time_start")
    features = ee.FeatureCollection(region["features"])

    image = _get_landuse(features.geometry(), date_begin, date_end)

    info = _get_zonal_info(features, image, scale)

    info = _get_zonal_timeseries(features, images, scale)
    info = info.getInfo()
    timeseries = []
    for i, feature_data in enumerate(info):
        timeseries.append({
            "series": []
        })
        for j in range(1, 7, 1):
            timeseries[i]["series"].append({"name": legend_remap[str(j)]["name"], "type": "line", "data": [],
                                            "color": legend_remap[str(j)]["color"]})

        timeseries[i]["xAxis"] = {
            "data": feature_data["times"]
        }
        timeseries[i]["yAxis"] = {
            "type": "value"
        }
        for a in feature_data['area']:
            for k in range(1, 7, 1):
                val = next((item for item in a if item["type"] == k), None)
                if not val:
                    timeseries[i]["series"][k - 1]["data"].append("-")
                else:
                    #     item = d.get("type", None) == str(k)
                    timeseries[i]["series"][k - 1]["data"].append(val.get("sum"))

    return timeseries


def get_zonal_timeseries_landuse_vs_legger(region, date_begin, date_end, scale):
    pass


def get_zonal_timeseries_ndvi(region, date_begin, date_end, scale):
    pass


def get_zonal_timeseries_legger(region, date_begin, date_end, scale):
    pass


zonal_timeseries = {
    'landuse': get_zonal_timeseries_landuse,
    'landuse-vs-legger': get_zonal_timeseries_landuse_vs_legger,
    'ndvi': get_zonal_timeseries_ndvi,
    'legger': get_zonal_timeseries_legger
}

modes = ['daily', 'yearly']

asset_types = ['day', 'year']


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

    if 'assetType' in j:
        asset_type = j['assetType']
    else:
        asset_type = 'day'

    if asset_type not in asset_types:
        return 'Error: assetType {0} is not supported, only day or year available' \
            .format(asset_type)

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

    image = exports[id](region, date_begin, date_end, vis, asset_type)

    format = 'tif'
    if id == 'satellite':
        format = 'png'

    url = image.getDownloadURL({
        "format": format,
        "name": id + "_" + date_begin + "_" + date_end,
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

    if 'assetType' in json:
        asset_type = json['assetType']
    else:
        asset_type = 'day'

    if asset_type not in asset_types:
        return 'Error: assetType {0} is not supported, only day or year available' \
            .format(asset_type)

    region = json['region']

    date_begin = None
    date_end = None

    if 'dateBegin' in json:
        date_begin = ee.Date(json['dateBegin'])

    if 'dateEnd' in json:
        date_end = ee.Date(json['dateEnd'])


    scale = json['scale']
    map_extent = json.get('mapExtent', None)

    info = zonal_info[id](region, date_begin, date_end, scale, asset_type, map_extent)

    return jsonify(info)


@app.route('/map/<string:id>/zonal-timeseries/', methods=['POST'])
@flask_cors.cross_origin()
def get_map_zonal_timeseries(id):
    """
    Returns zonal timeseries per input feature (region)
    """

    if id != 'landuse':
        return 'Error: zonal timeseries for {0} is not supported yet' \
            .format(id)

    json = request.get_json()

    region = json['region']

    date_begin = ee.Date("2000-01-01")
    date_end = ee.Date("2019-01-01")

    # if 'dateBegin' in json:
    #     date_begin = ee.Date(json['dateBegin'])
    #
    # if 'dateEnd' in json:
    #     date_end = ee.Date(json['dateEnd'])

    scale = json['scale']

    info = zonal_timeseries[id](region, date_begin, date_end, scale)

    return jsonify(info)


def _get_map_times_daily(id, region):
    # take images for one year from now
    date_end = datetime.today()
    date_begin = date_end - timedelta(days=365)

    # HACK: return least cloudy images using metadata
    images = ee.ImageCollection('COPERNICUS/S2') \
        .filterDate(ee.Date(date_begin), ee.Date(date_end)) \
        .select(band_names['s2'], band_names['readable']) \
        .filterBounds(region) \
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 10))

    # TODO: add Datastore

    # filter bounds of a region
    # aoi = ee.FeatureCollection('users/gdonchyts/vegetation-monitor-aoi')  # TODO: move to gs://deltares-rws
    # region = ee.Geometry(region).intersection(aoi.geometry(), 500)
    #
    # images = get_satellite_images(region, date_begin, date_end, True)

    image_times = ee.List(images.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()

    image_times = map(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M'), image_times)
    image_dates = list(sorted(set(map(lambda x: x.strftime('%Y-%m-%d'), image_times))))

    image_info_list = []

    for time in image_dates:
        image_info_list.append({
            "date": time,
            "dateFormat": 'YYYY-MM-DD',
            "type": "instance"
        })

    return image_info_list


def _get_map_times_yearly(id, region):
    date_begin = datetime(2000, 1, 1, 0, 0, 0)
    date_end = datetime(2019, 1, 1, 0, 0, 0)

    images = get_image_collection(yearly_collections[id], region, date_begin, date_end)

    image_times = ee.List(images.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()

    image_times = map(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M'), image_times)

    image_start_dates = list(map(lambda t: datetime(t.year, 1, 1), image_times))
    image_end_dates = list(map(lambda t: datetime(t.year + 1, 1, 1), image_start_dates))

    image_info_list = []
    for start, end in zip(image_start_dates, image_end_dates):
        image_info_list.append({
            "dateStart": start.strftime('%Y-%m-%d'),
            "dateEnd": end.strftime('%Y-%m-%d'),
            "dateFormat": 'YYYY-MM-DD',
            "type": "interval"
        })

    return image_info_list


@app.route('/map/<string:id>/times/<string:mode>', methods=['POST'])
@flask_cors.cross_origin()
def get_map_times(id, mode):
    """
    Returns maps processed by Google Earth Engine
    """

    json = request.get_json()

    region = json['region']

    if mode not in modes:
        return 'Error: only daily and yearly modes can be requested'

    if mode == 'daily':
        dates = _get_map_times_daily(id, region)
    else:
        dates = _get_map_times_yearly(id, region)

    return jsonify(dates)


def wet_moist_masks(start_date, feature):
    """
    Create mask of wet area (water in Feb-Mar and May-Jun) and moist area (water in Feb-Mar, not May-Jun)
    :param start_date: Date to start moist/wet masking
    :param feature: feature selected for analysis
    :return:
    """
    bounds = feature.geometry()
    start_year = ee.Date(start_date).get('year')
    begin_date = ee.Date(start_date).advance(1, 'month')
    lookback = begin_date.advance(-1, 'year')

    # get satellite images and filter out clouded images
    images = get_satellite_images(bounds, lookback, begin_date, True)

    ndwi_bands = ['green', 'nir']
    # Feb-Mar ndwi (wet season)
    images_wet = images.filterDate(ee.Date.fromYMD(start_year, 2, 1), ee.Date.fromYMD(start_year, 3, 31))
    image_wet = images_wet.median().divide(10000)
    ndwi_wet = image_wet.normalizedDifference(ndwi_bands)

    # May-June ndwi (dry season)
    images_dry = images.filterDate(ee.Date.fromYMD(start_year, 5, 1), ee.Date.fromYMD(start_year, 6, 30))
    image_dry = images_dry.median().divide(10000)
    ndwi_dry = image_dry.normalizedDifference(ndwi_bands)

    # Mask where ground was once flooded.
    # Where there was water in wet image (0.1 <= ndvi <= 0.4), no longer in dry image
    moist_mask = ndwi_wet.gte(-0.1).And(ndwi_wet.lte(0.4)).And(ndwi_dry.lte(-0.1)).Or(ndwi_dry.gte(0.4))

    # Mask where ground remains wet
    wet_mask = ndwi_wet.gte(-0.1).And(ndwi_wet.lte(0.4)).And(ndwi_dry.gte(-0.1)).And(ndwi_dry.lte(0.4))
    return moist_mask.addBands(wet_mask).rename(['moistMask', 'wetMask'])


def bare_grazing_variables(ecotop_map, bare_to_reed_mask, bare_to_willow_mask):
    """
    Create bands for scaling succession based on management of reed and willow areas
    :param ecotop_map:
    :param bare_to_reed_mask:
    :param bare_to_willow_mask:
    :return:
    """
    management_code = 'BEHEER'
    management_list = ['Onbekend', 'Nauwelijks tot geen beheer', 'Nauwelijks tot geen/extensief beheer',
                       'Extensief beheer', 'Intensief beheer', 'Kunstmatig hard substraat', 'Water']
    reed_grazing = [0, 100, 100, 100, 70, 0, 0]
    willow_grazing_a = [0, 50, 50, 230, 280, 0, 0]
    willow_grazing_b = [0, 57, 57, 57, 60, 0, 0]

    reed_grazing = ecotop_map.remap(management_list, reed_grazing, management_code)
    willow_grazing_a = ecotop_map.remap(management_list, willow_grazing_a, management_code)
    willow_grazing_b = ecotop_map.remap(management_list, willow_grazing_b, management_code)

    reed_grazing_image = ee.Image().int().paint(reed_grazing, management_code).divide(100)
    willow_grazing_a_image = ee.Image().int().paint(willow_grazing_a, management_code).multiply(bare_to_willow_mask)
    willow_grazing_b_image = ee.Image().int().paint(willow_grazing_b, management_code).divide(100).updateMask(
        bare_to_willow_mask)

    return reed_grazing_image.addBands(willow_grazing_a_image).addBands(willow_grazing_b_image) \
        .rename(['bareToReedGrazing', 'bareToWillowGrazingA', 'bareToWillowGrazingB'])


def willow_function(a, b, t):
    """
    Function to caluclate willow roughness over time t
    A = [50, 230, 280], B = [0.57, 0.57, 0.60] for Beheer = [No grazing, Extensive grazing, Intensief grazing]
    k = 25.41/(1 + A * B**t)
    :param a:
    :param b:
    :param t:
    :return:
    """
    k_value = ee.Image(25.41).divide(ee.Image(1.0).add(ee.Image(a).multiply(ee.Image(b).pow(ee.Number(ee.Image(t))))))
    return k_value


def prepare_voorspel_data(image, ecotop_features, grass_pct, herb_pct, willow_pct, feature, start_date, years):
    """

    :param image:
    :param ecotop_features:
    :param grass_pct:
    :param herb_pct:
    :param willow_pct:
    :param feature:
    :param start_date:
    :param years:
    :return:
    """

    class_values = [1, 2, 3, 4, 5, 6]
    class_roughness = [0.0, 0.15, 0.39, 1.45, 12.84, 24.41]

    # Convert image from classes to roughness
    image = image.remap(class_values, class_roughness)

    # Specify roughness value image for each class
    k_water = ee.Number(class_roughness[0])
    k_bare = ee.Number(class_roughness[1])
    k_grass = ee.Number(class_roughness[2])
    k_herbaceous = ee.Number(class_roughness[3])
    k_reed = ee.Number(20.73)
    k_forest = ee.Number(class_roughness[4])
    k_willow = ee.Number(class_roughness[5])

    k_water_im = ee.Image(k_water)
    k_bare_im = ee.Image(k_bare)
    k_grass_im = ee.Image(k_grass)
    k_herbaceous_im = ee.Image(k_herbaceous)
    k_reed_im = ee.Image(k_reed)
    k_forest_im = ee.Image(k_forest)
    k_willow_im = ee.Image(k_willow)

    # Rates for progression from one class to another.
    # All rates take 10 yr to change class
    bare_to_reed_rate = k_reed.subtract(k_bare).divide(5)
    grass_to_herb_rate = k_herbaceous.subtract(k_grass).divide(10)
    herb_to_willow_rate = k_willow.subtract(k_herbaceous).divide(10)
    willow_to_forest_rate = k_forest.subtract(k_willow).divide(10)

    # Shoreline roughness image @ t=0
    first_roughness_image = k_water_im.updateMask(image.eq(k_water)) \
        .addBands(k_bare_im.updateMask(image.eq(k_bare))) \
        .addBands(k_grass_im.updateMask(image.eq(k_grass))) \
        .addBands(k_herbaceous_im.updateMask(image.eq(k_herbaceous))) \
        .addBands(k_forest_im.updateMask(image.eq(k_forest))) \
        .addBands(k_willow_im.updateMask(image.eq(k_willow))) \
        .rename(['waterRoughness', 'bareRoughness', 'grassRoughness',
                 'herbaceousRoughness', 'forestRoughness', 'willowRoughness']) \
        .set('system:time_start', start_date)

    #
    moisture_masks = wet_moist_masks(start_date, feature)
    wet_mask = moisture_masks.select('wetMask')
    moist_mask = moisture_masks.select('moistMask')

    # Mechanical dynamics from ecotoop layers
    mech_dyn_list = ['Onbekend', 'Gering dynamisch', 'Matig/gering dynamisch', 'Sterk/matig dynamisch',
                     'Sterk dynamisch']
    ecotoop_mech_dyn = ecotop_features.remap(mech_dyn_list, [0, 1, 2, 3, 4], 'MECH_DYN')

    mech_dyn_im = ee.Image().int().paint(ecotoop_mech_dyn, 'MECH_DYN')
    weak_dynamics = mech_dyn_im.lte(1)
    moderate_dynamics = mech_dyn_im.eq(2)
    strong_dynamics = mech_dyn_im.gte(3)

    # bare remain bare with strong dynamics
    remain_bare = image.eq(k_bare).multiply(strong_dynamics);
    # bare will change to reed in 2 yr if it is wet and weak dynamics
    bare_to_reed_mask = image.eq(k_bare).multiply(wet_mask).multiply(weak_dynamics)
    # bare will change to willow if moist and moderate dynamics
    bare_to_willow_mask = image.eq(k_bare).multiply(moist_mask).multiply(moderate_dynamics)

    # Grazing/management will affect the rate at which bare progresses
    bare_grazing_im = bare_grazing_variables(ecotop_features, bare_to_reed_mask, bare_to_willow_mask)
    bare_to_reed_mask = bare_to_reed_mask.multiply(bare_grazing_im.select('bareToReedGrazing'))
    max_reed_im = k_reed_im.multiply(bare_to_reed_mask)

    # Create random images
    random_a = ee.Image.random(0)
    random_b = ee.Image.random(1)
    random_c = ee.Image.random(2)

    # % grass will change into herb in 10 yr
    grass_to_herb_mask = image.eq(k_grass).And(random_a.lte(grass_pct))

    # % herbaceous veg will change to shrubs in 10 yr
    herb_to_willow_mask = image.eq(k_herbaceous).And(random_b.lte(herb_pct))

    # % of willows/shrubs will change into forest in 10 yr
    willow_to_forest_mask = image.eq(k_willow).And(random_c.lte(willow_pct))

    def accumulate_roughness(year, prev):
        """
        """
        # Get the previous calculated image
        date_now = start_date.advance(ee.Number(year), 'year')
        prev_im = ee.Image(ee.List(prev).get(-1))
        water_now = prev_im.select('waterRoughness')

        bare_to_willow_prev = prev_im.select('bareRoughness').multiply(bare_to_willow_mask)

        bare_to_willow_now = k_willow_im.min(
            willow_function(bare_grazing_im.select('bareToWillowGrazingA'),
                            bare_grazing_im.select('bareToWillowGrazingB'),
                            year)
        )

        bare_now = prev_im.select('bareRoughness') \
            .add(max_reed_im.min(ee.Image(bare_to_reed_rate).multiply(bare_to_reed_mask)).unmask()) \
            .add(bare_to_willow_now.subtract(bare_to_willow_prev).unmask())

        grass_now = prev_im.select('grassRoughness') \
            .add(ee.Image(grass_to_herb_rate).multiply(grass_to_herb_mask))

        herb_now = prev_im.select('herbaceousRoughness') \
            .add(ee.Image(herb_to_willow_rate).multiply(herb_to_willow_mask))

        forest_now = prev_im.select('forestRoughness')

        willow_now = prev_im.select('willowRoughness') \
            .add(ee.Image(willow_to_forest_rate).multiply(willow_to_forest_mask))

        image_now = water_now \
            .addBands(bare_now) \
            .addBands(grass_now) \
            .addBands(herb_now) \
            .addBands(forest_now) \
            .addBands(willow_now) \
            .rename(['waterRoughness', 'bareRoughness', 'grassRoughness',
                     'herbaceousRoughness', 'forestRoughness', 'willowRoughness']) \
            .set('system:time_start', date_now)

        # return ee.ImageCollection(prev_im).merge(ee.ImageCollection([image_now]))
        return ee.List(prev).add(image_now)

    year_array = ee.List.sequence(1, years, 1)
    # Create an ImageCollection of images by iterating.
    # blank_collection = ee.ImageCollection([first_roughness_image])
    blank_collection = ee.List([first_roughness_image])

    # cumulative_images = year_array.iterate(accumulate_roughness, blank_collection)
    cumulative_images = ee.ImageCollection(ee.List(year_array.iterate(accumulate_roughness, blank_collection)))
    return cumulative_images


def calculate_total_roughness(image):
    image = ee.Image(image)
    water_rough = image.select('waterRoughness').unmask()
    bare_rough = image.select('bareRoughness').unmask()
    grass_rough = image.select('grassRoughness').unmask()
    herb_rough = image.select('herbaceousRoughness').unmask()
    forest_rough = image.select('forestRoughness').unmask()
    willow_rough = image.select('willowRoughness').unmask()
    total = water_rough.add(bare_rough).add(grass_rough) \
        .add(herb_rough).add(forest_rough).add(willow_rough)
    return ee.Image(total) \
        .set('system:time_start', ee.Date(image.get('system:time_start'))) \
        .rename('voorspeldeRuwheid')


def merge_roughness_regions(classified_image, images_shoreline, images_terrestrial, image_no_succession):
    def combine_images(i):
        image1 = ee.Image(i).unmask()
        image2 = ee.Image(images_terrestrial.filterDate(image1.get('system:time_start')).first()).unmask()
        image3 = ee.Image(image_no_succession).unmask()
        water_rough = image1.select('waterRoughness').add(image2.select('waterRoughness'))
        # water_rough = water_rough.updateMask(water_rough.neq(0))
        bare_rough = image1.select('bareRoughness').add(image2.select('bareRoughness')).add(image3.eq(0.15))
        bare_rough = bare_rough.updateMask(bare_rough.neq(0))
        grass_rough = image1.select('grassRoughness').add(image2.select('grassRoughness')).add(image3.eq(0.39))
        grass_rough = grass_rough.updateMask(grass_rough.neq(0))
        herb_rough = image1.select('herbaceousRoughness').add(image2.select('herbaceousRoughness')).add(image3.eq(1.45))
        herb_rough = herb_rough.updateMask(herb_rough.neq(0))
        forest_rough = image1.select('forestRoughness').add(image2.select('forestRoughness')).add(image3.eq(12.84))
        forest_rough = forest_rough.updateMask(forest_rough.neq(0))
        willow_rough = image1.select('willowRoughness').add(image2.select('willowRoughness')).add(image3.eq(24.41))
        willow_rough = willow_rough.updateMask(willow_rough.neq(0))
        total = water_rough.addBands(bare_rough).addBands(grass_rough) \
            .addBands(herb_rough).addBands(forest_rough).addBands(willow_rough)
        return ee.Image(total) \
            .set('system:time_start', ee.Date(image1.get('system:time_start'))) \
            .rename(['waterRoughness', 'bareRoughness', 'grassRoughness',
                     'herbaceousRoughness', 'forestRoughness', 'willowRoughness']) \
            .mask(classified_image)

    cumulative_images = images_shoreline.map(combine_images)
    return cumulative_images


def predict_roughness(region, start_date, num_years):
    # start_date = ee.Date(startYearString + '-11-01')
    feature = ee.FeatureCollection(region["features"]).first()
    ecotop_features = ee.FeatureCollection("users/gertjang/succession/ecotopen_cyclus_drie_rijntakken_utm31n")
    classified_images = ee.ImageCollection('users/rogersckw9/vegetatiemonitor/yearly-classified-images')
    start_year = ee.Date(start_date).get('year')
    lookback = start_date.advance(-1, 'year')

    # Hydrology from ecotop layers
    ecotop_hydrology = ecotop_features.remap(
        ['Onbekend', 'Overstromingsvrij', 'Periodiek tot zelden overstroomd', 'Oever - vochtig',
         'Oever - drassig/vochtig', 'Oever - drassig', 'Oever - nat/drassig/vochtig', 'Oever - nat',
         'Ondiep', 'Matig diep', 'Diep', 'Zeer diep/diep'],
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        'HYDROLOGIE'
    )

    hydrologie_image = ee.Image().int().paint(ecotop_hydrology, 'HYDROLOGIE')
    shoreline = hydrologie_image.gte(3).And(hydrologie_image.lte(7))
    terrestrial = hydrologie_image.lte(2)
    no_succession = hydrologie_image.gte(8)

    # Prepare starting Image
    classified_image = ee.Image(classified_images.filterDate(
        ee.Date.fromYMD(start_year, 1, 1),
        ee.Date.fromYMD(start_year, 12, 31)).first()
                                )
    roughness_image = classified_image.remap([1, 2, 3, 4, 5, 6], [0.0, 0.15, 0.39, 1.45, 12.84, 24.41]).rename(
        "predicted")
    classified_image_shore = classified_image.updateMask(shoreline)
    classified_image_terrestrial = classified_image.updateMask(terrestrial)
    classified_image_no_succession = classified_image.updateMask(no_succession)
    roughness_no_succession = roughness_image.updateMask(no_succession)

    # Shoreline Evolution Rates
    # 10% grass will change into herb in 10 yr
    grass_to_herb = ee.Number(0.1)
    # 40% herbaceous veg will change to shrubs in 10 yr
    herb_to_willow = ee.Number(0.4)
    # 10% of shrubs will change into forest in 10 yr
    willow_to_forest = ee.Number(0.1)

    cumulative_shore = prepare_voorspel_data(classified_image_shore,
                                             ecotop_features,
                                             grass_to_herb,
                                             herb_to_willow,
                                             willow_to_forest,
                                             feature,
                                             start_date,
                                             num_years)

    # Terrestrial Evolution Rates
    # 10% grass will change into herb in 10 yr (same as shoreline)
    # 60% herbaceous veg will change to shrubs in 10 yr
    herb_to_willow = ee.Number(0.6)
    # 20% of shrubs will change into forest in 10 yr
    willow_to_forest = ee.Number(0.2)
    # Forrest remains forest

    cumulative_terrestrial = prepare_voorspel_data(classified_image_terrestrial,
                                                   ecotop_features,
                                                   grass_to_herb,
                                                   herb_to_willow,
                                                   willow_to_forest,
                                                   feature,
                                                   start_date,
                                                   num_years)

    total_roughness_images = merge_roughness_regions(classified_image, cumulative_shore, cumulative_terrestrial,
                                                     roughness_no_succession)
    return total_roughness_images


def get_roughness_info(prediction_images):
    def add_date(i):
        return i.set('system:time_start', ee.Date(i.get('system:time_start')))

    # def mask_images(i):
    #     return i.mask(i.neq(0)).rename("voorspeldeRuwheid")

    def class_to_roughness(i):
        class_values = [1, 2, 3, 4, 5, 6]
        class_roughness = [0.0, 0.15, 0.39, 1.45, 12.84, 24.41]
        return i.remap(class_values, class_roughness).rename("ruwheid")

    predict_start = ee.Date('2019-06-01')
    prediction_images = prediction_images.map(add_date)
    prediction_images = prediction_images.filterDate(predict_start, predict_start.advance(10, 'years'))

    # ecotop_features = ee.FeatureCollection("users/gertjang/succession/ecotopen_cyclus_drie_rijntakken_utm31n")
    image_collection = ee.ImageCollection('users/rogersckw9/vegetatiemonitor/yearly-classified-images')
    empty = ee.Image().set("system:time_start", ee.Date("2012-06-01").millis()).rename("ruwheid")
    image_collection = image_collection.merge(ee.ImageCollection([empty])).sort("system:time_start")
    # ecotopen_images = ecotopen_images.map(add_date)
    # ecotopen_images = ecotopen_images.map(class_to_roughness)
    # ecotopen_images = ecotopen_images.select(['remapped'], ['ecotoop'])

    # filter collection only on growth season for display
    image_collection = image_collection.map(add_date)
    image_collection = image_collection.map(class_to_roughness)

    merged_collection = image_collection.merge(prediction_images)  # .merge(ecotopen_rough)

    return merged_collection


def get_voorspel_timeseries(region, collection, scale):
    feature = ee.FeatureCollection(region["features"]).first()
    geom = feature.geometry()
    times = ee.List(collection.aggregate_array('system:time_start')) \
        .map(to_date_time_string).getInfo()

    reducer = ee.Reducer.mean()

    def reduce_mean(i):
        mean_roughness = i.reduceRegion(reducer, geom, scale)
        return i.set({'mean': mean_roughness})

    info = collection.map(reduce_mean)
    info = info.aggregate_array('mean').getInfo()

    timeseries = [{
        "xAxis": {
            "data": times
        },
        "yAxis": {
            "type": "value"
        },
        "series": []
    }]

    all_keys = set().union(*(d.keys() for d in info))
    for key in all_keys:
        timeseries[0]["series"].append({"name": key, "data": [], "type": "line"})

    for time, value in zip(times, info):
        for k, key in enumerate(all_keys):
            val = next((item for item in value if list(value)[0] == key), None)
            # print(val, key)
            if not val:
                timeseries[0]["series"][k]["data"].append("-")
            else:
                #     item = d.get("type", None) == str(k)
                timeseries[0]["series"][k]["data"].append(value[val])

    return timeseries


@app.route('/voorspel/', methods=['POST'])
@flask_cors.cross_origin()
def get_voorspel():
    json = request.get_json()

    region = json['region']
    # classified_images =
    # date_begin = None
    # date_end = None
    #
    # if 'dateBegin' in json:
    #     date_begin = ee.Date(json['dateBegin'])
    #
    # if 'dateEnd' in json:
    #     date_end = ee.Date(json['dateEnd'])

    scale = 10
    if 'scale' in json:
        scale = json['scale']

    begin_year = 2018
    num_years = 10
    start_date = ee.Date.fromYMD(begin_year, 6, 1)
    future_roughness_images = predict_roughness(region, start_date, num_years)
    total_roughness_images = future_roughness_images.map(calculate_total_roughness)
    roughness_collection = get_roughness_info(total_roughness_images)
    info = get_voorspel_timeseries(region, roughness_collection, scale)

    return jsonify(info)


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


def _compound_tile_index(tx, ty):
    return tx * 100000 + ty


@app.route('/get_times_by_tiles/', methods=['POST'])
@flask_cors.cross_origin()
def get_times_by_tiles():
    json = request.get_json()

    db = firestore.Client()
    tile_images_ref = db.collection(u's2-tile-cache')

    tilesMin = json['tilesMin']
    tilesMax = json['tilesMax']
    print('tilesMin: ', tilesMin)
    print('tilesMax: ', tilesMax)

    tile_images = {}
    # times = set()
    txty_min = _compound_tile_index(tilesMin['tx'], tilesMin['ty'])
    txty_max = _compound_tile_index(tilesMax['tx'], tilesMax['ty'])

    tile_images_query = tile_images_ref.where(u'txty', u'>=', txty_min).where(u'txty', u'<=', txty_max) \
        .select(['image_time', 'image_id'])

    for tile_image in tile_images_query.stream():
        tile_image = tile_image.to_dict()
        tile_images[tile_image['image_time']] = {
            'id': tile_image['image_id'],
            'time': tile_image['image_time']
        }

        # times.add(tile_image['image_time'])

    # times = list(times)

    times = list(tile_images.keys())

    date_list = []
    for time in times:
        date_list.append({
            "date": datetime.fromtimestamp(time/1000.0).strftime('%Y-%m-%d'),
            "dateFormat": 'YYYY-MM-DD',
            "type": "instance"
        })

    return jsonify(date_list)


@app.route('/update_cloudfree_tile_images/', methods=['GET'])
@flask_cors.cross_origin()
def update_cloudfree_tile_images():
    aoi = ee.FeatureCollection('users/gdonchyts/vegetation-monitor-aoi').geometry()
    tiles = ee.FeatureCollection('users/gdonchyts/vegetation-monitor-tiles-z10')  # .limit(2)

    date_end = datetime.today()
    date_begin = date_end - timedelta(days=365)

    def get_tile_images(tile):
        region = tile.geometry().intersection(aoi, 500)
        images = get_satellite_images(region, date_begin, date_end, True)

        def set_tile_properties(i):
            tile_image = ee.Feature(None).copyProperties(tile)
            tile_image = tile_image.set('image_time', i.get('system:time_start'))
            tile_image = tile_image.set('image_id', ee.String('COPERNICUS/S2/').cat(i.id()))

            return tile_image

        return images.map(set_tile_properties)

    tile_images = tiles.map(get_tile_images).flatten()
    tile_images = ee.FeatureCollection(tile_images).getInfo()

    tile_images = [f['properties'] for f in tile_images['features']]

    db = firestore.Client()
    tile_images_ref = db.collection(u's2-tile-cache')

    # delete previous tile_image records
    for tile in tile_images_ref.stream():
        tile.reference.delete()

    # add new tile_image records
    for tile_image in tile_images:
        t = tile_images_ref.document()
        tile_image['txty'] = _compound_tile_index(tile_image['tx'], tile_image['ty'])
        t.set(tile_image)

    return 'DONE'


@app.route('/get_cloudfree_tile_image_count/', methods=['GET'])
@flask_cors.cross_origin()
def get_cloudfree_tile_image_count():
    db = firestore.Client()
    tile_images = db.collection(u's2-tile-cache').list_documents()

    return str(len(list(tile_images)))


@app.route('/')
@flask_cors.cross_origin()
def root():
    """
    Redirect default page to API docs.
    :return:
    """

    print('redirecting ...')
    return redirect(request.url + 'apidocs')
