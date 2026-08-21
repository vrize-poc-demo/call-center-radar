const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type CallRegistration = {
  call_id: string;
  job_id: string;
  status: string;
};

export type ProcessingStatus = {
  job_id: string;
  status: "completed" | "failed";
  audio_channels: number | null;
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
  speaker: "agent" | "customer";
  start_ms: number;
  end_ms: number;
  text: string;
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
