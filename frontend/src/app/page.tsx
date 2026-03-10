"use client";

import { useEffect, useState, useCallback } from "react";
import { api, DashboardData } from "@/lib/api";
import { HealthCards } from "@/components/dashboard/health-cards";
import { RecentActivities } from "@/components/dashboard/recent-activities";
import { WeeklyMileageChart } from "@/components/charts/weekly-mileage-chart";
import { SyncButton } from "@/components/dashboard/sync-button";
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.getDashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <SyncButton onSyncComplete={load} />
        </div>
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-80" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <SyncButton onSyncComplete={load} />
      </div>

      <HealthCards
        health={data.health_snapshot}
        weekDistance={data.current_week_distance_km}
        weekRuns={data.current_week_run_count}
        trends={data.trends}
      />

      <WeeklyMileageChart data={data.weekly_mileage} />

      <RecentActivities activities={data.recent_activities} />
    </div>
  );
}
