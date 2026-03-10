import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DailyHealth, DashboardTrends, TrendIndicator } from "@/lib/api";
import { formatSleepDuration } from "@/lib/format";

interface HealthCardsProps {
  health: DailyHealth | null;
  weekDistance: number;
  weekRuns: number;
  trends: DashboardTrends;
}

function TrendArrow({ trend, invertColor }: { trend: TrendIndicator | null; invertColor?: boolean }) {
  if (!trend) return null;

  const arrows = { up: "\u2191", down: "\u2193", unchanged: "\u2192" };
  const colors = {
    up: invertColor ? "text-red-500" : "text-emerald-500",
    down: invertColor ? "text-emerald-500" : "text-red-500",
    unchanged: "text-muted-foreground",
  };

  return (
    <span className={`ml-2 text-sm font-semibold ${colors[trend.direction]}`}>
      {arrows[trend.direction]}
    </span>
  );
}

export function HealthCards({ health, weekDistance, weekRuns, trends }: HealthCardsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">This Week</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {weekDistance.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground ml-1">km</span>
            <TrendArrow trend={trends.weekly_distance} />
          </p>
          <p className="text-sm text-muted-foreground">{weekRuns} run{weekRuns !== 1 ? "s" : ""}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Resting HR</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {health?.resting_heart_rate ?? "\u2014"}
            {health?.resting_heart_rate && <span className="text-sm font-normal text-muted-foreground ml-1">bpm</span>}
            <TrendArrow trend={trends.resting_hr} invertColor />
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Sleep</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {formatSleepDuration(health?.sleep_duration_seconds)}
            <TrendArrow trend={trends.sleep_score} />
          </p>
          <p className="text-sm text-muted-foreground">Score: {health?.sleep_score ?? "\u2014"}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Body Battery</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-bold">
            {health?.body_battery_current ?? "\u2014"}
            {health?.body_battery_current != null && (
              <span className="text-sm font-normal text-muted-foreground">/100</span>
            )}
            <TrendArrow trend={trends.body_battery} />
          </p>
          <div className="flex gap-3 text-sm text-muted-foreground mt-1">
            {health?.body_battery_charged != null && (
              <span className="text-emerald-600">+{health.body_battery_charged} charged</span>
            )}
            {health?.body_battery_drained != null && (
              <span className="text-red-500">-{health.body_battery_drained} drained</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
