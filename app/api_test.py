import json
import pytest

from . import main

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

    r = client.post('/map/legger/zonal-info/', data=input, content_type='application/json')

    assert r.status_code == 200

    output = sorted(json.loads(r.get_data(as_text=True)))

    output_expected = '''[
        {
           "id": 1,
           "area_per_type": [
                {"area": 567062.7642463235, "type": "0"}, 
                {"area": 1624781.6086224725, "type": "1"}, 
                {"area": 252953.091796875, "type": "2"}, 
                {"area": 1854597.840469899, "type": "3"}, 
                {"area": 682186.362109375, "type": "4"}, 
                {"area": 382541.0576171875, "type": "5"}, 
                {"area": 104886.63330078125, "type": "6"}
           ]
        }
    ]'''

    output_expected = sorted(json.loads(output_expected))

    open('test_output_zonal_legger.json', 'w').write(json.dumps(output))

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

    r = client.post('/map/landuse/zonal-info/', data=input, content_type='application/json')

    assert r.status_code == 200

    output = sorted(json.loads(r.get_data(as_text=True)))

    output_expected = '''[
        {
            "id": 1, 
            "area_per_type": [
                {"type": "", "area": 567062.7642463235}, 
                {"type": "Water", "area": 1624781.6086224725}, 
                {"type": "Verhard oppervlak", "area": 252953.091796875}, 
                {"type": "Gras en Akker", "area": 1854597.840469899}, 
                {"type": "Riet en Ruigte", "area": 682186.362109375}, 
                {"type": "Bos", "area": 382541.0576171875}, 
                {"type": "Struweel", "area": 104886.63330078125}
            ]
        }
    ]'''

    output_expected = sorted(json.loads(output_expected))

    open('test_output_zonal_landuse.json', 'w').write(json.dumps(output))

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

    r = client.post('/map/landuse/', data=input, content_type='application/json')

    assert r.status_code == 200

    output = json.loads(r.get_data(as_text=True))

    open('test_output_landuse.json', 'w').write(r.get_data(as_text=True))

    # https://earthengine.googleapis.com/map/ee6293d9845774ab8ae9c34b72b6d739/{z}/{x}/{y}?token=ec331d0b872fb8b60e1be59da49d3600
    assert 'https://earthengine.googleapis.com/map/' in output['url']
    assert '{z}/{x}/{y}' in output['url']
