IMAGE=ts/tscached

docker rmi -f $IMAGE
chmod +x run-kairosdb.sh
docker build -t $IMAGE .