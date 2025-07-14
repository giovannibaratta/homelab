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

## F.A.Q.

#### Workspace is not able to start

Issue: Workspace is not able to start and the following error is displayed:

```bash
: invalid option
set: usage: set [-abefhkmnptuvxBCEHPT] [-o option-name] [--] [-] [arg ...]
/bin/bash: line 2: $'\r': command not found
/bin/bash: -c: line 12: syntax error: unexpected end of file
```

Reason: the `main.tf` might use the wrong format for the carriage return. Use `dos2unix` to fix the file.
