terraform {
  required_providers {
    coder = {
      source  = "coder/coder"
      version = "2.3.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "3.0.2"
    }
  }
}
