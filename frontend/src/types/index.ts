/* ManualWorx TypeScript interfaces and enums. */

// --- Enums ---

export enum UserRole {
  OWNER = "owner",
  MANAGER = "manager",
  TECHNICIAN = "technician",
}

export enum PlanTier {
  FREE = "free",
  STARTER = "starter",
  PRO = "pro",
  SHOP = "shop",
}

export enum SkillLevel {
  GREEN = "green",
  APPRENTICE = "apprentice",
  JOURNEYMAN = "journeyman",
}

export enum PageClassification {
  TEXT = "text",
  HYDRAULIC_SCHEMATIC = "hydraulic_schematic",
  ELECTRICAL_DIAGRAM = "electrical_diagram",
  PARTS_EXPLODED_VIEW = "parts_exploded_view",
  TORQUE_SPEC_TABLE = "torque_spec_table",
  DIAGNOSTIC_FLOWCHART = "diagnostic_flowchart",
  WIRING_HARNESS = "wiring_harness",
  GENERAL_ILLUSTRATION = "general_illustration",
}

export enum ManualStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  READY = "ready",
  FAILED = "failed",
}

export enum QueryMode {
  QA = "qa",
  TROUBLESHOOT = "troubleshoot",
  DIAGRAM = "diagram",
  PROCEDURE = "procedure",
}

export enum ConfidenceLevel {
  HIGH = "high",
  MODERATE = "moderate",
  LOW = "low",
  INFERENCE = "inference",
}

export enum DocumentType {
  TROUBLESHOOTING_GUIDE = "troubleshooting_guide",
  SERVICE_PROCEDURE = "service_procedure",
  PARTS_REFERENCE = "parts_reference",
  QUICK_REFERENCE = "quick_reference",
  TRAINING_LESSON = "training_lesson",
  QUIZ_ASSESSMENT = "quiz_assessment",
  PROGRESS_REPORT = "progress_report",
  SYSTEM_ANALYSIS = "system_analysis",
  GAP_REPORT = "gap_report",
}

// --- Core Models ---

export interface Tenant {
  id: string;
  type: string;
  name: string;
  slug: string;
  subscription_plan: PlanTier;
  subscription_status: string;
  manual_limit: number;
  user_limit: number;
  query_limit_monthly: number;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  name: string;
  role: UserRole;
  skill_level: SkillLevel;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  is_superadmin?: boolean;
}

export interface Manual {
  id: string;
  tenant_id: string;
  title: string;
  make: string | null;
  model: string | null;
  manual_type: string;
  total_pages: number | null;
  upload_status: ManualStatus;
  visibility: string;
  created_at: string;
  updated_at: string;
}

export interface Page {
  id: string;
  manual_id: string;
  page_number: number;
  classification: PageClassification;
  extracted_text: string | null;
  image_url: string | null;
  has_table: boolean;
  has_diagram: boolean;
}

export interface Query {
  id: string;
  tenant_id: string;
  query_text: string;
  query_mode: QueryMode;
  response_text: string;
  confidence_score: number | null;
  sources: QuerySource[];
  created_at: string;
}

export interface QuerySource {
  page_id: string;
  page_number: number;
  classification: PageClassification;
  text_preview: string;
  relevance_score: number;
}

export interface Document {
  id: string;
  tenant_id: string;
  doc_type: DocumentType;
  format: string;
  file_url: string | null;
  created_at: string;
}

// --- Billing ---

export interface UsageInfo {
  queries_used: number;
  queries_limit: number;
  manuals_processed: number;
  manual_limit: number;
  docs_generated: number;
  current_period: string;
  total_ai_cost_cents: number;
}

// --- Confidence ---

export interface ConfidenceScore {
  score: number;
  level: ConfidenceLevel;
  sources: string[];
}

export interface Claim {
  claim_text: string;
  claim_type: "spec" | "description" | "procedure_step" | "warning";
  safety_critical: boolean;
  source_pages: number[];
  confidence: number;
  corroborated: boolean;
  contradictions: string[];
}

export interface RefinementSuggestion {
  query: string;
  reason: string;
}

// --- Viewer ---

export interface DiagramComponent {
  id: string;
  designator: string;
  name: string;
  type: string;
  bbox_pct: [number, number, number, number];
  specs: Record<string, string>;
}

export interface DiagramConnection {
  from_id: string;
  to_id: string;
  line_type: string;
  label?: string;
  waypoints?: [number, number][];
}

export interface FlowPath {
  line_type: string;
  path: string[];
}

export interface OperatingState {
  id: string;
  name: string;
  description: string;
  active_components: string[];
  flow_paths: FlowPath[];
}

export interface DiagramAnnotation {
  id: string;
  page_id: string;
  diagram_type: string;
  annotation_data: {
    components: DiagramComponent[];
    connections: DiagramConnection[];
  };
  component_count: number;
  connection_count: number;
  operating_states: OperatingState[];
  confidence_overall: number;
  generated_at?: string;
  verified?: boolean;
  cached?: boolean;
}

export interface DiagramPageItem {
  page_id: string;
  manual_id: string;
  page_number: number;
  classification: string;
  manual_title: string;
  annotated: boolean;
  component_count: number;
  confidence: number | null;
}

// --- Analysis / Inference ---

export interface CoverageAnalysis {
  manual_id: string;
  system_area: string;
  machine_model: string;
  coverage_score: number;
  has_service_manual: boolean;
  has_operator_manual: boolean;
  has_parts_manual: boolean;
  has_hydraulic_schematic: boolean;
  has_electrical_schematic: boolean;
  has_wiring_diagram: boolean;
  has_diagnostic_flowchart: boolean;
  gaps: { type: string; description: string; impact: string }[];
  strengths: string[];
  recommendations: string[];
  page_count: number;
}

export interface InferredComponent {
  id: string;
  component_name: string;
  component_type: string;
  designator: string | null;
  inferred_from: string;
  confidence: number;
  specs: Record<string, string>;
  notes?: string;
}

export interface GapAnalysis {
  manual_id: string;
  title: string;
  overall_quality: number;
  gaps: {
    category: string;
    description: string;
    impact: string;
    affected_systems: string[];
    recommendation: string;
  }[];
  coverage_by_area: {
    system_area: string;
    coverage: number;
    has_specs: boolean;
    has_procedures: boolean;
    has_diagrams: boolean;
    has_troubleshooting: boolean;
  }[];
}

// --- Teaching ---

export interface LearningPath {
  id: string;
  title: string;
  system_area: string;
  modules: LearningModule[];
  auto_generated: boolean;
}

export interface LearningModule {
  index: number;
  title: string;
  lessons: LearningLesson[];
  quiz_question_count: number;
}

export interface LearningLesson {
  index: number;
  title: string;
  page_ids: string[];
}

export interface LearningProgress {
  learning_path_id: string;
  mechanic_id: string;
  completed_modules: number;
  total_modules: number;
  quiz_scores: { module_index: number; score: number }[];
}
