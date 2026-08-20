terraform {
  required_providers {
    coder = {
      source  = "coder/coder"
      version = ">= 0.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.20"
    }
  }
}

provider "coder" {}

provider "kubernetes" {
  # In-cluster configuration when running from Coder Server inside K8s
  # Falls back to ~/.kube/config when run locally
}

locals {
  username = data.coder_workspace_owner.me.name
}

data "coder_provisioner" "me" {}
data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

resource "coder_agent" "main" {
  arch           = data.coder_provisioner.me.arch
  os             = "linux"
  startup_script = <<-EOT
    echo "Configuring ephemeral instance ..."
    set -e

    # Ensure ephemeral storage and workspace ownership
    sudo chown -R ${local.username}:containers /ephermeral 2>/dev/null || true
    sudo chmod -R 775 /ephermeral 2>/dev/null || true
    sudo chown -R ${local.username}:${local.username} /workspace 2>/dev/null || true

    # Prepare user home with default files on first start
    if [ ! -f ~/.init_done ]; then
      echo "Initializing user home ..."
      cp -rT /etc/skel ~
      touch ~/.init_done
    fi

    echo "Installing VSCode server ..."
    curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone --prefix=/tmp/code-server --version 4.132.0

    echo "Starting VSCode server ..."
    /tmp/code-server/bin/code-server --auth none --port 13337 >/tmp/code-server.log 2>&1 &
  EOT

  env = {
    GIT_AUTHOR_NAME     = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_AUTHOR_EMAIL    = data.coder_workspace_owner.me.email
    GIT_COMMITTER_NAME  = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_COMMITTER_EMAIL = data.coder_workspace_owner.me.email
  }

  metadata {
    display_name = "CPU Usage"
    key          = "0_cpu_usage"
    script       = "coder stat cpu"
    interval     = 10
    timeout      = 1
  }

  metadata {
    display_name = "RAM Usage"
    key          = "1_ram_usage"
    script       = "coder stat mem"
    interval     = 10
    timeout      = 1
  }
}

resource "coder_app" "code-server" {
  agent_id     = coder_agent.main.id
  slug         = "code-server"
  display_name = "code-server"
  url          = "http://localhost:13337/?folder=/workspace"
  icon         = "/icon/code.svg"
  subdomain    = false
  share        = "owner"

  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 5
    threshold = 6
  }
}

# Persistent Volume Claims per workspace
resource "kubernetes_persistent_volume_claim_v1" "home" {
  wait_until_bound = false
  metadata {
    name      = "coder-${data.coder_workspace.me.id}-home"
    namespace = "coder-workspaces"
  }
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "piraeus-rwo-async"
    resources {
      requests = {
        storage = "10Gi"
      }
    }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

resource "kubernetes_persistent_volume_claim_v1" "workspace" {
  wait_until_bound = false
  metadata {
    name      = "coder-${data.coder_workspace.me.id}-workspace"
    namespace = "coder-workspaces"
  }
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "piraeus-rwo-async"
    resources {
      requests = {
        storage = "50Gi"
      }
    }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

# Workspace Pod inside isolated coder-workspaces namespace
resource "kubernetes_pod_v1" "workspace" {
  count = data.coder_workspace.me.start_count
  metadata {
    name      = "coder-${lower(data.coder_workspace_owner.me.name)}-${lower(data.coder_workspace.me.name)}"
    namespace = "coder-workspaces"
    labels = {
      "app.kubernetes.io/name"     = "coder-workspace"
      "app.kubernetes.io/instance" = data.coder_workspace.me.name
    }
  }

  spec {
    # Pin workspace strictly to node2
    node_selector = {
      "kubernetes.io/hostname" = "node2"
    }

    # One-shot init container to guarantee volume ownership before dev container starts
    init_container {
      name    = "init-permissions"
      image   = "ghcr.io/giovannibaratta/coder-dev-env:v0.0.4"
      command = ["sh", "-c", "chown -R 1001:1001 /ephermeral /workspace /home/${local.username} 2>/dev/null || true; chmod -R 775 /ephermeral 2>/dev/null || true"]
      security_context {
        run_as_user = 0
        privileged  = true
      }
      volume_mount {
        name       = "home-dir"
        mount_path = "/home/${local.username}"
      }
      volume_mount {
        name       = "workspace-dir"
        mount_path = "/workspace"
      }
      volume_mount {
        name       = "ephemeral-storage"
        mount_path = "/ephermeral"
      }
    }

    # Main Dev Workspace Container (Rootless Podman / DinD in K8s)
    container {
      name              = "dev"
      image             = "ghcr.io/giovannibaratta/coder-dev-env:v0.0.4"
      image_pull_policy = "Always"
      command           = ["sh", "-c", coder_agent.main.init_script]

      security_context {
        privileged = true
      }

      env {
        name  = "CODER_AGENT_TOKEN"
        value = coder_agent.main.token
      }

      volume_mount {
        name       = "home-dir"
        mount_path = "/home/${local.username}"
      }
      volume_mount {
        name       = "workspace-dir"
        mount_path = "/workspace"
      }
      volume_mount {
        name       = "ephemeral-storage"
        mount_path = "/ephermeral"
      }
    }

    # Volumes
    volume {
      name = "home-dir"
      persistent_volume_claim {
        claim_name = kubernetes_persistent_volume_claim_v1.home.metadata[0].name
      }
    }
    volume {
      name = "workspace-dir"
      persistent_volume_claim {
        claim_name = kubernetes_persistent_volume_claim_v1.workspace.metadata[0].name
      }
    }
    volume {
      name = "ephemeral-storage"
      empty_dir {}
    }
  }
}
