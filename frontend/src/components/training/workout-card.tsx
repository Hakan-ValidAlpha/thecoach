"use client";

import { PlannedWorkout } from "@/lib/api";

const WORKOUT_COLORS: Record<string, string> = {
  easy_run: "bg-emerald-100 border-emerald-300 text-emerald-800",
  long_run: "bg-blue-100 border-blue-300 text-blue-800",
  tempo_run: "bg-orange-100 border-orange-300 text-orange-800",
  interval_run: "bg-red-100 border-red-300 text-red-800",
  hill_repeats: "bg-amber-100 border-amber-300 text-amber-800",
  rest: "bg-gray-50 border-gray-200 text-gray-500",
  cross_training: "bg-purple-100 border-purple-300 text-purple-800",
  walk: "bg-teal-100 border-teal-300 text-teal-800",
};

const WORKOUT_LABELS: Record<string, string> = {
  easy_run: "Easy",
  long_run: "Long",
  tempo_run: "Tempo",
  interval_run: "Interval",
  hill_repeats: "Hills",
  rest: "Rest",
  cross_training: "Cross",
  walk: "Walk",
};

const STATUS_ICONS: Record<string, { icon: string; class: string }> = {
  completed: { icon: "\u2713", class: "text-emerald-600" },
  skipped: { icon: "\u2014", class: "text-gray-400" },
  missed: { icon: "\u2717", class: "text-red-500" },
};

export function WorkoutCard({
  workout,
  onClick,
  compact = false,
}: {
  workout: PlannedWorkout;
  onClick?: () => void;
  compact?: boolean;
}) {
  const colors = WORKOUT_COLORS[workout.workout_type] || "bg-gray-100 border-gray-300 text-gray-700";
  const label = WORKOUT_LABELS[workout.workout_type] || workout.workout_type;
  const statusInfo = STATUS_ICONS[workout.status];
  const isPast = workout.status === "planned" && new Date(workout.scheduled_date) < new Date(new Date().toDateString());
  const isDraggable = workout.status === "planned";

  return (
    <button
      draggable={isDraggable}
      onDragStart={(e) => {
        e.stopPropagation();
        e.dataTransfer.setData("workout-id", String(workout.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      className={`w-full text-left rounded-md border px-2 py-1.5 text-xs transition-all hover:shadow-sm ${colors} ${
        isPast ? "opacity-50" : ""
      } ${workout.status === "skipped" ? "line-through opacity-60" : ""} ${
        isDraggable ? "cursor-grab active:cursor-grabbing" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-medium truncate">
          {compact ? label : workout.title}
        </span>
        <span className="flex items-center gap-0.5 shrink-0">
          {workout.garmin_workout_id && (
            <span className="text-[9px] opacity-50" title="Synced with Garmin">G</span>
          )}
          {statusInfo && (
            <span className={`text-sm font-bold ${statusInfo.class}`}>{statusInfo.icon}</span>
          )}
        </span>
      </div>
      {!compact && workout.target_distance_meters && (
        <div className="text-[10px] opacity-75 mt-0.5">
          {(workout.target_distance_meters / 1000).toFixed(1)} km
        </div>
      )}
    </button>
  );
}
