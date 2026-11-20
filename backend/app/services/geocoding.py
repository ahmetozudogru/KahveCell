import json
from threading import Lock
from time import monotonic, sleep
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.schemas.admin import GeocodeResponse

_REQUEST_INTERVAL_SECONDS = 1.1
_REQUEST_TIMEOUT_SECONDS = 8
_request_lock = Lock()
_last_request_started = 0.0


def geocode_address(address: str) -> GeocodeResponse:
    global _last_request_started

    query = urlencode({"q": address, "format": "jsonv2", "limit": 1})
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "KahveCell/0.1 (shop address lookup)",
        },
    )

    with _request_lock:
        wait_seconds = _REQUEST_INTERVAL_SECONDS - (
            monotonic() - _last_request_started
        )
        if wait_seconds > 0:
            sleep(wait_seconds)
        _last_request_started = monotonic()
        try:
            with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
                results = json.load(response)
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Adres servisine şu anda ulaşılamıyor. "
                    "Koordinatları elle girebilirsiniz."
                ),
            ) from error

    if not isinstance(results, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Adres servisi beklenmeyen bir yanıt verdi.",
        )
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Bu adres için konum bulunamadı. "
                "Adresi kontrol edin veya koordinatları elle girin."
            ),
        )

    first_result = results[0]
    try:
        latitude = float(first_result["lat"])
        longitude = float(first_result["lon"])
        display_name = str(first_result["display_name"])
        return GeocodeResponse(
            latitude=latitude,
            longitude=longitude,
            display_name=display_name,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Adres servisi geçerli koordinat döndürmedi.",
        ) from error
