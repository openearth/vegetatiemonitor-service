import json
import os
import random
import pytest

from . import main


@pytest.fixture()
def client():
    print(dir(main))

    main.app.testing = True

    return main.app.test_client()


def write_test_output(filename, s):
    dirname = '../output/test/'

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    path = os.path.join(dirname, filename)

    with open(path, 'w') as f:
        f.write(s)


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
    write_test_output('test_output_zonal_legger.json', s)

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


def test_get_zonal_info_landuse_daily(client):
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
        "assetType":"day",
        "scale": 100
        }'''

    r = client.post('/map/landuse/zonal-info/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)
    write_test_output('test_output_zonal_landuse.json', s)

    output = sorted(json.loads(s))

    output_expected = '''[
      {
        "area_per_type": [
          {
            "area": 2070230.8170802696,
            "type": "1"
          },
          {
            "area": 688500.925067019,
            "type": "2"
          },
          {
            "area": 1475154.438426777,
            "type": "3"
          },
          {
            "area": 1238260.7638825062,
            "type": "4"
          },
          {
            "area": 410510.32361557905,
            "type": "5"
          },
          {
            "area": 758932.494140625,
            "type": "6"
          }
        ],
        "id": 1
      }
    ]'''

    output_expected = sorted(json.loads(output_expected))

    assert output[0]["area_per_type"] == output_expected[0]["area_per_type"]


def test_get_zonal_info_landuse_yearly(client):
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
        "dateBegin":"2016-01-01",
        "dateEnd":"2017-01-01",
        "assetType":"year",
        "scale": 100
        }'''

    r = client.post('/map/landuse/zonal-info/', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)
    write_test_output('test_output_zonal_landuse_yearly.json', s)

    output = sorted(json.loads(s))

    output_expected = '''[{
        "area_per_type": [{
            "area": 772665.3883118873,
            "type": "1"
        }, {
            "area": 781310.6807100184,
            "type": "2"
        }, {
            "area": 2228946.2171243103,
            "type": "3"
        }, {
            "area": 1426625.1962354474,
            "type": "4"
        }, {
            "area": 584609.772332644,
            "type": "5"
        }, {
            "area": 178931.24853515625,
            "type": "6"
        }],
        "id": 1
    }]'''

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

    write_test_output('test_output_landuse.json', r.get_data(as_text=True))

    # https://earthengine.googleapis.com/map/ee6293d9845774ab8ae9c34b72b6d739/{z}/{x}/{y}?token=ec331d0b872fb8b60e1be59da49d3600
    assert 'https://earthengine.googleapis.com/map/' in output['url']
    assert '{z}/{x}/{y}' in output['url']


def test_export_landuse(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "assetType": "day",
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

    write_test_output('test_output_export_landuse.json', r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_ndvi(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "assetType": "day",
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

    write_test_output('test_output_export_ndvi.json', r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']

def test_export_ndvi_yearly(client):
    input = '''{
       "dateBegin": "2016-01-01",
       "dateEnd": "2017-01-01",
       "assetType": "year",
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

    open('test_output_export_ndvi_yearly.json', 'w').write(r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_landuse_vs_legger(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "assetType": "day",
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

    write_test_output('test_output_export_landuse_vs_legger.json', r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_export_satellite_image(client):
    input = '''{
       "dateBegin": "2016-07-20",
       "dateEnd": "2016-07-21",
       "assetType": "day",
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

    write_test_output('test_output_export_satellite.json', r.get_data(as_text=True))

    # https://earthengine.googleapis.com/api/download?docid=e14ce2ae37ba788858184239bfc6f8da&token=a1e12add29abf9abcbc11999db92c07e
    assert 'https://earthengine.googleapis.com/api/download' in output['url']


def test_get_times(client):
    input = '''{
        "region": {
          "geodesic": false,
          "crs": {
            "type": "name",
            "properties": {
              "name": "EPSG:3857"
            }
          },
          "type": "Polygon",
          "coordinates": [
            [
              [
                508764.86048223823,
                6770486.217669737
              ],
              [
                528332.7397234514,
                6770486.217669737
              ],
              [
                528332.7397234514,
                6790054.09691095
              ],
              [
                508764.86048223823,
                6790054.09691095
              ],
              [
                508764.86048223823,
                6770486.217669737
              ]
            ]
          ]
        }
        }'''

    # randomize coordinate to skip EE caching
    body = json.loads(input)
    body['region']['coordinates'][0][0][0] += random.random() / 10
    input = json.dumps(body)

    r = client.post('/map/satellite/times/daily', data=input,
                    content_type='application/json')

    assert r.status_code == 200

    s = r.get_data(as_text=True)

    # write_test_output('test_output_satellite_times_daily.json', s)

    times = json.loads(s)
    print('times: ', len(times))

    assert r.status_code == 200


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
    # write_test_output('test_output_zonal_timeseries_landuse.json', s)

    output = sorted(json.loads(s))

    assert len(output[0]["series"]) == 6


def test_voorspel(client):
    input = '''{
        "region": {
            "type": "FeatureCollection",
            "features": [
                {
                  "type": "Feature",
                  "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                      [
                        [
                          5.869412857055636,
                          51.97090473175753
                        ],
                        [
                          5.888209777832003,
                          51.96746759577021
                        ],
                        [
                          5.895419555664034,
                          51.978306898532956
                        ],
                        [
                          5.884690719604464,
                          51.98142601683456
                        ],
                        [
                          5.869412857055636,
                          51.97090473175753
                        ]
                      ]
                    ]
                  },
                  "id": "0",
                  "properties": {}
                }
            ]
        }
    }'''

    r = client.post('/voorspel/', data=input,
                    content_type='application/json')

    assert r.status_code == 200
    #
    # s = r.get_data(as_text=True)
    # output = sorted(json.loads(s))
    # print(output)
    # assert output[0]["series"][0]["data"][0] == 1.6977447813586202
