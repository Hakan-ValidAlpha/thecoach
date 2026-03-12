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

const ACTIVITY_TYPES = [
  { value: "running", label: "Running" },
  { value: "trail_running", label: "Trail Running" },
  { value: "treadmill_running", label: "Treadmill" },
  { value: "walking", label: "Walking" },
  { value: "cycling", label: "Cycling" },
  { value: "swimming", label: "Swimming" },
  { value: "strength_training", label: "Strength" },
] as const;

export default function ActivitiesPage() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [trainingFilter, setTrainingFilter] = useState<string | null>(null);
  const [activityFilter, setActivityFilter] = useState<string | null>(null);
  const limit = 20;

  useEffect(() => {
    setLoading(true);
    api
      .getActivities({
        limit,
        offset,
        training_type: trainingFilter || undefined,
        activity_type: activityFilter || undefined,
      })
      .then(setActivities)
      .finally(() => setLoading(false));
  }, [offset, trainingFilter, activityFilter]);

  function handleTrainingFilterChange(type: string | null) {
    setTrainingFilter(type);
    setOffset(0);
  }

  function handleActivityFilterChange(type: string | null) {
    setActivityFilter(type);
    setOffset(0);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Activities</h1>

      <div className="flex items-center gap-3">
        <select
          value={activityFilter || ""}
          onChange={(e) => handleActivityFilterChange(e.target.value || null)}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All types</option>
          {ACTIVITY_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select
          value={trainingFilter || ""}
          onChange={(e) => handleTrainingFilterChange(e.target.value || null)}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All training</option>
          {TRAINING_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
          <option value="unlabeled">Unlabeled</option>
        </select>
        {(activityFilter || trainingFilter) && (
          <button
            onClick={() => { handleActivityFilterChange(null); handleTrainingFilterChange(null); }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : activities.length === 0 ? (
        <p className="text-muted-foreground">No activities found.</p>
      ) : (
        <div className="space-y-4">
          {activities.map((a) => (
            <Link key={a.id} href={`/activities/${a.id}`} className="block">
              <Card className="transition-colors hover:bg-muted">
                <CardContent className="p-4">
                  <div className="flex flex-col gap-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-medium truncate">{a.name || "Untitled"}</span>
                          <Badge variant="secondary" className="shrink-0 text-[10px]">{activityTypeLabel(a.activity_type)}</Badge>
                          {a.training_type && (
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0 ${TRAINING_TYPE_COLORS[a.training_type] || "bg-gray-100 text-gray-800"}`}>
                              {trainingTypeLabel(a.training_type)}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(a.started_at)} at {formatTime(a.started_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-4 text-sm">
                      <div>
                        <p className="font-medium">{formatDistance(a.distance_meters)}</p>
                        <p className="text-[10px] text-muted-foreground">Distance</p>
                      </div>
                      <div>
                        <p className="font-medium">{formatDuration(a.duration_seconds)}</p>
                        <p className="text-[10px] text-muted-foreground">Duration</p>
                      </div>
                      <div>
                        <p className="font-medium">{formatPace(a.avg_pace_min_per_km)}</p>
                        <p className="text-[10px] text-muted-foreground">Pace</p>
                      </div>
                      {a.avg_heart_rate && (
                        <div>
                          <p className="font-medium">{a.avg_heart_rate}</p>
                          <p className="text-[10px] text-muted-foreground">Avg HR</p>
                        </div>
                      )}
                    </div>
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
