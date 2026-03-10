"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { api, ActivityDetail, TimeseriesData, TRAINING_TYPES } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDistance, formatDuration, formatPace, formatDate, formatTime } from "@/lib/format";
import { TimeseriesCharts } from "@/components/activity/timeseries-charts";

// Leaflet must be loaded client-side only (uses window)
const RouteMap = dynamic(
  () => import("@/components/activity/route-map").then((m) => m.RouteMap),
  { ssr: false, loading: () => <Skeleton className="h-[460px]" /> }
);

function activityTypeLabel(type: string | null): string {
  if (!type) return "Activity";
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const TRAINING_TYPE_COLORS: Record<string, string> = {
  easy_run: "bg-emerald-100 text-emerald-800 border-emerald-300",
  long_run: "bg-blue-100 text-blue-800 border-blue-300",
  tempo_run: "bg-orange-100 text-orange-800 border-orange-300",
  interval_run: "bg-red-100 text-red-800 border-red-300",
  hill_repeats: "bg-purple-100 text-purple-800 border-purple-300",
};

export default function ActivityDetailPage() {
  const params = useParams();
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = Number(params.id);
    if (isNaN(id)) return;

    api.getActivity(id).then(setActivity).catch((e) => setError(e.message));
    api.getActivityTimeseries(id).then(setTimeseries).catch(() => {});
  }, [params.id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (!activity) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-[460px]" />
      </div>
    );
  }

  const stats = [
    { label: "Distance", value: formatDistance(activity.distance_meters) },
    { label: "Duration", value: formatDuration(activity.duration_seconds) },
    { label: "Avg Pace", value: formatPace(activity.avg_pace_min_per_km) },
    { label: "Avg HR", value: activity.avg_heart_rate ? `${activity.avg_heart_rate} bpm` : "—" },
    { label: "Max HR", value: activity.max_heart_rate ? `${activity.max_heart_rate} bpm` : "—" },
    { label: "Calories", value: activity.calories ? `${activity.calories} kcal` : "—" },
    { label: "Cadence", value: activity.avg_cadence ? `${Math.round(activity.avg_cadence)} spm` : "—" },
    { label: "Elevation", value: activity.elevation_gain ? `${Math.round(activity.elevation_gain)} m` : "—" },
    { label: "Aerobic TE", value: activity.training_effect_aerobic ? activity.training_effect_aerobic.toFixed(1) : "—" },
    { label: "Anaerobic TE", value: activity.training_effect_anaerobic ? activity.training_effect_anaerobic.toFixed(1) : "—" },
    { label: "VO2 Max", value: activity.vo2max_estimate ? activity.vo2max_estimate.toFixed(1) : "—" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <Link href="/activities" className="text-sm text-primary hover:underline">
          &larr; Back to activities
        </Link>
      </div>

      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{activity.name || "Untitled"}</h1>
        <Badge variant="secondary">{activityTypeLabel(activity.activity_type)}</Badge>
      </div>
      <p className="text-muted-foreground">
        {formatDate(activity.started_at)} at {formatTime(activity.started_at)}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground mr-1">Training type:</span>
        {TRAINING_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={async (e) => {
              e.preventDefault();
              const newType = activity.training_type === t.value ? null : t.value;
              await api.updateTrainingType(activity.id, newType);
              setActivity({ ...activity, training_type: newType });
            }}
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors cursor-pointer ${
              activity.training_type === t.value
                ? TRAINING_TYPE_COLORS[t.value]
                : "border-border text-muted-foreground hover:border-foreground/30"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.filter((s) => s.value !== "—").map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="text-xl font-bold">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {activity.splits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Splits</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Km</th>
                    <th className="pb-2 pr-4">Pace</th>
                    <th className="pb-2 pr-4">Duration</th>
                    <th className="pb-2">Avg HR</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.splits.map((s) => (
                    <tr key={s.split_number} className="border-b border-border last:border-0">
                      <td className="py-2 pr-4 font-medium">{s.split_number}</td>
                      <td className="py-2 pr-4">{formatPace(s.avg_pace_min_per_km)}</td>
                      <td className="py-2 pr-4">{formatDuration(s.duration_seconds)}</td>
                      <td className="py-2">{s.avg_heart_rate ? `${s.avg_heart_rate} bpm` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {timeseries && timeseries.polyline.length > 0 && (
        <RouteMap polyline={timeseries.polyline} />
      )}

      {timeseries && timeseries.timeseries.length > 0 && (
        <TimeseriesCharts data={timeseries.timeseries} />
      )}
    </div>
  );
}
