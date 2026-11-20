import { useEffect } from 'react'
import L, { type LatLngExpression } from 'leaflet'
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import { Link } from 'react-router-dom'

import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIconRetina from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { Coordinates, Shop } from '../types/api'

const SHOP_ICON = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIconRetina,
  shadowUrl: markerShadow,
})

const USER_LOCATION_ICON = L.divIcon({
  className: 'user-location-marker',
  iconAnchor: [11, 11],
  iconSize: [22, 22],
})

interface ShopMapProps {
  shops: Shop[]
  userLocation: Coordinates
}

function FitMapToShops({ shops, userLocation }: ShopMapProps) {
  const map = useMap()

  useEffect(() => {
    const points: LatLngExpression[] = [
      ...shops.map(
        (shop) => [shop.latitude, shop.longitude] as LatLngExpression,
      ),
      [userLocation.latitude, userLocation.longitude],
    ]

    if (points.length === 1) {
      map.setView(points[0], 13)
    } else {
      map.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 13 })
    }
  }, [map, shops, userLocation])

  return null
}

export function ShopMap({ shops, userLocation }: ShopMapProps) {
  return (
    <div className="map-frame">
      <MapContainer
        center={[userLocation.latitude, userLocation.longitude]}
        zoom={12}
        scrollWheelZoom
        className="map"
      >
        <FitMapToShops shops={shops} userLocation={userLocation} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {shops.map((shop) => (
          <Marker
            icon={SHOP_ICON}
            key={shop.id}
            position={[shop.latitude, shop.longitude]}
          >
            <Popup>
              <Link
                state={{ userLocation }}
                to={`/shops/${shop.id}`}
              >
                {shop.name}
              </Link>
              <br />
              {shop.address}
            </Popup>
          </Marker>
        ))}
        <Marker
          icon={USER_LOCATION_ICON}
          position={[userLocation.latitude, userLocation.longitude]}
          zIndexOffset={1000}
        >
          <Popup>Konumunuz</Popup>
        </Marker>
      </MapContainer>
    </div>
  )
}
