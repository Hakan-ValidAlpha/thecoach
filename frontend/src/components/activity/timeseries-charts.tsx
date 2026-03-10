"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TimeseriesPoint } from "@/lib/api";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

interface TimeseriesChartsProps {
  data: TimeseriesPoint[];
}

function formatDistanceKm(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

function formatPace(minPerKm: number): string {
  const mins = Math.floor(minPerKm);
  const secs = Math.round((minPerKm - mins) * 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// Downsample data to ~300 points for chart performance
function downsample(data: TimeseriesPoint[], target = 300): TimeseriesPoint[] {
  if (data.length <= target) return data;
  const step = data.length / target;
  const result: TimeseriesPoint[] = [];
  for (let i = 0; i < target; i++) {
    result.push(data[Math.floor(i * step)]);
  }
  return result;
}

function computeStats(data: TimeseriesPoint[], dataKey: keyof TimeseriesPoint) {
  const values = data.map((d) => d[dataKey]).filter((v): v is number => typeof v === "number" && !isNaN(v));
  if (values.length === 0) return null;
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    avg: values.reduce((a, b) => a + b, 0) / values.length,
  };
}

function TSChart({
  title,
  data,
  dataKey,
  color,
  unit,
  yFormatter,
  type = "line",
}: {
  title: string;
  data: TimeseriesPoint[];
  dataKey: keyof TimeseriesPoint;
  color: string;
  unit: string;
  yFormatter?: (v: number) => string;
  type?: "line" | "area";
}) {
  const hasData = data.some((d) => d[dataKey] != null);
  if (!hasData) return null;

  const yFmt = yFormatter || ((v: number) => `${v}${unit}`);
  const stats = computeStats(data, dataKey);

  const fmtStat = (v: number) => yFormatter ? yFormatter(v) : `${Math.round(v)}${unit}`;

  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        {stats && (
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span>Low <span className="font-semibold text-foreground">{fmtStat(stats.min)}</span></span>
            <span>Avg <span className="font-semibold text-foreground">{fmtStat(stats.avg)}</span></span>
            <span>High <span className="font-semibold text-foreground">{fmtStat(stats.max)}</span></span>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          {type === "area" ? (
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis
                dataKey="distance"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => v != null ? formatDistanceKm(v) : ""}
              />
              <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={yFmt} />
              <Tooltip
                labelFormatter={(v) => v != null ? formatDistanceKm(v as number) : ""}
                formatter={(value: number) => [yFmt(value), title]}
                contentStyle={{ borderRadius: "8px", border: "1px solid #e5e5e5", fontSize: "12px" }}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                fill={color}
                fillOpacity={0.15}
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            </AreaChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis
                dataKey="distance"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => v != null ? formatDistanceKm(v) : ""}
              />
              <YAxis fontSize={11} tickLine={false} axisLine={false} tickFormatter={yFmt} />
              <Tooltip
                labelFormatter={(v) => v != null ? formatDistanceKm(v as number) : ""}
                formatter={(value: number) => [yFmt(value), title]}
                contentStyle={{ borderRadius: "8px", border: "1px solid #e5e5e5", fontSize: "12px" }}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function TimeseriesCharts({ data }: TimeseriesChartsProps) {
  if (data.length === 0) return null;

  const sampled = downsample(data);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <TSChart
        title="Heart Rate"
        data={sampled}
        dataKey="hr"
        color="#ef4444"
        unit=" bpm"
      />
      <TSChart
        title="Pace"
        data={sampled}
        dataKey="pace"
        color="#3b82f6"
        unit=""
        yFormatter={formatPace}
      />
      <TSChart
        title="Cadence"
        data={sampled}
        dataKey="cadence"
        color="#f59e0b"
        unit=" spm"
      />
      <TSChart
        title="Elevation"
        data={sampled}
        dataKey="elevation"
        color="#059669"
        unit=" m"
        type="area"
      />
    </div>
  );
}
