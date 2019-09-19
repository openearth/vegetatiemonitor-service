import json
import pytest
import ee

from . import main
from .api import prepare_voorspel_data, wet_moist_masks, bare_grazing_variables, calculate_total_roughness


@pytest.fixture()
def client():
    print(dir(main))

    main.app.testing = True

    return main.app.test_client()


def test_get_zonal_info_legger(client):
    input = '''{
        "region": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [5.846,51.984],
                            [5.849,51.961],
                            [5.910,51.960],
                            [5.916,51.985],
                            [5.877,51.990],
                            [5.846,51.984]
                        ]]
                    },
                    "properties": {
                        "id": 1
                    }
                }
            ]
        },
        "scale": 100
        }'''

    r = client.post('/map/legger/zonal-info/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)
    open('test_output_zonal_legger.json', 'w').write(s)

    output = sorted(json.loads(s))

    output_expected = '''[
      {
        "area_per_type": [
          {
            "area": 1790886.72332644,
            "type": "1"
          },
          {
            "area": 455036.860223269,
            "type": "2"
          },
          {
            "area": 2252862.6694067856,
            "type": "3"
          },
          {
            "area": 650561.147265625,
            "type": "4"
          },
          {
            "area": 364032.44482421875,
            "type": "5"
          },
          {
            "area": 207065.13603515626,
            "type": "6"
          }
        ],
        "id": 1
      }
    ]'''

    output_expected = sorted(json.loads(output_expected))

    assert output[0]["area_per_type"] == output_expected[0]["area_per_type"]


def test_get_zonal_info_landuse(client):
    input = '''{
        "region": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [5.846,51.984],
                            [5.849,51.961],
                            [5.910,51.960],
                            [5.916,51.985],
                            [5.877,51.990],
                            [5.846,51.984]
                        ]]
                    },
                    "properties": {
                        "id": 1
                    }
                }
            ]
        },
        "dateBegin":"2016-07-20",
        "dateEnd":"2016-07-21",
        "scale": 100
        }'''

    r = client.post('/map/landuse/zonal-info/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)
    open('test_output_zonal_landuse.json', 'w').write(s)

    output = sorted(json.loads(s))

    output_expected = '''[
      {
        "area_per_type": [
          {
            "area": 2195869.233553539,
            "type": "1"
          },
          {
            "area": 965375.9703986673,
            "type": "2"
          },
          {
            "area": 2063152.831169577,
            "type": "3"
          },
          {
            "area": 778296.2523360907,
            "type": "4"
          },
          {
            "area": 293278.7791819853,
            "type": "5"
          },
          {
            "area": 345519.912109375,
            "type": "6"
          }
        ],
        "id": 1
      }
    ]'''


    output_expected = sorted(json.loads(output_expected))

    assert output[0]["area_per_type"] == output_expected[0]["area_per_type"]


def test_get_map_landuse(client):
    input = '''{
                   "dateBegin": "2016-07-20",
                   "dateEnd": "2016-07-21",
                   "region": {
                       "coordinates": [[
                           [5.846, 51.984],
                           [5.849, 51.961],
                           [5.91, 51.96],
                           [5.916, 51.985],
                           [5.877, 51.99],
                           [5.846, 51.984]]],
                       "geodesic": true,
                       "type": "Polygon"
                   }
    }'''

    r = client.post('/map/landuse/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_landuse.json', 'w').write(r.get_data(as_text=True))

    # https://earthengine.googleapis.com/map/ee6293d9845774ab8ae9c34b72b6d739/{z}/{x}/{y}?token=ec331d0b872fb8b60e1be59da49d3600
    assert 'https://earthengine.googleapis.com/map/' in output['url']
    assert '{z}/{x}/{y}' in output['url']


def test_export_landuse(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "region": {
           "coordinates": [[
               [5.846, 51.984],
               [5.849, 51.961],
               [5.91, 51.96],
               [5.916, 51.985],
               [5.877, 51.99],
               [5.846, 51.984]]],
           "geodesic": true,
           "type": "Polygon"
       }
    }'''

    r = client.post('/map/landuse/export/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_export_landuse.json', 'w').write(
        r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_ndvi(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "region": {
           "coordinates": [[
               [5.846, 51.984],
               [5.849, 51.961],
               [5.91, 51.96],
               [5.916, 51.985],
               [5.877, 51.99],
               [5.846, 51.984]]],
           "geodesic": true,
           "type": "Polygon"
       }
    }'''

    r = client.post('/map/ndvi/export/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_export_ndvi.json', 'w').write(r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_landuse_vs_legger(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "region": {
           "coordinates": [[
               [5.846, 51.984],
               [5.849, 51.961],
               [5.91, 51.96],
               [5.916, 51.985],
               [5.877, 51.99],
               [5.846, 51.984]]],
           "geodesic": true,
           "type": "Polygon"
       }
    }'''

    r = client.post('/map/landuse-vs-legger/export/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_export_landuse_vs_legger.json', 'w').write(
        r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_satellite_image(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "region": {
           "coordinates": [[
               [5.846, 51.984],
               [5.849, 51.961],
               [5.91, 51.96],
               [5.916, 51.985],
               [5.877, 51.99],
               [5.846, 51.984]]],
           "geodesic": true,
           "type": "Polygon"
       },
       "vis": {
            "bands": ["swir", "nir", "green"],
            "min": 0.03, 
            "max": 0.5
       }
    }'''

    r = client.post('/map/satellite/export/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_export_satellite.json', 'w').write(
        r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']

def test_get_zonal_timeseries_landuse(client):
    input = '''{
        "scale": 30,
        "region": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [5.846, 51.984],
                            [5.849, 51.961],
                            [5.910, 51.960],
                            [5.916, 51.985],
                            [5.877, 51.990],
                            [5.846, 51.984]
                        ]
                    ]
                },
                "properties": {
                    "id": 1
                }
            }]
        }
    }'''

    r = client.post('/map/landuse/zonal-timeseries/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)
    # open('test_output_zonal_timeseries_landuse.json', 'w').write(s)

    output = sorted(json.loads(s))

    assert len(output[0]["series"]) == 6

def test_get_zonal_timeseries_landuse(client):
    r = client.post('/map/landuse/zonal-timeseries/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)


def test_wet_moist_masks():
    start_date = ee.Date('2018-11-01')
    feature = ee.Feature(
        ee.Geometry.Polygon(
            [[[6.0115432966861135, 51.88332509634447],
              [6.0286236036929495, 51.87898050435874],
              [6.025705360284746, 51.88655677657944],
              [6.011972450128496, 51.88660975300831]]]
        )
    )
    moisture_masks = wet_moist_masks(start_date, feature)
    assert moisture_masks.bandNames().getInfo() == ['moistMask', 'wetMask']

def test_bare_grazing():
    ecotop_features = ee.FeatureCollection("users/gertjang/succession/ecotopen_cyclus_drie_rijntakken_utm31n")
    start_date = ee.Date('2018-11-01')
    feature = ee.Feature(
        ee.Geometry.Polygon(
            [[[6.0115432966861135, 51.88332509634447],
              [6.0286236036929495, 51.87898050435874],
              [6.025705360284746, 51.88655677657944],
              [6.011972450128496, 51.88660975300831]]]
        )
    )

    class_values = [1, 2, 3, 4, 5, 6]
    class_roughness = [0.0, 0.15, 0.39, 1.45, 12.84, 24.41]

    start_year = start_date.get('year')
    lookback = start_date.advance(-1, 'year')

    image = ee.Image('users/rogersckw9/vegetatiemonitor/yearly-classified-images/classified-image-2018')
    # Convert image from classes to roughness
    image = image.remap(class_values, class_roughness)

    moisture_masks = wet_moist_masks(start_date, feature)
    wet_mask = moisture_masks.select('wetMask')
    moist_mask = moisture_masks.select('moistMask')

    mech_dyn_list = ['Onbekend', 'Gering dynamisch', 'Matig/gering dynamisch', 'Sterk/matig dynamisch',
                     'Sterk dynamisch']
    ecotoop_mech_dyn = ecotop_features.remap(mech_dyn_list, [0, 1, 2, 3, 4], 'MECH_DYN')

    mech_dyn_im = ee.Image().int().paint(ecotoop_mech_dyn, 'MECH_DYN')
    weak_dynamics = mech_dyn_im.eq(0).Or(mech_dyn_im.eq(1))
    moderate_dynamics = mech_dyn_im.eq(2)
    bare_to_reed_mask = image.eq(0.15).multiply(wet_mask).multiply(weak_dynamics)
    bare_to_willow_mask = image.eq(0.15).multiply(moist_mask).multiply(moderate_dynamics)
    bare_grazing_im = bare_grazing_variables(ecotop_features, bare_to_reed_mask, bare_to_willow_mask)
    assert bare_grazing_im.bandNames().getInfo() == ['bareToReedGrazing', 'bareToWillowGrazingA', 'bareToWillowGrazingB']

def test_prepare_voorspel_data():

    image = ee.Image('users/rogersckw9/vegetatiemonitor/yearly-classified-images/classified-image-2018')
    ecotop_features = ee.FeatureCollection("users/gertjang/succession/ecotopen_cyclus_drie_rijntakken_utm31n")
    grass_pct = ee.Number(0.1)
    herb_pct = ee.Number(0.4)
    willow_pct = ee.Number(0.1)
    feature = ee.Feature(
        ee.Geometry.Polygon(
            [[[6.0115432966861135, 51.88332509634447],
              [6.0286236036929495, 51.87898050435874],
              [6.025705360284746, 51.88655677657944],
              [6.011972450128496, 51.88660975300831]]]
        )
    )
    start_date = ee.Date('2018-11-01')
    years = 10

    cumulative_images = prepare_voorspel_data(image,
                                              ecotop_features,
                                              grass_pct,
                                              herb_pct,
                                              willow_pct,
                                              feature,
                                              start_date,
                                              years)

    assert cumulative_images.size().getInfo() == years+1
    first_image = ee.Image(cumulative_images.first())
    assert first_image.bandNames().getInfo() == ['waterRoughness', 'bareRoughness', 'grassRoughness',
                                 'herbaceousRoughness', 'forestRoughness', 'willowRoughness']

    total_roughness = cumulative_images.map(calculate_total_roughness)
    first_image = ee.Image(total_roughness.sort("system:time_start", False).first())
    mean_roughness = ee.Number(first_image.reduceRegion(ee.Reducer.max(), feature.geometry(), 10).get('total_roughness')).round().getInfo()
    assert mean_roughness == 2