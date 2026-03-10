const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

// Types
export const TRAINING_TYPES = [
  { value: "easy_run", label: "Easy Run" },
  { value: "long_run", label: "Long Run" },
  { value: "tempo_run", label: "Tempo Run" },
  { value: "interval_run", label: "Interval Run" },
  { value: "hill_repeats", label: "Hill Repeats" },
] as const;

export type TrainingType = typeof TRAINING_TYPES[number]["value"];

export interface Activity {
  id: number;
  garmin_activity_id: number;
  activity_type: string | null;
  training_type: string | null;
  name: string | null;
  started_at: string;
  duration_seconds: number | null;
  distance_meters: number | null;
  avg_pace_min_per_km: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  calories: number | null;
  avg_cadence: number | null;
  elevation_gain: number | null;
  training_effect_aerobic: number | null;
  training_effect_anaerobic: number | null;
  vo2max_estimate: number | null;
}

export interface ActivitySplit {
  split_number: number;
  distance_meters: number | null;
  duration_seconds: number | null;
  avg_pace_min_per_km: number | null;
  avg_heart_rate: number | null;
}

export interface ActivityDetail extends Activity {
  splits: ActivitySplit[];
}

export interface DailyHealth {
  date: string;
  resting_heart_rate: number | null;
  hrv_weekly_avg: number | null;
  hrv_last_night: number | null;
  stress_avg: number | null;
  stress_max: number | null;
  body_battery_high: number | null;
  body_battery_low: number | null;
  body_battery_current: number | null;
  body_battery_charged: number | null;
  body_battery_drained: number | null;
  sleep_score: number | null;
  sleep_duration_seconds: number | null;
  deep_sleep_seconds: number | null;
  light_sleep_seconds: number | null;
  rem_sleep_seconds: number | null;
  awake_seconds: number | null;
  steps: number | null;
  training_readiness: number | null;
  vo2max: number | null;
  intensity_minutes: number | null;
}

export interface WeeklyMileage {
  week_start: string;
  total_distance_km: number;
  run_count: number;
}

export interface TrendIndicator {
  direction: "up" | "down" | "unchanged";
  current: number | null;
  previous: number | null;
}

export interface DashboardTrends {
  weekly_distance: TrendIndicator | null;
  resting_hr: TrendIndicator | null;
  sleep_score: TrendIndicator | null;
  body_battery: TrendIndicator | null;
}

export interface DashboardData {
  recent_activities: Activity[];
  weekly_mileage: WeeklyMileage[];
  health_snapshot: DailyHealth | null;
  current_week_distance_km: number;
  current_week_run_count: number;
  trends: DashboardTrends;
}

export interface SyncStatus {
  last_garmin_sync: string | null;
  last_withings_sync: string | null;
  is_syncing: boolean;
}

export interface SyncResult {
  activities_synced: number;
  health_days_synced: number;
  errors: string[];
}

export interface BodyComposition {
  id: number;
  measured_at: string;
  source: string;
  weight_kg: number | null;
  fat_mass_kg: number | null;
  fat_percent: number | null;
  muscle_mass_kg: number | null;
  bone_mass_kg: number | null;
  bmi: number | null;
}

export interface ActivitySummary {
  period: string;
  total_distance_km: number;
  total_duration_minutes: number;
  activity_count: number;
  avg_pace_min_per_km: number | null;
  avg_heart_rate: number | null;
}

export interface TimeseriesPoint {
  elapsed?: number;
  distance?: number;
  hr?: number;
  cadence?: number;
  pace?: number;
  elevation?: number;
}

export interface TimeseriesData {
  timeseries: TimeseriesPoint[];
  polyline: [number, number][];
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  last_message_at: string;
  message_count: number;
}

export interface TrainingPhase {
  id: number;
  plan_id: number;
  name: string;
  phase_type: string;
  start_date: string;
  end_date: string;
  order_index: number;
  description: string | null;
}

export interface TrainingPlan {
  id: number;
  name: string;
  goal: string | null;
  goal_date: string | null;
  start_date: string;
  end_date: string;
  status: string;
  notes: string | null;
  created_at: string;
  phases: TrainingPhase[];
  workout_count: number;
  completed_count: number;
}

export interface PlannedWorkout {
  id: number;
  plan_id: number;
  phase_id: number | null;
  scheduled_date: string;
  workout_type: string;
  title: string;
  description: string | null;
  target_distance_meters: number | null;
  target_duration_seconds: number | null;
  target_pace_min_per_km: number | null;
  status: string;
  completed_activity_id: number | null;
  completed_at: string | null;
  garmin_workout_id: number | null;
  garmin_schedule_id: number | null;
}

export interface PlanCompliance {
  total: number;
  completed: number;
  skipped: number;
  missed: number;
  planned: number;
  compliance_pct: number;
  by_phase: {
    phase_id: number;
    phase_name: string;
    total: number;
    completed: number;
    skipped: number;
    missed: number;
    compliance_pct: number;
  }[];
}

export interface AppSettings {
  height_cm: number | null;
  garmin_email: string | null;
  garmin_password_set: boolean;
  withings_client_id: string | null;
  withings_client_secret_set: boolean;
  withings_connected: boolean;
  last_garmin_sync: string | null;
  last_withings_sync: string | null;
}

