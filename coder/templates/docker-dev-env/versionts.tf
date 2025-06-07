terraform {
  required_providers {
    coder = {
      source  = "coder/coder"
      version = "2.5.3"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "3.6.1"
    }
  }
}
