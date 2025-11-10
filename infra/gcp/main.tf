
locals {
  secrets = {
    OPENAI_API_KEY    = var.OPENAI_API_KEY
    ANTHROPIC_API_KEY = var.ANTHROPIC_API_KEY
    GITHUB_TOKEN      = var.GITHUB_TOKEN
    DB_PASS           = var.DB_PASS
  }
}


# vpc
resource "google_compute_network" "vpc" {
  name = "optimiser-vpc"
}

resource "google_compute_subnetwork" "subnet" {
  name          = "optimiser-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}


# private services connection
resource "google_compute_global_address" "private_ip_range" {
  name          = "sql-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
  project       = var.project_id
}


# vpc peering to psc
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}



resource "google_secret_manager_secret" "secrets" {
  for_each = local.secrets

  secret_id = each.key
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "secrets_version" {
  for_each = local.secrets

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value
}




# postgreSQL
resource "google_sql_database_instance" "postgres_instance" {
  name             = "optimiser-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}


# pipeline optimiser - cloud run service
resource "google_service_account" "cloudrun_sa" {
  account_id   = "cloudrun-optimiser-sa"
  display_name = "Cloud Run Optimiser Service Account"
}

resource "google_secret_manager_secret_iam_member" "cloudrun_secret_access" {
  for_each = google_secret_manager_secret.secrets

  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloudrun_sa.email}"
}

resource "google_cloud_run_service" "optimiser" {
  name     = "optimiser-service"
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.cloudrun_sa.email

      containers {
        image = var.image_url

        # Secure env vars from Secret Manager
        dynamic "env" {
          for_each = {
            OPENAI_API_KEY    = google_secret_manager_secret.secrets["OPENAI_API_KEY"].secret_id
            ANTHROPIC_API_KEY = google_secret_manager_secret.secrets["ANTHROPIC_API_KEY"].secret_id
            GITHUB_TOKEN      = google_secret_manager_secret.secrets["GITHUB_TOKEN"].secret_id
            DB_PASS           = google_secret_manager_secret.secrets["DB_PASS"].secret_id
          }
          content {
            name = env.key
            value_from {
              secret_key_ref {
                name = env.value
                key  = "latest"
              }
            }
          }
        }

        dynamic "env" {
          for_each = {
            DECISION_MODEL               = var.DECISION_MODEL
            CRITIC_MODEL                 = var.CRITIC_MODEL
            OPTIMISER_MODEL              = var.OPTIMISER_MODEL
            RISK_MODEL                   = var.RISK_MODEL
            DECISION_MODEL_TEMPERATURE   = var.DECISION_MODEL_TEMPERATURE
            OPTIMISER_MODEL_TEMPERATURE  = var.OPTIMISER_MODEL_TEMPERATURE
            CRITIC_MODEL_TEMPERATURE     = var.CRITIC_MODEL_TEMPERATURE
            RISK_MODEL_TEMPERATURE       = var.RISK_MODEL_TEMPERATURE
            DECISION_MODEL_TOKEN         = var.DECISION_MODEL_TOKEN
            OPTIMISER_MODEL_TOKEN        = var.OPTIMISER_MODEL_TOKEN
            CRITIC_MODEL_TOKEN           = var.CRITIC_MODEL_TOKEN
            RISK_MODEL_TOKEN             = var.RISK_MODEL_TOKEN
            CRITIC_DEFAULT_QUALITY_SCORE = var.CRITIC_DEFAULT_QUALITY_SCORE
            CRITIC_REGRESSION_PENALTY    = var.CRITIC_REGRESSION_PENALTY
            CRITIC_UNRESOLVED_PENALTY    = var.CRITIC_UNRESOLVED_PENALTY
            DB_HOST                      = "/cloudsql/${google_sql_database_instance.postgres_instance.connection_name}"
            DB_PORT                      = "5432"
            DB_NAME                      = var.DB_NAME
            DB_USER                      = var.DB_USER
            DB_POOL_SIZE                 = var.DB_POOL_SIZE
            DB_MAX_OVERFLOW              = var.DB_MAX_OVERFLOW
            API_HOST                     = var.API_HOST
            API_PORT                     = var.API_PORT
            LOG_LEVEL                    = var.LOG_LEVEL
            GIT_CLONE_DEPTH              = var.GIT_CLONE_DEPTH
            GIT_TIMEOUT                  = var.GIT_TIMEOUT
            LLM_MAX_RETRIES              = var.LLM_MAX_RETRIES
            LLM_TIMEOUT                  = var.LLM_TIMEOUT
            MAX_PLAN_TOOLS               = var.MAX_PLAN_TOOLS
            ENABLE_PARALLEL_EXECUTION    = var.ENABLE_PARALLEL_EXECUTION
            IS_LOCAL                     = var.IS_LOCAL
          }
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "DATABASE_URL"
          value = "postgresql://${var.DB_USER}:${var.DB_PASS}@/${var.DB_NAME}?host=/cloudsql/${google_sql_database_instance.postgres_instance.connection_name}"
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# Allow unauthenticated access (optional)
resource "google_cloud_run_service_iam_member" "public_invoker" {
  service  = google_cloud_run_service.optimiser.name
  location = google_cloud_run_service.optimiser.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "cloud_run_url" {
  value = google_cloud_run_service.optimiser.status[0].url
}

output "db_connection_name" {
  value = google_sql_database_instance.postgres_instance.connection_name
}
