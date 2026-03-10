"use client";

import { useEffect, useState } from "react";
import { api, DailyHealth, BodyComposition } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatSleepDuration } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from "recharts";

type Range = 7 | 14 | 30 | 90;
type Tab = "recovery" | "sleep" | "body";

const TABS: { value: Tab; label: string }[] = [
  { value: "recovery", label: "Heart & Recovery" },
  { value: "sleep", label: "Sleep" },
  { value: "body", label: "Body & Activity" },
];

const METRIC_INFO: Record<string, string> = {
  "Resting Heart Rate": "Your heart rate at complete rest, measured in beats per minute. A lower resting HR generally indicates better cardiovascular fitness. Typical range: 40-100 bpm for adults.",
  "HRV": "Heart Rate Variability measures the variation in time between heartbeats. Higher HRV indicates better recovery and fitness. Solid line is last night's reading, dashed line is the 7-day average.",
  "Sleep Score": "Garmin's composite sleep quality score (0-100) based on duration, depth, and restfulness. Above 80 is good, above 90 is excellent.",
  "Sleep Duration": "Total time asleep in hours. Adults generally need 7-9 hours for optimal recovery and performance.",
  "Sleep Stages": "Breakdown of sleep into stages. Deep sleep is critical for physical recovery, REM for mental recovery, and light sleep makes up the bulk. Less awake time is better.",
  "Stress": "Garmin's stress level derived from HRV analysis (0-100). Lower is more relaxed. Orange shows average daily stress, red shows peak stress.",
  "Body Battery": "Garmin's energy monitoring metric (0-100). Green shows your daily peak energy, gray shows the lowest point. Higher peaks and higher lows mean better recovery.",
  "Steps": "Total daily step count. 7,000-10,000 steps/day is a common goal for general health.",
  "Training Readiness": "Garmin's assessment of how prepared your body is for training (0-100), based on sleep, recovery, training load, and HRV. Above 50 means you're ready to train.",
  "VO2 Max": "Maximum rate of oxygen consumption during exercise (ml/kg/min). A key indicator of aerobic fitness. Higher is better. Improves with consistent training.",
  "Intensity Minutes": "Minutes spent in moderate to vigorous physical activity. WHO recommends 150+ moderate or 75+ vigorous minutes per week.",
  "Weight": "Body weight in kilograms. Track trends over weeks rather than daily fluctuations, which are normal due to hydration and food intake.",
  "Body Fat %": "Percentage of total body mass that is fat tissue. Healthy range varies by age and sex. For men typically 10-20%, for women 18-28%.",
  "Muscle Mass": "Estimated skeletal muscle mass in kilograms. Important to maintain or increase during training for injury prevention and performance.",
  "BMI": "Body Mass Index calculated from weight and height (kg/m²). Normal range: 18.5-24.9. Note: BMI doesn't distinguish between muscle and fat mass, so it's less useful for athletes.",
};

function InfoTooltip({ text }: { text: string }) {
  return (
    <div className="relative group">
      <svg className="w-4 h-4 text-muted-foreground cursor-help" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 rounded-lg border border-border bg-card p-3 text-xs text-foreground shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-50">
        {text}
        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-border" />
      </div>
    </div>
  );
}

function shortDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function computeAvg(data: { [key: string]: unknown }[], dataKey: string): number | null {
  const values = data.map((d) => d[dataKey]).filter((v): v is number => typeof v === "number");
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function formatAvg(avg: number | null, unit?: string): string {
  if (avg == null) return "";
  const formatted = Number.isInteger(avg) ? avg.toString() : avg.toFixed(1);
  return `avg ${formatted}${unit || ""}`;
}

function computeTrend(data: { [key: string]: unknown }[], dataKey: string): "up" | "down" | "unchanged" | null {
  const values = data
    .map((d, i) => ({ i, v: d[dataKey] }))
    .filter((d): d is { i: number; v: number } => typeof d.v === "number");
  if (values.length < 2) return null;
  const third = Math.max(1, Math.floor(values.length / 3));
  const oldSlice = values.slice(0, third);
  const newSlice = values.slice(-third);
  const oldAvg = oldSlice.reduce((s, d) => s + d.v, 0) / oldSlice.length;
  const newAvg = newSlice.reduce((s, d) => s + d.v, 0) / newSlice.length;
  const threshold = oldAvg === 0 ? 0.01 : Math.abs(oldAvg) * 0.02;
  if (newAvg > oldAvg + threshold) return "up";
  if (newAvg < oldAvg - threshold) return "down";
  return "unchanged";
}

const INVERTED_METRICS = new Set(["Resting Heart Rate", "Stress", "Weight", "Body Fat %", "BMI"]);

function TrendArrow({ direction, inverted }: { direction: "up" | "down" | "unchanged" | null; inverted?: boolean }) {
  if (!direction) return null;
  const arrows = { up: "\u2191", down: "\u2193", unchanged: "\u2192" };
  const colors = {
    up: inverted ? "text-red-500" : "text-emerald-500",
    down: inverted ? "text-emerald-500" : "text-red-500",
    unchanged: "text-muted-foreground",
  };
  return <span className={`text-sm font-semibold ${colors[direction]}`}>{arrows[direction]}</span>;
}

function MetricChart({
  title,
  data,
  dataKey,
  color = "#059669",
  unit,
  type = "line",
  secondaryKey,
  secondaryColor,
}: {
  title: string;
  data: { date: string; [key: string]: unknown }[];
  dataKey: string;
  color?: string;
  unit?: string;
  type?: "line" | "bar" | "area";
  secondaryKey?: string;
  secondaryColor?: string;
}) {
  const hasData = data.some((d) => d[dataKey] != null);
  if (!hasData) return null;

  const avg = computeAvg(data, dataKey);
  const trend = computeTrend(data, dataKey);
  const ChartComponent = type === "bar" ? BarChart : type === "area" ? AreaChart : LineChart;

  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <div className="flex items-center gap-1.5">
          <CardTitle className="text-base">{title}</CardTitle>
          {METRIC_INFO[title] && <InfoTooltip text={METRIC_INFO[title]} />}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-muted-foreground">{formatAvg(avg, unit)}</span>
          <TrendArrow direction={trend} inverted={INVERTED_METRICS.has(title)} />
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <ChartComponent data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
            {avg != null && <ReferenceLine y={avg} stroke="#ef4444" strokeWidth={1} strokeDasharray="6 3" />}
            <XAxis dataKey="date" fontSize={11} tickLine={false} axisLine={false} tickFormatter={shortDate} />
            <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => unit ? `${v}${unit}` : String(v)} />
            <Tooltip
              labelFormatter={shortDate}
              formatter={(value: number, name: string) => [
                unit ? `${value}${unit}` : value,
                name,
              ]}
              contentStyle={{ borderRadius: "8px", border: "1px solid #e5e5e5", fontSize: "13px" }}
            />
            {type === "line" && (
              <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} connectNulls />
            )}
            {type === "line" && secondaryKey && (
              <Line type="monotone" dataKey={secondaryKey} stroke={secondaryColor || "#9ca3af"} strokeWidth={2} dot={false} connectNulls strokeDasharray="4 4" />
            )}
            {type === "bar" && (
              <Bar dataKey={dataKey} fill={color} radius={[3, 3, 0, 0]} />
            )}
            {type === "area" && (
              <Area type="monotone" dataKey={dataKey} stroke={color} fill={color} fillOpacity={0.15} strokeWidth={2} connectNulls />
            )}
            {type === "area" && secondaryKey && (
              <Area type="monotone" dataKey={secondaryKey} stroke={secondaryColor || "#9ca3af"} fill={secondaryColor || "#9ca3af"} fillOpacity={0.08} strokeWidth={2} connectNulls />
            )}
          </ChartComponent>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function SleepBreakdownChart({ data }: { data: { date: string; deep: number; light: number; rem: number; awake: number }[] }) {
  const hasData = data.some((d) => d.deep > 0 || d.light > 0 || d.rem > 0);
  if (!hasData) return null;

  const totalSleep = data.filter((d) => d.deep + d.light + d.rem > 0);
  const avgTotal = totalSleep.length > 0
    ? totalSleep.reduce((sum, d) => sum + d.deep + d.light + d.rem + d.awake, 0) / totalSleep.length
    : null;

  const totalData = data.map((d) => ({ ...d, total: d.deep + d.light + d.rem + d.awake }));
  const trend = computeTrend(totalData, "total");

  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <div className="flex items-center gap-1.5">
          <CardTitle className="text-base">Sleep Stages</CardTitle>
          {METRIC_INFO["Sleep Stages"] && <InfoTooltip text={METRIC_INFO["Sleep Stages"]} />}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-muted-foreground">
            {avgTotal != null ? `avg ${formatSleepDuration(avgTotal)}` : ""}
          </span>
          <TrendArrow direction={trend} />
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
            <XAxis dataKey="date" fontSize={11} tickLine={false} axisLine={false} tickFormatter={shortDate} />
            <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v / 3600).toFixed(1)}h`} />
            <Tooltip
              labelFormatter={shortDate}
              formatter={(value: number, name: string) => [formatSleepDuration(value), name]}
              contentStyle={{ borderRadius: "8px", border: "1px solid #e5e5e5", fontSize: "13px" }}
            />
            <Bar dataKey="deep" stackId="sleep" fill="#1e40af" radius={0} name="Deep" />
            <Bar dataKey="light" stackId="sleep" fill="#60a5fa" radius={0} name="Light" />
            <Bar dataKey="rem" stackId="sleep" fill="#a78bfa" radius={0} name="REM" />
            <Bar dataKey="awake" stackId="sleep" fill="#fbbf24" radius={[3, 3, 0, 0]} name="Awake" />
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-2 flex gap-4 justify-center text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-[#1e40af]" /> Deep</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-[#60a5fa]" /> Light</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-[#a78bfa]" /> REM</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-[#fbbf24]" /> Awake</span>
        </div>
      </CardContent>
    </Card>
  );
}

function BodyCompChart({ data }: { data: BodyComposition[] }) {
  if (data.length === 0) return null;

  const chartData = [...data]
    .reverse()
    .map((d) => ({
      date: d.measured_at,
      weight: d.weight_kg,
      fat: d.fat_percent,
      muscle: d.muscle_mass_kg,
      bmi: d.bmi,
    }));

  return (
    <>
      <MetricChart title="Weight" data={chartData} dataKey="weight" color="#059669" unit=" kg" type="area" />
      <MetricChart title="Body Fat %" data={chartData} dataKey="fat" color="#ef4444" unit="%" type="line" />
      <MetricChart title="Muscle Mass" data={chartData} dataKey="muscle" color="#3b82f6" unit=" kg" type="area" />
      <MetricChart title="BMI" data={chartData} dataKey="bmi" color="#8b5cf6" type="line" />
    </>
  );
}

export default function StatsPage() {
  const [health, setHealth] = useState<DailyHealth[]>([]);
  const [bodyComp, setBodyComp] = useState<BodyComposition[]>([]);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<Range>(30);
  const [tab, setTab] = useState<Tab>("recovery");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getHealthDaily({ limit: range }),
      api.getBodyComposition(range),
    ])
      .then(([h, b]) => {
        setHealth(h);
        setBodyComp(b);
      })
      .finally(() => setLoading(false));
  }, [range]);

  const chartData = [...health].reverse().map((h) => ({
    date: h.date,
    resting_hr: h.resting_heart_rate,
    hrv_weekly: h.hrv_weekly_avg,
    hrv_night: h.hrv_last_night,
    stress_avg: h.stress_avg,
    stress_max: h.stress_max,
    battery_high: h.body_battery_high,
    battery_low: h.body_battery_low,
    sleep_score: h.sleep_score,
    sleep_hours: h.sleep_duration_seconds ? +(h.sleep_duration_seconds / 3600).toFixed(1) : null,
    steps: h.steps,
    training_readiness: h.training_readiness,
    vo2max: h.vo2max,
    intensity: h.intensity_minutes,
  }));

  const sleepData = [...health].reverse().map((h) => ({
    date: h.date,
    deep: h.deep_sleep_seconds || 0,
    light: h.light_sleep_seconds || 0,
    rem: h.rem_sleep_seconds || 0,
    awake: h.awake_seconds || 0,
  }));

  const ranges: Range[] = [7, 14, 30, 90];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Stats</h1>
        <div className="flex gap-1">
          {ranges.map((r) => (
            <Button
              key={r}
              variant={range === r ? "default" : "outline"}
              size="sm"
              onClick={() => setRange(r)}
            >
              {r}d
            </Button>
          ))}
        </div>
      </div>

      <div className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.value
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-72" />)}
        </div>
      ) : health.length === 0 ? (
        <p className="text-muted-foreground">No data yet. Sync your Garmin data to get started.</p>
      ) : (
        <>
          {tab === "recovery" && (
            <div className="grid gap-4 md:grid-cols-2">
              <MetricChart title="Resting Heart Rate" data={chartData} dataKey="resting_hr" color="#ef4444" unit=" bpm" type="line" />
              <MetricChart title="HRV" data={chartData} dataKey="hrv_night" color="#8b5cf6" unit=" ms" type="line" secondaryKey="hrv_weekly" secondaryColor="#c4b5fd" />
              <MetricChart title="Body Battery" data={chartData} dataKey="battery_high" color="#059669" type="area" secondaryKey="battery_low" secondaryColor="#9ca3af" />
              <MetricChart title="Training Readiness" data={chartData} dataKey="training_readiness" color="#059669" type="line" />
              <MetricChart title="Stress" data={chartData} dataKey="stress_avg" color="#f59e0b" type="area" secondaryKey="stress_max" secondaryColor="#dc2626" />
            </div>
          )}

          {tab === "sleep" && (
            <div className="grid gap-4 md:grid-cols-2">
              <MetricChart title="Sleep Score" data={chartData} dataKey="sleep_score" color="#3b82f6" type="bar" />
              <MetricChart title="Sleep Duration" data={chartData} dataKey="sleep_hours" color="#6366f1" unit="h" type="area" />
              <SleepBreakdownChart data={sleepData} />
            </div>
          )}

          {tab === "body" && (
            <div className="grid gap-4 md:grid-cols-2">
              <MetricChart title="Steps" data={chartData} dataKey="steps" color="#06b6d4" type="bar" />
              <MetricChart title="VO2 Max" data={chartData} dataKey="vo2max" color="#7c3aed" type="line" />
              <MetricChart title="Intensity Minutes" data={chartData} dataKey="intensity" color="#f97316" type="bar" unit=" min" />
              <BodyCompChart data={bodyComp} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
