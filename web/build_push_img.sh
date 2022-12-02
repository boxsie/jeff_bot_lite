#!/bin/bash

docker build -t meat-o-matic-web:local .
docker save meat-o-matic-web > serves_mom_web.tar
microk8s ctr image import serves_mom_web.tar
rm -rf serves_mom_web.tar

microk8s.kubectl delete deployment -n discord discord-bot-web-deployment
microk8s.kubectl apply -n discord -f deployment/manifest.yml