"""Shared constants and enums for ManualWorx."""

from enum import StrEnum


class PageClassification(StrEnum):
    TEXT = "text"
    HYDRAULIC_SCHEMATIC = "hydraulic_schematic"
    ELECTRICAL_DIAGRAM = "electrical_diagram"
    PARTS_EXPLODED_VIEW = "parts_exploded_view"
    TORQUE_SPEC_TABLE = "torque_spec_table"
    DIAGNOSTIC_FLOWCHART = "diagnostic_flowchart"
    WIRING_HARNESS = "wiring_harness"
    GENERAL_ILLUSTRATION = "general_illustration"


class UserRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    TECHNICIAN = "technician"


class SkillLevel(StrEnum):
    GREEN = "green"
    APPRENTICE = "apprentice"
    JOURNEYMAN = "journeyman"


class SubscriptionPlan(StrEnum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    SHOP = "shop"


class TenantType(StrEnum):
    SHOP = "shop"
    INDIVIDUAL = "individual"


class ManualType(StrEnum):
    SERVICE = "service"
    OPERATOR = "operator"
    PARTS = "parts"


class ManualStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class QueryMode(StrEnum):
    AUTO = "auto"
    QA = "qa"
    TROUBLESHOOT = "troubleshoot"
    DIAGRAM = "diagram"
    PROCEDURE = "procedure"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFERENCE = "inference"


class DocumentType(StrEnum):
    TROUBLESHOOTING_GUIDE = "troubleshooting_guide"
    SERVICE_PROCEDURE = "service_procedure"
    PARTS_REFERENCE = "parts_reference"
    QUICK_REFERENCE = "quick_reference"
    TRAINING_LESSON = "training_lesson"
    QUIZ_ASSESSMENT = "quiz_assessment"
    PROGRESS_REPORT = "progress_report"
    SYSTEM_ANALYSIS = "system_analysis"
    GAP_REPORT = "gap_report"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class DiagramType(StrEnum):
    HYDRAULIC_SCHEMATIC = "hydraulic_schematic"
    ELECTRICAL = "electrical"
    WIRING = "wiring"


class LearningStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class QuestionType(StrEnum):
    CONCEPT = "concept"
    DIAGRAM_ID = "diagram_id"
    SCENARIO = "scenario"
    SEQUENCE = "sequence"
    SAFETY = "safety"


class TeachDepth(StrEnum):
    FULL = "full"
    STANDARD = "standard"
    QUICK = "quick"
    SKIPPED = "skipped"


# Plan configuration with limits and pricing
PLAN_CONFIG = {
    SubscriptionPlan.FREE: {
        "price_monthly": 0,
        "users": 1,
        "manuals": 2,
        "queries_monthly": 25,
        "docs_monthly": 5,
        "teaching_mode": False,
        "schematic_viewer": "view_only",
        "ai_schematics": False,
        "confidence_detail": "basic",
        "shared_library": False,
        "api_access": False,
    },
    SubscriptionPlan.STARTER: {
        "price_monthly": 2900,  # cents
        "users": 1,
        "manuals": 10,
        "queries_monthly": 200,
        "docs_monthly": 25,
        "teaching_mode": "basic",
        "schematic_viewer": "full",
        "ai_schematics": False,
        "confidence_detail": "full",
        "shared_library": "use",
        "api_access": False,
    },
    SubscriptionPlan.PRO: {
        "price_monthly": 5900,
        "users": 1,
        "manuals": 50,
        "queries_monthly": 1000,
        "docs_monthly": -1,  # unlimited
        "teaching_mode": "full",
        "schematic_viewer": "full",
        "ai_schematics": True,
        "confidence_detail": "full",
        "shared_library": "use_contribute",
        "api_access": False,
    },
    SubscriptionPlan.SHOP: {
        "price_monthly": 9900,  # base price
        "price_per_user": 2900,
        "users": -1,  # unlimited (priced per user)
        "manuals": -1,  # unlimited
        "queries_per_user_monthly": 500,
        "docs_monthly": -1,
        "teaching_mode": "full",
        "schematic_viewer": "full",
        "ai_schematics": True,
        "confidence_detail": "full",
        "shared_library": "use_contribute",
        "api_access": True,
    },
}

# Processing fees by plan and page count tier (in cents)
PROCESSING_FEES = {
    SubscriptionPlan.FREE: {"small": 500, "medium": 1500, "large": 2500},
    SubscriptionPlan.STARTER: {"small": 500, "medium": 1500, "large": 2500},
    SubscriptionPlan.PRO: {"small": 300, "medium": 1000, "large": 2000},
    SubscriptionPlan.SHOP: {"small": 200, "medium": 800, "large": 1500},
}

# Page count tier thresholds
PAGE_TIER_SMALL_MAX = 500
PAGE_TIER_MEDIUM_MAX = 2000

# Hydraulic diagram color codes
HYDRAULIC_COLORS = {
    "pressure": "#E53E3E",
    "return": "#3182CE",
    "pilot": "#ECC94B",
    "drain": "#38A169",
    "charge": "#ED8936",
    "inactive": "#A0AEC0",
    "electrical_signal": "#805AD5",
}

# Electrical diagram color codes
ELECTRICAL_COLORS = {
    "power_positive": "#E53E3E",
    "ground_negative": "#1A202C",
    "signal_data": "#3182CE",
    "switched_power": "#ECC94B",
    "can_bus": "#38A169",
    "sensor_signal": "#ED8936",
    "inactive": "#A0AEC0",
}

# Confidence score thresholds
CONFIDENCE_THRESHOLDS = {
    ConfidenceLevel.HIGH: (0.80, 1.00),
    ConfidenceLevel.MODERATE: (0.60, 0.79),
    ConfidenceLevel.LOW: (0.40, 0.59),
    ConfidenceLevel.INFERENCE: (0.00, 0.39),
}

# Source quality weights for confidence calculation
SOURCE_WEIGHTS = {
    "oem_manual_text": 0.95,
    "oem_manual_table": 0.95,
    "oem_diagram_clear": 0.90,
    "oem_diagram_partial": 0.70,
    "user_uploaded_diagram": 0.75,
    "cross_reference_match": 0.80,
    "model_knowledge": 0.60,
    "general_knowledge": 0.45,
    "inference_from_similar": 0.40,
    "pure_inference": 0.25,
}

# RBAC permission matrix
PERMISSIONS = {
    "query_manuals": [UserRole.OWNER, UserRole.MANAGER, UserRole.TECHNICIAN],
    "use_troubleshooting": [UserRole.OWNER, UserRole.MANAGER, UserRole.TECHNICIAN],
    "use_viewer": [UserRole.OWNER, UserRole.MANAGER, UserRole.TECHNICIAN],
    "complete_training": [UserRole.OWNER, UserRole.MANAGER, UserRole.TECHNICIAN],
    "generate_documents": [UserRole.OWNER, UserRole.MANAGER, UserRole.TECHNICIAN],
    "upload_manuals": [UserRole.OWNER, UserRole.MANAGER],
    "delete_manuals": [UserRole.OWNER, UserRole.MANAGER],
    "view_all_progress": [UserRole.OWNER, UserRole.MANAGER],
    "assign_learning_paths": [UserRole.OWNER, UserRole.MANAGER],
    "manage_users": [UserRole.OWNER],
    "manage_billing": [UserRole.OWNER],
    "view_usage_dashboard": [UserRole.OWNER, UserRole.MANAGER],
    "verify_annotations": [UserRole.OWNER, UserRole.MANAGER],
    "manage_api_keys": [UserRole.OWNER],
}

# --- Operational constants (Phase 9: Polish) ---

# Timeouts (seconds)
AI_API_TIMEOUT = 60
EMBEDDING_TIMEOUT = 30
OCR_TIMEOUT = 120
STORAGE_TIMEOUT = 30

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Upload limits
MAX_UPLOAD_MB = 100
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {"application/pdf"}

# Rate limit cache TTL (seconds) — how long to cache tenant query limits in Redis
RATE_LIMIT_CACHE_TTL = 300  # 5 minutes

# Worker retry configuration
WORKER_MAX_RETRIES = 3
WORKER_RETRY_BACKOFF_BASE = 2  # exponential: 2s, 4s, 8s
