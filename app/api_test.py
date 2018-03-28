import json
import pytest

from . import main

@pytest.fixture()
def client():
    main.api.app.testing = True

    return main.api.app.test_client()

def test_get_image_urls(client):
    input = '''{
        "dateBegin": "2017-07-01",
        "dateEnd": "2017-07-15",
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

    assert output[0]["area_per_type"] == output_expected[0]["area_per_type"]
