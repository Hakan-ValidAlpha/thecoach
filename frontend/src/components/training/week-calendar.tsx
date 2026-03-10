"use client";

import { useState } from "react";
import { PlannedWorkout, Activity } from "@/lib/api";
import { WorkoutCard } from "./workout-card";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getWeekDates(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return d;
  });
}

function dateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDistance(meters: number | null): string {
  if (!meters) return "";
  return `${(meters / 1000).toFixed(1)} km`;
}

export function WeekCalendar({
  weekStart,
  workouts,
  activities,
  onWorkoutClick,
  onDayClick,
  onWorkoutDrop,
  phaseName,
}: {
  weekStart: Date;
  workouts: PlannedWorkout[];
  activities: Activity[];
  onWorkoutClick: (w: PlannedWorkout) => void;
  onDayClick: (date: Date) => void;
  onWorkoutDrop?: (workoutId: number, newDate: string) => void;
  phaseName?: string;
}) {
  const days = getWeekDates(weekStart);
  const todayStr = dateKey(new Date());
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);

  // Group by date
  const workoutsByDate = new Map<string, PlannedWorkout[]>();
  for (const w of workouts) {
    const key = w.scheduled_date;
    workoutsByDate.set(key, [...(workoutsByDate.get(key) || []), w]);
  }

  const activitiesByDate = new Map<string, Activity[]>();
  for (const a of activities) {
    const key = a.started_at.split("T")[0];
    activitiesByDate.set(key, [...(activitiesByDate.get(key) || []), a]);
  }

  return (
    <div>
      {phaseName && (
        <div className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {phaseName}
        </div>
      )}
      <div className="grid grid-cols-7 gap-px bg-border rounded-lg overflow-hidden border border-border">
        {/* Header */}
        {days.map((d, i) => {
          const key = dateKey(d);
          const isToday = key === todayStr;
          return (
            <div
              key={`header-${i}`}
              className={`px-2 py-1.5 text-center text-xs font-medium ${
                isToday ? "bg-primary/10 text-primary" : "bg-muted/50 text-muted-foreground"
              }`}
            >
              <div>{DAYS[i]}</div>
              <div className={`text-sm ${isToday ? "font-bold" : ""}`}>{d.getDate()}</div>
            </div>
          );
        })}

        {/* Day cells */}
        {days.map((d, i) => {
          const key = dateKey(d);
          const isToday = key === todayStr;
          const dayWorkouts = workoutsByDate.get(key) || [];
          const dayActivities = activitiesByDate.get(key) || [];
          // Filter to activities not linked to a workout
          const linkedIds = new Set(dayWorkouts.map((w) => w.completed_activity_id).filter(Boolean));
          const unmatchedActivities = dayActivities.filter((a) => !linkedIds.has(a.id));

          return (
            <div
              key={`cell-${i}`}
              onClick={() => onDayClick(d)}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                setDragOverDate(key);
              }}
              onDragLeave={() => setDragOverDate(null)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOverDate(null);
                const workoutId = e.dataTransfer.getData("workout-id");
                if (workoutId && onWorkoutDrop) {
                  onWorkoutDrop(Number(workoutId), key);
                }
              }}
              className={`min-h-[100px] p-1.5 bg-background cursor-pointer hover:bg-muted/30 transition-colors ${
                isToday ? "ring-1 ring-inset ring-primary/30" : ""
              } ${dragOverDate === key ? "bg-primary/10 ring-2 ring-inset ring-primary/40" : ""}`}
            >
              <div className="space-y-1">
                {dayWorkouts.map((w) => (
                  <WorkoutCard
                    key={w.id}
                    workout={w}
                    onClick={() => {
                      onWorkoutClick(w);
                    }}
                  />
                ))}
                {unmatchedActivities.map((a) => (
                  <div
                    key={a.id}
                    className="rounded-md border border-dashed border-muted-foreground/30 px-2 py-1 text-[10px] text-muted-foreground"
                  >
                    {a.name || a.activity_type}
                    {a.distance_meters ? ` - ${formatDistance(a.distance_meters)}` : ""}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
