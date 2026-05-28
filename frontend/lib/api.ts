// =============================================================================
// DevBrain AI — API Client
// =============================================================================
// All communication with the FastAPI backend goes through this file.
// Uses fetch() with typed responses. Token is stored in localStorage.
// SSE streaming for code review uses the native EventSource API.
// =============================================================================

import type {
  User,
  SkillProfile,
  GithubAnalyzeRequest,
  GithubAnalyzeResponse,
  Roadmap,
  GenerateRoadmapRequest,
  Challenge,
  ChallengeAttempt,
  SubmitChallengeResponse,
  CodeReview,
  SubmitCodeReviewRequest,
  Resource,
  ResourceSearchResponse,
  ProgressDashboard,
  StreakInfo,
  InterviewSession,
  StartInterviewRequest,
  SendInterviewMessageResponse,
  AuthLoginResponse,
  HealthResponse,
  RoadmapDifficulty,
} from "./types";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "devbrain_token";

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  options: { skipAuth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!options.skipAuth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      detail = errJson?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function checkHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("GET", "/health", undefined, {
    skipAuth: true,
  });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/** Returns the GitHub OAuth URL. Redirect the user there. */
export async function getLoginUrl(): Promise<AuthLoginResponse> {
  return apiRequest<AuthLoginResponse>("GET", "/auth/login", undefined, {
    skipAuth: true,
  });
}

/** Fetch the current authenticated user. */
export async function getCurrentUser(): Promise<User> {
  return apiRequest<User>("GET", "/auth/me");
}

// ---------------------------------------------------------------------------
// GitHub / Skill Analysis
// ---------------------------------------------------------------------------

/** Kick off repo analysis. Pass `github_token` if user provided a PAT. */
export async function analyzeGithub(
  opts?: GithubAnalyzeRequest,
): Promise<GithubAnalyzeResponse> {
  return apiRequest<GithubAnalyzeResponse>("POST", "/github/analyze", opts ?? {});
}

/** Retrieve the latest computed skill profile. */
export async function getSkillProfile(): Promise<SkillProfile> {
  return apiRequest<SkillProfile>("GET", "/github/profile");
}

// ---------------------------------------------------------------------------
// Roadmap
// ---------------------------------------------------------------------------

/** Generate (or regenerate) a weekly learning roadmap for the given role. */
export async function generateRoadmap(
  target_role: string,
): Promise<Roadmap> {
  const body: GenerateRoadmapRequest = { target_role };
  return apiRequest<Roadmap>("POST", "/roadmap/generate", body);
}

/** Fetch the currently active roadmap. */
export async function getCurrentRoadmap(): Promise<Roadmap> {
  return apiRequest<Roadmap>("GET", "/roadmap/current");
}

// ---------------------------------------------------------------------------
// Challenges
// ---------------------------------------------------------------------------

/** Ask the backend to generate a new challenge targeting weak areas. */
export async function generateChallenge(): Promise<Challenge> {
  return apiRequest<Challenge>("POST", "/challenges/generate");
}

/** Submit a solution for a specific challenge. */
export async function submitChallenge(
  id: string,
  code: string,
): Promise<SubmitChallengeResponse> {
  return apiRequest<SubmitChallengeResponse>(
    "POST",
    `/challenges/${id}/submit`,
    { code },
  );
}

/** Get the user's challenge attempt history. */
export async function getChallengeHistory(): Promise<ChallengeAttempt[]> {
  return apiRequest<ChallengeAttempt[]>("GET", "/challenges/history");
}

// ---------------------------------------------------------------------------
// Code Review
// ---------------------------------------------------------------------------

/** Submit code for a full AI review (non-streaming). */
export async function submitCodeReview(
  code: string,
  language: string,
  context?: string,
): Promise<CodeReview> {
  const body: SubmitCodeReviewRequest = { code, language, context };
  return apiRequest<CodeReview>("POST", "/review/submit", body);
}

/**
 * Open an SSE stream for real-time code review tokens.
 * `onChunk` is called for every token that arrives.
 * Returns a cleanup function — call it to close the stream early.
 */
export function streamCodeReview(
  code: string,
  language: string,
  onChunk: (token: string) => void,
  onComplete?: () => void,
  onError?: (err: Event) => void,
): () => void {
  const token = getToken();
  const params = new URLSearchParams({ code, language });
  if (token) params.set("token", token);

  const url = `${BASE_URL}/review/stream?${params.toString()}`;
  const es = new EventSource(url);

  es.onmessage = (event: MessageEvent) => {
    if (event.data === "[DONE]") {
      es.close();
      onComplete?.();
      return;
    }
    onChunk(event.data as string);
  };

  es.onerror = (err: Event) => {
    es.close();
    onError?.(err);
  };

  // Return cleanup
  return () => es.close();
}

/** Get code review history for the current user. */
export async function getReviewHistory(): Promise<CodeReview[]> {
  return apiRequest<CodeReview[]>("GET", "/review/history");
}

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

/** Search for learning resources. */
export async function searchResources(
  topic: string,
  difficulty?: RoadmapDifficulty,
): Promise<ResourceSearchResponse> {
  const params = new URLSearchParams({ topic });
  if (difficulty) params.set("difficulty", difficulty);
  return apiRequest<ResourceSearchResponse>(
    "GET",
    `/resources/search?${params.toString()}`,
  );
}

// ---------------------------------------------------------------------------
// Interview
// ---------------------------------------------------------------------------

/** Start a new interview session. */
export async function startInterview(
  mode: "dsa" | "system_design",
): Promise<InterviewSession> {
  const body: StartInterviewRequest = { mode };
  return apiRequest<InterviewSession>("POST", "/interview/start", body);
}

/** Send a message in an existing interview session. */
export async function sendInterviewMessage(
  session_id: string,
  message: string,
): Promise<SendInterviewMessageResponse> {
  return apiRequest<SendInterviewMessageResponse>(
    "POST",
    `/interview/${session_id}/message`,
    { message },
  );
}

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

/** Get the full progress dashboard data. */
export async function getProgressDashboard(): Promise<ProgressDashboard> {
  return apiRequest<ProgressDashboard>("GET", "/progress/dashboard");
}

/** Get only streak information (lightweight). */
export async function getStreak(): Promise<StreakInfo> {
  return apiRequest<StreakInfo>("GET", "/progress/streak");
}