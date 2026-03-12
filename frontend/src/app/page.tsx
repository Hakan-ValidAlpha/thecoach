"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, DashboardData, Briefing, SyncStatus } from "@/lib/api";
import { HealthCards } from "@/components/dashboard/health-cards";
import { RecentActivities } from "@/components/dashboard/recent-activities";
import { WeeklyMileageChart } from "@/components/charts/weekly-mileage-chart";
import { SyncButton } from "@/components/dashboard/sync-button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

function formatSyncTime(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  return `${diffDays}d ago`;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.getDashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  const loadSyncStatus = useCallback(() => {
    api.getSyncStatus().then(setSyncStatus).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadSyncStatus(); }, [loadSyncStatus]);

  useEffect(() => {
    api.getBriefing().then((b) => {
      if (b.status === "completed" && b.content) setBriefing(b);
    }).catch(() => {});
  }, []);

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
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          {syncStatus && (
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span>Garmin: {formatSyncTime(syncStatus.last_garmin_sync)}</span>
              <span>Withings: {formatSyncTime(syncStatus.last_withings_sync)}</span>
            </div>
          )}
        </div>
        <SyncButton onSyncComplete={() => { load(); loadSyncStatus(); }} />
      </div>

      {briefing && (
        <Link href="/coach" className="block">
          <Card className="border-primary/20 bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <span className="text-lg shrink-0">🌅</span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold">Today&apos;s Briefing</h3>
                    {briefing.changes_made && briefing.changes_made.length > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200 font-medium">
                        {briefing.changes_made.length} plan change{briefing.changes_made.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground line-clamp-2">{briefing.content}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      )}

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
