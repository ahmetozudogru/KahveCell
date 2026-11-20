import json
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import HTTPException

from app.schemas.admin import GeocodeRequest
from app.services import geocoding
from app.services.geocoding import geocode_address


class GeocodingTests(unittest.TestCase):
    def setUp(self) -> None:
        geocoding._last_request_started = 0.0

    @patch("app.services.geocoding.sleep")
    @patch("app.services.geocoding.urlopen")
    def test_address_returns_coordinates_from_nominatim(
        self,
        mock_urlopen,
        _mock_sleep,
    ) -> None:
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                [
                    {
                        "lat": "39.9208",
                        "lon": "32.8541",
                        "display_name": "Kızılay, Ankara, Türkiye",
                    }
                ]
            ).encode()
        )

        result = geocode_address(GeocodeRequest(address="Kızılay, Ankara").address)

        self.assertEqual(result.latitude, 39.9208)
        self.assertEqual(result.longitude, 32.8541)
        self.assertEqual(result.display_name, "Kızılay, Ankara, Türkiye")
        request = mock_urlopen.call_args.args[0]
        self.assertIn("nominatim.openstreetmap.org", request.full_url)
        self.assertIn("K%C4%B1z%C4%B1lay", request.full_url)

    @patch("app.services.geocoding.sleep")
    @patch("app.services.geocoding.urlopen")
    def test_address_not_found_returns_actionable_error(
        self,
        mock_urlopen,
        _mock_sleep,
    ) -> None:
        mock_urlopen.return_value = BytesIO(b"[]")

        with self.assertRaises(HTTPException) as error:
            geocode_address("Bilinmeyen yer")

        self.assertEqual(error.exception.status_code, 404)
        self.assertIn("elle girin", error.exception.detail)

    @patch("app.services.geocoding.sleep")
    @patch("app.services.geocoding.urlopen")
    def test_service_failure_returns_manual_entry_guidance(
        self,
        mock_urlopen,
        _mock_sleep,
    ) -> None:
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("network unavailable")

        with self.assertRaises(HTTPException) as error:
            geocode_address("Kızılay, Ankara")

        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("elle girebilirsiniz", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
