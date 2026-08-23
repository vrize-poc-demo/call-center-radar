const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type CallRegistration = {
  call_id: string;
  job_id: string;
  status: string;
};

export type ProcessingStatus = {
  job_id: string;
  status: "queued" | "transcribing" | "analyzing" | "completed" | "failed";
  audio_channels: number | null;
  failure_reason: string | null;
  transcript_turn_count: number;
};

export type ProcessingQueueItem = {
  job_id: string;
  call_id: string;
  customer_name: string;
  status: "queued" | "transcribing" | "analyzing" | "completed" | "failed";
  updated_at: string;
  failure_reason: string | null;
};

export type CallDetail = {
  call_id: string;
  agent_name: string;
  customer_name: string;
  created_at: string;
  processing_status: string;
  audio_channels: number | null;
  failure_reason: string | null;
  transcript_turn_count: number;
};

export type TranscriptTurn = {
  transcript_turn_id: string;
  speaker: "agent" | "customer" | "unknown";
  start_ms: number;
  end_ms: number;
  text: string;
};

export type EvidenceCandidate = {
  evidence_id: string;
  rule_id: string;
  label: string;
  transcript_turn_id: string;
  start_ms: number;
  end_ms: number;
  quote: string;
};

export type PriorityFactor = {
  factor_key: string;
  label: string;
  contribution: number;
  evidence_id: string;
  transcript_turn_id: string;
  start_ms: number;
  end_ms: number;
};

export type RadarPriority = {
  call_id: string;
  score: number;
  scoring_version: string;
  factors: PriorityFactor[];
};

export type EvidenceClaim = {
  claim: string;
  transcript_turn_id: string;
  quote: string;
  start_ms: number;
  end_ms: number;
};

export type MoodShift = {
  from_mood: "positive" | "neutral" | "negative" | "mixed";
  to_mood: "positive" | "neutral" | "negative" | "mixed";
  reason: string;
  transcript_turn_id: string;
  quote: string;
  start_ms: number;
  end_ms: number;
};

export type FalseResolutionSignal = {
  rule_id: string;
  resolution: EvidenceClaim;
  contradiction: EvidenceClaim;
};

export type RepeatedQuestionEvent = {
  rule_id: string;
  speaker: "agent" | "customer";
  original: EvidenceClaim;
  repeated: EvidenceClaim;
};

export type TreatmentSignal = {
  rule_id: string;
  label: string;
  evidence: EvidenceClaim;
};

export type SilenceWindow = {
  before: EvidenceClaim;
  after: EvidenceClaim;
  duration_ms: number;
};

export type ConversationBalance = {
  agent_talk_ms: number;
  customer_talk_ms: number;
  agent_share_pct: number;
  customer_share_pct: number;
};

export type CallAnalysis = {
  intent: string;
  mood: string;
  resolution: string;
  summary: string;
  manager_brief: string;
  recommended_action: string;
  claims: EvidenceClaim[];
  mood_shifts: MoodShift[];
  false_resolution: FalseResolutionSignal | null;
  repeated_questions: RepeatedQuestionEvent[];
  treatment_signals?: TreatmentSignal[];
  silence_windows: SilenceWindow[];
  conversation_balance: ConversationBalance;
  model_version: string;
};

export type TriageAnalysis = {
  intent: string;
  mood: "positive" | "neutral" | "negative" | "mixed";
  resolution: "resolved" | "unresolved" | "unclear";
  summary: string;
  manager_brief: string;
  recommended_action: string;
  model_version: string;
  analysis_version: number;
  analyzed_at: string;
  false_resolution: boolean;
};

export type TriageCall = {
  call_id: string;
  created_at: string;
  radar_priority: number | null;
  risk_level: "high" | "medium" | "low" | "unscored";
  analysis: TriageAnalysis;
};

export type AgentSummary = {
  agent_name: string;
  calls_handled: number;
  difficult_calls: number;
  estimated_satisfaction: number;
  average_handle_time_ms: number | null;
  calls_with_handle_time: number;
  resolved_count: number;
  resolved_rate: number;
  average_priority: number | null;
  treatment_signal_count: number;
  unresolved_count: number;
  false_resolution_count: number;
  high_risk_count: number;
  coaching_note: string;
  recent_call_ids: string[];
};

