# Temporary expose a port on a Docker container

Docker does not allow you to expose a port on a running container. As an alternative, you can use the following steps to temporarily expose a port on a running Docker container:
1. Run a `socat` based container to forward the port from the running container to another container on the same Docker network.

    ```bash
    podman run \
      -it \
      --publish 10000:5432 \
      --network bitmagnet \
      alpine/socat \
      tcp-listen:5432,fork,reuseaddr tcp-connect:bitmagnet-db:5432
    ```
1. Use SSH to local forward the port from your local machine to the host running the Docker container.

    ```bash
    ssh -L 10000:localhost:10000 user@host
    ```