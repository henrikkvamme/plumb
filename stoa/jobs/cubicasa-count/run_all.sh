#!/usr/bin/env bash
# E1: two queues in parallel on one GPU. Each training writes out/logs/<name>.log.
set -u
mkdir -p out/logs
nvidia-smi --query-gpu=name,memory.total --format=csv
train() { name=$1; shift; echo "start $name $(date +%T)"; python train.py --name "$name" "$@" > "out/logs/$name.log" 2>&1; echo "end $name exit $? $(date +%T)"; tail -n 1 "out/logs/$name.log"; }
(
  train cnx-dino-1024 --backbone convnext_tiny.dinov3_lvd1689m --side 1024
  train vits-dino-1024 --backbone vit_small_patch16_dinov3.lvd1689m --side 1024 --lr 1e-4
) &
(
  train cnx-dino-768 --backbone convnext_tiny.dinov3_lvd1689m --side 768
  train cnx-in22k-1024 --backbone convnext_tiny.fb_in22k --side 1024
) &
wait
echo "all done $(date +%T)"
