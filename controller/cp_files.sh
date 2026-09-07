CONTAINER_NAME=${1:-toolathlon-dev-controller-1}

docker cp /data01/zhangx/files/bin/kind ${CONTAINER_NAME}:/usr/local/bin/kind
docker cp /data01/zhangx/files/bin/kubectl ${CONTAINER_NAME}:/usr/local/bin/kubectl

