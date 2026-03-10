import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity } from "@/lib/api";
import { formatDistance, formatDuration, formatPace, formatDate, formatTime } from "@/lib/format";

function activityTypeLabel(type: string | null): string {
  if (!type) return "Activity";
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function RecentActivities({ activities }: { activities: Activity[] }) {
  if (activities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Activities</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No activities yet. Sync your Garmin data to get started.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Recent Activities</CardTitle>
        <Link href="/activities" className="text-sm text-primary hover:underline">
          View all
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {activities.map((a) => (
            <Link
              key={a.id}
              href={`/activities/${a.id}`}
              className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-muted"
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{a.name || "Untitled"}</span>
                  <Badge variant="secondary">{activityTypeLabel(a.activity_type)}</Badge>
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
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
