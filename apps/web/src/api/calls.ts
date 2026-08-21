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
