import type { Allocation } from "./dimensions";
import type { StreamEvent } from "./api";

export type Recommendation = {
  rank: number;
  district: string;
  verdict: string;
  rationale: string;
  tradeoff: string;
  tip: string;
  weighted_score: number | null;
  scores: Record<string, number | null>;
  spawn_score: number | null;
  insights: string[];
};

export type RunState = {
  status: "idle" | "running" | "done" | "error";
  startedAt?: number;
  knowledge?: { chars: number; cold_start: boolean };
  orchestrator?: {
    type: "ignore" | "adjust" | "spawn" | "combination";
    reasoning: string;
    original_allocation: Allocation;
    adjusted_allocation: Allocation;
    synthesiser_instruction: string;
    spawn: { intent: string; overpass_query: string | null; web_search_fallback: boolean } | null;
  };
  spawnStarted?: { intent: string; overpass_query: string | null; web_search_fallback: boolean };
  spawnComplete?: { districts_matched: number; districts_total: number; from_cache: boolean; timed_out?: boolean; failed: boolean };
  scorersDone: string[];
  scoring?: { top_10: { district: string; weighted_score: number; scores: Record<string, number | null> }[]; districts_scored: number };
  shortlist?: {
    top_5: { district: string; weighted_score: number }[];
    removed_by_spawn_filter: { district: string; weighted_score: number; spawn_score: number }[];
    spawn_filter_applied: boolean;
  };
  research: Record<string, { status: "running" | "done"; insights: string[]; failed?: boolean }>;
  recommendations?: Recommendation[];
  learning?: { count: number; query_count: number | null; distillation_due: boolean; learnings: { category: string; content: string }[] };
  done?: { search_id: string | null; duration_ms: number };
  error?: { code: string; message: string };
};

export const initialRun = (): RunState => ({ status: "idle", scorersDone: [], research: {} });

export function applyEvent(state: RunState, { event, data }: StreamEvent): RunState {
  switch (event) {
    case "started":
      return { ...initialRun(), status: "running", startedAt: Date.now() };
    case "knowledge_loaded":
      return { ...state, knowledge: data };
    case "orchestrator":
      return { ...state, orchestrator: data };
    case "spawn_started":
      return { ...state, spawnStarted: data };
    case "spawn_complete":
      return { ...state, spawnComplete: data };
    case "scorer_complete":
      return { ...state, scorersDone: [...state.scorersDone, data.dimension] };
    case "scoring_complete":
      return { ...state, scoring: data };
    case "shortlist":
      return { ...state, shortlist: data };
    case "research_started":
      return { ...state, research: { ...state.research, [data.district]: { status: "running", insights: [] } } };
    case "research_complete":
      return {
        ...state,
        research: { ...state.research, [data.district]: { status: "done", insights: data.insights ?? [], failed: data.failed } },
      };
    case "synthesis_complete":
      return { ...state, recommendations: data.recommendations };
    case "learning_saved":
      return { ...state, learning: data };
    case "done":
      return { ...state, status: "done", done: data };
    case "error":
      return { ...state, status: "error", error: data };
    default:
      return state;
  }
}

export const firstSentence = (text: string) => {
  const match = text.match(/^.*?[.!?](\s|$)/);
  return (match ? match[0] : text).trim();
};