export type CustomerHistoryCall = {
  call_id: string;
  created_at: string;
  processing_status: string | null;
  analysis_status: string;
  mood: string | null;
  resolution: string | null;
  issue: { key: string; label: string; repeated: boolean } | null;
};
export async function getCustomerHistory(
  callId: string,
): Promise<CustomerHistoryCall[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/calls/${callId}/customer-history`,
  );
  if (!response.ok) throw new Error("Customer history could not be loaded.");
  return ((await response.json()) as { calls: CustomerHistoryCall[] }).calls;
}

export type IssueTrend =
  "emerging" | "declining" | "stable" | "not_enough_data";

export type IssueCategory = {
  key: string;
  label: string;
  call_count: number;
  current_window_count: number;
  previous_window_count: number;
  trend: IssueTrend;
  representative_call_id: string;
  related_call_ids: string[];
};

export async function registerCall(
  formData: FormData,
): Promise<CallRegistration> {
  const response = await fetch(`${apiBaseUrl}/api/calls`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(body?.detail ?? "The call could not be registered.");
  }

  return (await response.json()) as CallRegistration;
}

export async function processCall(jobId: string): Promise<ProcessingStatus> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${jobId}/process`, {
    method: "POST",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(body?.detail ?? "The call could not be processed.");
  }
  return (await response.json()) as ProcessingStatus;
}

export async function getProcessingQueue(): Promise<ProcessingQueueItem[]> {
  const response = await fetch(`${apiBaseUrl}/api/calls/processing-queue`);
  if (!response.ok) {
    throw new Error("Processing queue could not be loaded.");
  }
  return ((await response.json()) as { items: ProcessingQueueItem[] }).items;
}

export async function dismissProcessingQueueItem(jobId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${jobId}/queue-item`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("The call could not be removed from the queue.");
  }
}

export async function getCallDetail(callId: string): Promise<CallDetail> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${callId}`);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(body?.detail ?? "The call detail could not be loaded.");
  }
  return (await response.json()) as CallDetail;
}

export function getCallAudioUrl(callId: string): string {
  return `${apiBaseUrl}/api/calls/${callId}/audio`;
}

export async function getTranscript(callId: string): Promise<TranscriptTurn[]> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${callId}/transcript`);
  if (!response.ok) throw new Error("The transcript could not be loaded.");
  return ((await response.json()) as { turns: TranscriptTurn[] }).turns;
}

export async function getEvidence(
  callId: string,
): Promise<EvidenceCandidate[]> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${callId}/evidence`);
  if (!response.ok) throw new Error("Evidence could not be loaded.");
  return ((await response.json()) as { candidates: EvidenceCandidate[] })
    .candidates;
}

export async function calculatePriority(
  callId: string,
): Promise<RadarPriority> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${callId}/priority`, {
    method: "POST",
  });
  if (!response.ok)
    throw new Error("The Radar Priority score could not be calculated.");
  return (await response.json()) as RadarPriority;
}

export async function getAnalysis(callId: string): Promise<CallAnalysis> {
  const response = await fetch(`${apiBaseUrl}/api/calls/${callId}/analysis`);
  if (!response.ok) throw new Error("The analysis could not be loaded.");
  return ((await response.json()) as { analysis: CallAnalysis }).analysis;
}

export async function getDashboardTriage(): Promise<TriageCall[]> {
  const response = await fetch(`${apiBaseUrl}/api/dashboard/triage`);
  if (!response.ok) throw new Error("Today's dashboard could not be loaded.");
  return ((await response.json()) as { calls: TriageCall[] }).calls;
}

export async function getIssueRadar(): Promise<IssueCategory[]> {
  const response = await fetch(`${apiBaseUrl}/api/dashboard/issues`);
  if (!response.ok) throw new Error("Issue Radar could not be loaded.");
  return ((await response.json()) as { categories: IssueCategory[] })
    .categories;
}

export async function getAgentSummaries(): Promise<AgentSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/dashboard/agents`);
  if (!response.ok) throw new Error("Agent summaries could not be loaded.");
  return ((await response.json()) as { agents: AgentSummary[] }).agents;
}
