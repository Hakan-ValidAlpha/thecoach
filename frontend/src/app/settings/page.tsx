"use client";

import { useEffect, useState } from "react";
import { api, AppSettings, SettingsUpdate } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL === undefined
  ? "http://localhost:8002"
  : process.env.NEXT_PUBLIC_API_URL;

function formatDate(d: string | null) {
  if (!d) return "Never";
  return new Date(d).toLocaleString();
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Form state
  const [heightCm, setHeightCm] = useState("");
  const [garminEmail, setGarminEmail] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [withingsClientId, setWithingsClientId] = useState("");
  const [withingsClientSecret, setWithingsClientSecret] = useState("");
  const [anthropicApiKey, setAnthropicApiKey] = useState("");
  // Profile state
  const [userName, setUserName] = useState("");
  const [age, setAge] = useState("");
  const [runningExperience, setRunningExperience] = useState("");
  const [primaryGoal, setPrimaryGoal] = useState("");
  const [goalRace, setGoalRace] = useState("");
  const [goalRaceDate, setGoalRaceDate] = useState("");
  const [gender, setGender] = useState("");
  const [injuriesNotes, setInjuriesNotes] = useState("");

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        setHeightCm(s.height_cm?.toString() || "");
        setGarminEmail(s.garmin_email || "");
        setWithingsClientId(s.withings_client_id || "");
        setUserName(s.user_name || "");
        setAge(s.age?.toString() || "");
        setGender(s.gender || "");
        setRunningExperience(s.running_experience || "");
        setPrimaryGoal(s.primary_goal || "");
        setGoalRace(s.goal_race || "");
        setGoalRaceDate(s.goal_race_date || "");
        setInjuriesNotes(s.injuries_notes || "");
      })
      .catch(() => setMessage({ type: "error", text: "Failed to load settings" }))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(section: string, update: SettingsUpdate) {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await api.updateSettings(update);
      setSettings(updated);
      setGarminPassword("");
      setWithingsClientSecret("");
      setAnthropicApiKey("");
      setMessage({ type: "success", text: `${section} saved successfully` });
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  function handleWithingsConnect() {
    window.open(`${API_BASE}/api/withings/connect`, "_blank", "width=600,height=700");
    const interval = setInterval(async () => {
      try {
        const s = await api.getSettings();
        if (s.withings_connected) {
          setSettings(s);
          clearInterval(interval);
        }
      } catch {}
    }, 2000);
    setTimeout(() => clearInterval(interval), 120000);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="grid gap-4 max-w-2xl">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-48" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      {message && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid gap-6 max-w-2xl">
        {/* Profile & Goals */}
        <Card>
          <CardHeader>
            <CardTitle>Profile & Goals</CardTitle>
            <CardDescription>Your coach uses this to personalize advice and track your journey</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSave("Profile", {
                  user_name: userName || null,
                  age: age ? parseInt(age) : null,
                  gender: gender || null,
                  height_cm: heightCm ? parseFloat(heightCm) : null,
                  running_experience: runningExperience || null,
                  primary_goal: primaryGoal || null,
                  goal_race: goalRace || null,
                  goal_race_date: goalRaceDate || null,
                  injuries_notes: injuriesNotes || null,
                });
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    type="text"
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    placeholder="Your first name"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Age</label>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    placeholder="e.g. 35"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Gender</label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">Select...</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Height (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="100"
                    max="250"
                    value={heightCm}
                    onChange={(e) => setHeightCm(e.target.value)}
                    placeholder="e.g. 180"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Running Experience</label>
                  <select
                    value={runningExperience}
                    onChange={(e) => setRunningExperience(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">Select...</option>
                    <option value="beginner">Beginner (0-1 years)</option>
                    <option value="intermediate">Intermediate (1-3 years)</option>
                    <option value="advanced">Advanced (3+ years)</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Primary Goal</label>
                <input
                  type="text"
                  value={primaryGoal}
                  onChange={(e) => setPrimaryGoal(e.target.value)}
                  placeholder="e.g. Get healthier, run a marathon"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Goal Race</label>
                  <input
                    type="text"
                    value={goalRace}
                    onChange={(e) => setGoalRace(e.target.value)}
                    placeholder="e.g. Stockholm Marathon"
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Race Date</label>
                  <input
                    type="date"
                    value={goalRaceDate}
                    onChange={(e) => setGoalRaceDate(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Injuries or Limitations</label>
                <textarea
                  value={injuriesNotes}
                  onChange={(e) => setInjuriesNotes(e.target.value)}
                  placeholder="Any current injuries, past injuries, or physical limitations your coach should know about"
                  rows={2}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Garmin */}
        <Card>
          <CardHeader>
            <CardTitle>Garmin Connect</CardTitle>
            <CardDescription>
              Credentials for syncing activities and health data
              {settings?.last_garmin_sync && (
                <span className="block mt-1 text-xs">
                  Last sync: {formatDate(settings.last_garmin_sync)}
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const update: SettingsUpdate = {};
                if (garminEmail) update.garmin_email = garminEmail;
                if (garminPassword) update.garmin_password = garminPassword;
                handleSave("Garmin credentials", update);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  value={garminEmail}
                  onChange={(e) => setGarminEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Password
                  {settings?.garmin_password_set && (
                    <span className="ml-2 text-xs text-muted-foreground">(currently set)</span>
                  )}
                </label>
                <input
                  type="password"
                  value={garminPassword}
                  onChange={(e) => setGarminPassword(e.target.value)}
                  placeholder={settings?.garmin_password_set ? "Leave blank to keep current" : "Enter password"}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Withings */}
        <Card>
          <CardHeader>
            <CardTitle>Withings Scale</CardTitle>
            <CardDescription>
              OAuth2 credentials for body composition data
              {settings?.last_withings_sync && (
                <span className="block mt-1 text-xs">
                  Last sync: {formatDate(settings.last_withings_sync)}
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const update: SettingsUpdate = {};
                if (withingsClientId) update.withings_client_id = withingsClientId;
                if (withingsClientSecret) update.withings_client_secret = withingsClientSecret;
                handleSave("Withings credentials", update);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">Client ID</label>
                <input
                  type="text"
                  value={withingsClientId}
                  onChange={(e) => setWithingsClientId(e.target.value)}
                  placeholder="Your Withings Client ID"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Client Secret
                  {settings?.withings_client_secret_set && (
                    <span className="ml-2 text-xs text-muted-foreground">(currently set)</span>
                  )}
                </label>
                <input
                  type="password"
                  value={withingsClientSecret}
                  onChange={(e) => setWithingsClientSecret(e.target.value)}
                  placeholder={settings?.withings_client_secret_set ? "Leave blank to keep current" : "Enter client secret"}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            </form>

            <div className="border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Connection Status</p>
                  <p className="text-xs text-muted-foreground">
                    {settings?.withings_connected ? "Connected" : "Not connected"}
                  </p>
                </div>
                {settings?.withings_connected ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 border border-emerald-200">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Connected
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleWithingsConnect}
                    disabled={!settings?.withings_client_id}
                  >
                    Connect Withings
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
        {/* AI Coach */}
        <Card>
          <CardHeader>
            <CardTitle>AI Coach</CardTitle>
            <CardDescription>Anthropic API key for the Claude-powered coach</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (anthropicApiKey) {
                  handleSave("API key", { anthropic_api_key: anthropicApiKey });
                }
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">
                  API Key
                  {settings?.anthropic_api_key_set && (
                    <span className="ml-2 text-xs text-muted-foreground">(currently set)</span>
                  )}
                </label>
                <input
                  type="password"
                  value={anthropicApiKey}
                  onChange={(e) => setAnthropicApiKey(e.target.value)}
                  placeholder={settings?.anthropic_api_key_set ? "Leave blank to keep current" : "sk-ant-..."}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
