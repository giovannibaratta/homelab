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

    # Volume ownership is prepared by init-permissions; no runtime sudo.
    install -d -m 0700 /tmp/podman-run-1001

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
      "security.coder.dev/bwrap"   = "true"
    }
  }

  spec {
    # Pin workspace strictly to node2
    automount_service_account_token = false

    node_selector = {
      "kubernetes.io/hostname" = "node2"
    }

    # One-shot init container to guarantee volume ownership before dev container starts
    init_container {
      name  = "init-permissions"
      image = "ghcr.io/giovannibaratta/coder-dev-env:v0.0.5"
      # Do not recursively chown Podman data or persistent workspaces: subordinate
      # IDs in existing files must survive restarts. Only prepare mount roots.
      command = ["sh", "-ec", "chown 1001:1001 /ephemeral /workspace /home/${local.username}; chmod 0770 /ephemeral"]

      security_context {
        run_as_user                = 0
        privileged                 = false
        allow_privilege_escalation = false
        read_only_root_filesystem  = true
        capabilities {
          drop = ["ALL"]
          add  = ["CHOWN", "FOWNER"]
        }
        seccomp_profile {
          type = "RuntimeDefault"
        }
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
        mount_path = "/ephemeral"
      }
    }

    # Main Dev Workspace Container (Rootless Podman / DinD in K8s)
    container {
      name              = "dev"
      image             = "ghcr.io/giovannibaratta/coder-dev-env:v0.0.5"
      image_pull_policy = "Always"
      command           = ["sh", "-c", coder_agent.main.init_script]

      # Kubelet injects TUN and its device-cgroup permission for rootless Pasta.
      # A hostPath mount alone does not grant device-cgroup access.
      resources {
        limits = {
          "devic.es/coder-tun" = "1"
        }
        requests = {
          "devic.es/coder-tun" = "1"
        }
      }

      security_context {
        privileged                = false
        run_as_user               = 1001
        run_as_group              = 1001
        run_as_non_root           = true
        read_only_root_filesystem = true
        # Required for file-capability newuidmap/newgidmap. No sudo/setuid tools.
        allow_privilege_escalation = true
        capabilities {
          drop = ["ALL"]
          add  = ["SETUID", "SETGID"]
        }

        # Node-local denylist preserves namespace/mount calls while blocking
        # unrelated high-risk kernel APIs. Installed alongside AppArmor.
        seccomp_profile {
          type              = "Localhost"
          localhost_profile = "coder-workspace.json"
        }
      }

      # The Unix user is fixed at coder:1001 in the image, but the persistent
      # home volume is mounted using the Coder owner's username.
      env {
        name  = "HOME"
        value = "/home/${local.username}"
      }

      env {
        name  = "XDG_RUNTIME_DIR"
        value = "/tmp/podman-run-1001"
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
        mount_path = "/ephemeral"
      }

      volume_mount {
        name       = "tmp"
        mount_path = "/tmp"
      }

      volume_mount {
        name       = "var-tmp"
        mount_path = "/var/tmp"
      }
    }

    # Volumes
    volume {
      name = "tmp"
      empty_dir {}
    }

    volume {
      name = "var-tmp"
      empty_dir {}
    }

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
