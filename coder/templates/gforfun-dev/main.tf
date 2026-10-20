data "coder_provisioner" "me" {}
data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

locals {
  workspace_image = "ghcr.io/giovannibaratta/gforfun@sha256:dcb159d4c85422f3ba8cb65419ba37f9e7a04a71bf23b78a1a824fd9158f2772"

  # Pin this in source so an old saved Coder input cannot
  # silently keep provisioning the former synchronous storage class.
  storage_class = "piraeus-rwo-async"
}

resource "coder_agent" "main" {
  arch                    = data.coder_provisioner.me.arch
  os                      = "linux"
  startup_script_behavior = "blocking"
  startup_script          = <<-EOT
    echo "Configuring ephemeral instance ..."
    set -e

    install -d -m 0700 /tmp/podman-run-1001

    # Initialize home once, preserving any existing user settings.
    if [ ! -f ~/.init_done ]; then
      echo "Initializing user home ..."
      cp -an /etc/skel/. "$HOME/"
      touch ~/.init_done
    fi

    mkdir -p /workspace/gforfun

    echo "Installing VSCode server ..."
    curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone --prefix=/tmp/code-server --version 4.132.0

    echo "Starting VSCode server ..."
    /tmp/code-server/bin/code-server --auth none --port 13337 >/tmp/code-server.log 2>&1 &
  EOT
  # Tool settings and PATH come from the image; Coder extends PATH for its agent.

  env = {
    GIT_AUTHOR_NAME     = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_AUTHOR_EMAIL    = data.coder_workspace_owner.me.email
    GIT_COMMITTER_NAME  = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_COMMITTER_EMAIL = data.coder_workspace_owner.me.email
  }

  metadata {
    display_name = "CPU"
    key          = "cpu"
    script       = "coder stat cpu"
    interval     = 10
    timeout      = 1
  }
  metadata {
    display_name = "Memory"
    key          = "memory"
    script       = "coder stat mem"
    interval     = 10
    timeout      = 1
  }
}

resource "coder_app" "code-server" {
  agent_id     = coder_agent.main.id
  slug         = "code-server"
  display_name = "code-server"
  url          = "http://localhost:13337/?folder=/workspace/gforfun/project"
  icon         = "/icon/code.svg"
  subdomain    = false
  share        = "owner"
  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 5
    threshold = 6
  }
}

resource "kubernetes_persistent_volume_claim_v1" "home" {
  wait_until_bound = false

  metadata {
    name      = "coder-${data.coder_workspace.me.id}-gforfun-home"
    namespace = var.namespace
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = local.storage_class
    resources {
      requests = {
        storage = "${var.home_storage_gib}Gi"
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
    name      = "coder-${data.coder_workspace.me.id}-gforfun-workspace"
    namespace = var.namespace
  }
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = local.storage_class
    resources {
      requests = {
        storage = "${var.workspace_storage_gib}Gi"
      }
    }
  }
  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

resource "kubernetes_pod_v1" "workspace" {
  count = data.coder_workspace.me.start_count
  metadata {
    name      = "coder-${data.coder_workspace.me.id}-gforfun"
    namespace = var.namespace
    labels = {
      "app.kubernetes.io/name"     = "coder-workspace"
      "app.kubernetes.io/instance" = data.coder_workspace.me.name
      "security.coder.dev/bwrap"   = "true"
    }
  }
  spec {
    automount_service_account_token = false
    node_selector = {
      "kubernetes.io/hostname" = var.node_name
      "kubernetes.io/arch"     = "amd64"
    }
    # Kubernetes mounts a fresh PVC as root; it does not copy image home files.
    # Change only the mount root, preserving existing project file ownership.
    init_container {
      name              = "init-permissions"
      image             = local.workspace_image
      image_pull_policy = "Always"
      command           = ["sh", "-ec", "chown 1001:1001 /home/coder /workspace /ephemeral; chmod 0755 /home/coder /workspace; chmod 0700 /ephemeral"]
      security_context {
        run_as_user                = 0
        run_as_group               = 0
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
        mount_path = "/home/coder"
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

    container {
      name              = "dev"
      image             = local.workspace_image
      image_pull_policy = "Always"
      command           = ["sh", "-c", coder_agent.main.init_script]
      working_dir       = "/workspace"
      env {
        name  = "HOME"
        value = "/home/coder"
      }
      env {
        name  = "XDG_RUNTIME_DIR"
        value = "/tmp/podman-run-1001"
      }
      env {
        name  = "CODER_AGENT_TOKEN"
        value = coder_agent.main.token
      }
      security_context {
        run_as_user     = 1001
        run_as_group    = 1001
        run_as_non_root = true
        privileged      = false
        # Allow the AppArmor transition into the existing Bubblewrap child
        # profile. The image removes setuid/setgid bits and drops all caps.
        allow_privilege_escalation = true
        read_only_root_filesystem  = true
        capabilities {
          drop = ["ALL"]
        }
        seccomp_profile {
          type              = "Localhost"
          localhost_profile = "coder-workspace.json"
        }
      }
      volume_mount {
        name       = "home-dir"
        mount_path = "/home/coder"
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
      empty_dir {
        size_limit = "${var.ephemeral_storage_gib}Gi"
      }
    }
    volume {
      name = "tmp"
      empty_dir {
        size_limit = "2Gi"
      }
    }
    volume {
      name = "var-tmp"
      empty_dir {
        size_limit = "2Gi"
      }
    }
  }
}