export interface SettingsUpdate {
  height_cm?: number | null;
  garmin_email?: string | null;
  garmin_password?: string | null;
  withings_client_id?: string | null;
  withings_client_secret?: string | null;
}

// API functions
export const api = {
  getDashboard: () => fetchApi<DashboardData>("/dashboard"),

  getActivities: (params?: {
    activity_type?: string;
    training_type?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) query.set(k, String(v));
      });
    }
    const qs = query.toString();
    return fetchApi<Activity[]>(`/activities${qs ? `?${qs}` : ""}`);
  },

  getActivity: (id: number) => fetchApi<ActivityDetail>(`/activities/${id}`),

  updateTrainingType: (id: number, training_type: string | null) =>
    fetchApi<Activity>(`/activities/${id}/training-type`, {
      method: "PATCH",
      body: JSON.stringify({ training_type }),
    }),

  getActivityTimeseries: (id: number) => fetchApi<TimeseriesData>(`/activities/${id}/timeseries`),

  getActivitySummary: (period = "weekly", weeks = 12) =>
    fetchApi<ActivitySummary[]>(`/activities/summary?period=${period}&weeks=${weeks}`),

  getHealthDaily: (params?: { start_date?: string; end_date?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) query.set(k, String(v));
      });
    }
    const qs = query.toString();
    return fetchApi<DailyHealth[]>(`/health/daily${qs ? `?${qs}` : ""}`);
  },

  getBodyComposition: (limit = 30) =>
    fetchApi<BodyComposition[]>(`/body-composition?limit=${limit}`),

  syncGarmin: () => fetchApi<SyncResult>("/sync/garmin", { method: "POST" }),

  getSyncStatus: () => fetchApi<SyncStatus>("/sync/status"),

  getWithingsStatus: () => fetchApi<{ connected: boolean; last_sync: string | null }>("/withings/status"),

  syncWithings: () => fetchApi<{ status: string }>("/withings/sync", { method: "POST" }),

  getConversations: () => fetchApi<ConversationSummary[]>("/coach/conversations"),

  getConversation: (id: string) => fetchApi<ChatMessage[]>(`/coach/conversations/${id}`),

  deleteConversation: (id: string) =>
    fetchApi<{ status: string }>(`/coach/conversations/${id}`, { method: "DELETE" }),

  streamChat: (conversationId: string, message: string) =>
    fetch(`${API_BASE}/api/coach/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    }),

  // Training
  getTrainingPlans: (status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return fetchApi<TrainingPlan[]>(`/training/plans${qs}`);
  },

  createTrainingPlan: (data: {
    name: string;
    goal?: string;
    goal_date?: string;
    start_date: string;
    end_date: string;
    notes?: string;
    phases?: { name: string; phase_type: string; start_date: string; end_date: string; order_index?: number; description?: string }[];
  }) => fetchApi<TrainingPlan>("/training/plans", { method: "POST", body: JSON.stringify(data) }),

  getTrainingPlan: (id: number) => fetchApi<TrainingPlan>(`/training/plans/${id}`),

  updateTrainingPlan: (id: number, data: Record<string, unknown>) =>
    fetchApi<TrainingPlan>(`/training/plans/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteTrainingPlan: (id: number) =>
    fetchApi<{ status: string }>(`/training/plans/${id}`, { method: "DELETE" }),

  getWorkouts: (params?: { plan_id?: number; start_date?: string; end_date?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) query.set(k, String(v));
      });
    }
    const qs = query.toString();
    return fetchApi<PlannedWorkout[]>(`/training/workouts${qs ? `?${qs}` : ""}`);
  },

  createWorkout: (data: {
    plan_id: number;
    phase_id?: number;
    scheduled_date: string;
    workout_type: string;
    title: string;
    description?: string;
    target_distance_meters?: number;
    target_duration_seconds?: number;
    target_pace_min_per_km?: number;
  }) => fetchApi<PlannedWorkout>("/training/workouts", { method: "POST", body: JSON.stringify(data) }),

  updateWorkout: (id: number, data: Record<string, unknown>) =>
    fetchApi<PlannedWorkout>(`/training/workouts/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteWorkout: (id: number) =>
    fetchApi<{ status: string }>(`/training/workouts/${id}`, { method: "DELETE" }),

  completeWorkout: (id: number, activityId?: number) =>
    fetchApi<PlannedWorkout>(`/training/workouts/${id}/complete${activityId ? `?activity_id=${activityId}` : ""}`, { method: "PATCH" }),

  skipWorkout: (id: number) =>
    fetchApi<PlannedWorkout>(`/training/workouts/${id}/skip`, { method: "PATCH" }),

  autoMatchWorkouts: (planId: number) =>
    fetchApi<{ matched: number }>(`/training/plans/${planId}/auto-match`, { method: "POST" }),

  getPlanCompliance: (planId: number) =>
    fetchApi<PlanCompliance>(`/training/plans/${planId}/compliance`),

  syncGarminCalendar: () =>
    fetchApi<{ status: string }>("/training/sync-garmin", { method: "POST" }),

  getSettings: () => fetchApi<AppSettings>("/settings"),

  updateSettings: (update: SettingsUpdate) =>
    fetchApi<AppSettings>("/settings", {
      method: "PUT",
      body: JSON.stringify(update),
    }),
};
