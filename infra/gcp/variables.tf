# ---- Project & Deployment ----
variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "image_url" {
  type = string
}

# ---- API Keys (Sensitive) ----
variable "OPENAI_API_KEY" {
  sensitive = true
}

variable "ANTHROPIC_API_KEY" {
  sensitive = true
}

variable "GITHUB_TOKEN" {
  sensitive = true
}

# ---- Models ----
variable "DECISION_MODEL" {
  default = "claude-sonnet-4-20250514"
}

variable "CRITIC_MODEL" {
  default = "claude-sonnet-4-20250514"
}

variable "OPTIMISER_MODEL" {
  default = "claude-sonnet-4-20250514"
}

variable "RISK_MODEL" {
  default = "claude-sonnet-4-20250514"
}

variable "DECISION_MODEL_TEMPERATURE" {
  default = "0.0"
}

variable "OPTIMISER_MODEL_TEMPERATURE" {
  default = "0.0"
}

variable "CRITIC_MODEL_TEMPERATURE" {
  default = "0.0"
}

variable "RISK_MODEL_TEMPERATURE" {
  default = "0.0"
}

variable "DECISION_MODEL_TOKEN" {
  default = "4096"
}

variable "OPTIMISER_MODEL_TOKEN" {
  default = "4096"
}

variable "CRITIC_MODEL_TOKEN" {
  default = "4096"
}

variable "RISK_MODEL_TOKEN" {
  default = "4096"
}

# ---- Critic Config ----
variable "CRITIC_DEFAULT_QUALITY_SCORE" {
  default = "7"
}

variable "CRITIC_REGRESSION_PENALTY" {
  default = "0.05"
}

variable "CRITIC_UNRESOLVED_PENALTY" {
  default = "0.02"
}

# ---- Database ----
variable "DB_HOST" {
  default = "host.docker.internal"
}

variable "DB_PORT" {
  default = "5432"
}

variable "DB_NAME" {
  default = "pipeline_db"
}

variable "DB_USER" {
  default = "pipeline_user"
}

variable "DB_PASS" {
  sensitive = true
}

variable "DB_POOL_SIZE" {
  default = "5"
}

variable "DB_MAX_OVERFLOW" {
  default = "10"
}

# ---- App Config ----
variable "API_HOST" {
  default = "0.0.0.0"
}

variable "API_PORT" {
  default = "8091"
}

variable "LOG_LEVEL" {
  default = "DEBUG"
}

# ---- Git ----
variable "GIT_CLONE_DEPTH" {
  default = "1"
}

variable "GIT_TIMEOUT" {
  default = "300"
}

# ---- LLM ----
variable "LLM_MAX_RETRIES" {
  default = "3"
}

variable "LLM_TIMEOUT" {
  default = "60"
}

# ---- Workflow ----
variable "MAX_PLAN_TOOLS" {
  default = "10"
}

variable "ENABLE_PARALLEL_EXECUTION" {
  default = "false"
}

# ---- Runtime ----
variable "IS_LOCAL" {
  default = "false"
}
