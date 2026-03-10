"use client";

import { useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface RouteMapProps {
  polyline: [number, number][];
}

export function RouteMap({ polyline }: RouteMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapRef.current || polyline.length === 0) return;

    if (mapInstance.current) {
      mapInstance.current.remove();
      mapInstance.current = null;
    }

    const map = L.map(mapRef.current, {
      scrollWheelZoom: false,
      attributionControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);

    const latLngs = polyline.map(([lat, lng]) => L.latLng(lat, lng));
    const route = L.polyline(latLngs, {
      color: "#059669",
      weight: 4,
      opacity: 0.9,
    }).addTo(map);

    // Start marker (green)
    L.circleMarker(latLngs[0], {
      radius: 7,
      color: "#fff",
      weight: 2,
      fillColor: "#22c55e",
      fillOpacity: 1,
    }).addTo(map).bindTooltip("Start");

    // End marker (red)
    L.circleMarker(latLngs[latLngs.length - 1], {
      radius: 7,
      color: "#fff",
      weight: 2,
      fillColor: "#ef4444",
      fillOpacity: 1,
    }).addTo(map).bindTooltip("Finish");

    map.fitBounds(route.getBounds(), { padding: [30, 30] });
    mapInstance.current = map;

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, [polyline]);

  if (polyline.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Route</CardTitle>
      </CardHeader>
      <CardContent>
        <div ref={mapRef} className="h-[400px] w-full rounded-lg" />
      </CardContent>
    </Card>
  );
}
