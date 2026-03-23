"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL === undefined
  ? "http://localhost:8002"
  : process.env.NEXT_PUBLIC_API_URL;

export function SyncButton({ onSyncComplete }: { onSyncComplete?: () => void }) {
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [withingsConnected, setWithingsConnected] = useState<boolean | null>(null);

  useEffect(() => {
    api.getWithingsStatus().then((s) => setWithingsConnected(s.connected)).catch(() => {});
  }, []);

  async function handleSync() {
    setSyncing(true);
    setMessage(null);
    const results: string[] = [];

    try {
      const garmin = await api.syncGarmin();
      if (garmin.errors && garmin.errors.length > 0) {
        results.push(`Garmin: ${garmin.errors[0]}`);
      } else {
        results.push(`Garmin: ${garmin.activities_synced} activities, ${garmin.health_days_synced} health`);
      }
    } catch (err) {
      results.push(`Garmin: ${err instanceof Error ? err.message : "failed"}`);
    }

    if (withingsConnected) {
      try {
        await api.syncWithings();
        results.push("Withings: synced");
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : "failed";
        if (errMsg.includes("expired") || errMsg.includes("reconnect") || errMsg.includes("401")) {
          setWithingsConnected(false);
          results.push("Withings: session expired — reconnect needed");
        } else {
          results.push(`Withings: ${errMsg}`);
        }
      }
    }

    setMessage(results.join(" · "));
    onSyncComplete?.();
    setSyncing(false);
  }

  function handleWithingsConnect() {
    window.open(`${API_BASE}/api/withings/connect`, "_blank", "width=600,height=700");
    const interval = setInterval(async () => {
      try {
        const status = await api.getWithingsStatus();
        if (status.connected) {
          setWithingsConnected(true);
          setMessage(null);
          clearInterval(interval);
        }
      } catch {}
    }, 2000);
    setTimeout(() => clearInterval(interval), 120000);
  }

  return (
    <div className="flex items-center gap-2">
      <Button onClick={handleSync} disabled={syncing} size="sm" variant="outline">
        <svg className={`w-4 h-4 mr-1.5 ${syncing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M1 4v6h6M23 20v-6h-6" />
          <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
        </svg>
        {syncing ? "Syncing..." : "Sync"}
      </Button>
      {withingsConnected === false && (
        <Button onClick={handleWithingsConnect} size="sm" variant="outline">
          Connect Withings
        </Button>
      )}
      {message && <span className="text-xs text-muted-foreground max-w-xs truncate">{message}</span>}
    </div>
  );
}
