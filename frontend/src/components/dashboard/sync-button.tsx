"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

export function SyncButton({ onSyncComplete }: { onSyncComplete?: () => void }) {
  const [syncing, setSyncing] = useState(false);
  const [syncingWithings, setSyncingWithings] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [withingsConnected, setWithingsConnected] = useState<boolean | null>(null);

  useEffect(() => {
    api.getWithingsStatus().then((s) => setWithingsConnected(s.connected)).catch(() => {});
  }, []);

  async function handleGarminSync() {
    setSyncing(true);
    setMessage(null);
    try {
      const result = await api.syncGarmin();
      setMessage(
        `Synced ${result.activities_synced} activities, ${result.health_days_synced} health days`
      );
      onSyncComplete?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handleWithingsSync() {
    setSyncingWithings(true);
    setMessage(null);
    try {
      await api.syncWithings();
      setMessage("Withings sync started");
      onSyncComplete?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Withings sync failed");
    } finally {
      setSyncingWithings(false);
    }
  }

  function handleWithingsConnect() {
    window.open(`${API_BASE}/api/withings/connect`, "_blank", "width=600,height=700");
    // Poll for connection status after opening the window
    const interval = setInterval(async () => {
      try {
        const status = await api.getWithingsStatus();
        if (status.connected) {
          setWithingsConnected(true);
          clearInterval(interval);
        }
      } catch {}
    }, 2000);
    // Stop polling after 2 minutes
    setTimeout(() => clearInterval(interval), 120000);
  }

  return (
    <div className="flex items-center gap-2">
      <Button onClick={handleGarminSync} disabled={syncing} size="sm">
        {syncing ? "Syncing..." : "Sync Garmin"}
      </Button>
      {withingsConnected === true ? (
        <Button onClick={handleWithingsSync} disabled={syncingWithings} size="sm" variant="outline">
          {syncingWithings ? "Syncing..." : "Sync Withings"}
        </Button>
      ) : withingsConnected === false ? (
        <Button onClick={handleWithingsConnect} size="sm" variant="outline">
          Connect Withings
        </Button>
      ) : null}
      {message && <span className="text-sm text-muted-foreground">{message}</span>}
    </div>
  );
}
