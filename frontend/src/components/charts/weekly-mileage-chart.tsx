"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WeeklyMileage } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

function formatWeekLabel(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function WeeklyMileageChart({ data }: { data: WeeklyMileage[] }) {
  const chartData = data.map((d) => ({
    week: formatWeekLabel(d.week_start),
    km: d.total_distance_km,
    runs: d.run_count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Weekly Mileage</CardTitle>
      </CardHeader>
      <CardContent>
        {chartData.length === 0 ? (
          <p className="text-muted-foreground">No mileage data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="week" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `${v} km`} />
              <Tooltip
                formatter={(value: number) => [`${value.toFixed(1)} km`, "Distance"]}
                contentStyle={{ borderRadius: "8px", border: "1px solid #e5e5e5" }}
              />
              <Bar dataKey="km" fill="#059669" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
