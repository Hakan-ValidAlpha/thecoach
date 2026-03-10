"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Activity, TRAINING_TYPES } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDistance, formatDuration, formatPace, formatDate, formatTime } from "@/lib/format";

function activityTypeLabel(type: string | null): string {
  if (!type) return "Activity";
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function trainingTypeLabel(type: string | null): string {
  if (!type) return "";
  const found = TRAINING_TYPES.find((t) => t.value === type);
  return found ? found.label : type;
}

const TRAINING_TYPE_COLORS: Record<string, string> = {
  easy_run: "bg-emerald-100 text-emerald-800",
  long_run: "bg-blue-100 text-blue-800",
  tempo_run: "bg-orange-100 text-orange-800",
  interval_run: "bg-red-100 text-red-800",
  hill_repeats: "bg-purple-100 text-purple-800",
};

export default function ActivitiesPage() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<string | null>(null);
  const limit = 20;

  useEffect(() => {
    setLoading(true);
    api
      .getActivities({
        limit,
        offset,
        training_type: filter || undefined,
      })
      .then(setActivities)
      .finally(() => setLoading(false));
  }, [offset, filter]);

  function handleFilterChange(type: string | null) {
    setFilter(type);
    setOffset(0);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Activities</h1>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={filter === null ? "default" : "outline"}
          size="sm"
          onClick={() => handleFilterChange(null)}
        >
          All
        </Button>
        {TRAINING_TYPES.map((t) => (
          <Button
            key={t.value}
            variant={filter === t.value ? "default" : "outline"}
            size="sm"
            onClick={() => handleFilterChange(t.value)}
          >
            {t.label}
          </Button>
        ))}
        <Button
          variant={filter === "unlabeled" ? "default" : "outline"}
          size="sm"
          onClick={() => handleFilterChange("unlabeled")}
        >
          Unlabeled
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : activities.length === 0 ? (
        <p className="text-muted-foreground">No activities found.</p>
      ) : (
        <div className="space-y-3">
          {activities.map((a) => (
            <Link key={a.id} href={`/activities/${a.id}`}>
              <Card className="transition-colors hover:bg-muted">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{a.name || "Untitled"}</span>
                      <Badge variant="secondary">{activityTypeLabel(a.activity_type)}</Badge>
                      {a.training_type && (
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${TRAINING_TYPE_COLORS[a.training_type] || "bg-gray-100 text-gray-800"}`}>
                          {trainingTypeLabel(a.training_type)}
                        </span>
                      )}
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {formatDate(a.started_at)} at {formatTime(a.started_at)}
                    </span>
                  </div>
                  <div className="flex gap-6 text-right text-sm">
                    <div>
                      <p className="font-medium">{formatDistance(a.distance_meters)}</p>
                      <p className="text-muted-foreground">Distance</p>
                    </div>
                    <div>
                      <p className="font-medium">{formatDuration(a.duration_seconds)}</p>
                      <p className="text-muted-foreground">Duration</p>
                    </div>
                    <div>
                      <p className="font-medium">{formatPace(a.avg_pace_min_per_km)}</p>
                      <p className="text-muted-foreground">Pace</p>
                    </div>
                    {a.avg_heart_rate && (
                      <div>
                        <p className="font-medium">{a.avg_heart_rate} bpm</p>
                        <p className="text-muted-foreground">Avg HR</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={activities.length < limit} onClick={() => setOffset(offset + limit)}>
          Next
        </Button>
      </div>
    </div>
  );
}
