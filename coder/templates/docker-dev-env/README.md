# Docker template

The template contained in this folder can be used to provision an environment containing all the necessary tools to develop and run on a Coder workspace.

## Upload a new version of the template

1. Login as a Coder admin user using the coder CLI
1. Run the follow command to upload the template to Coder:
  ```bash
  coder templates push docker-dev-env
  ```

## Prerequisites

A network named `coder-workspace` must exist.
