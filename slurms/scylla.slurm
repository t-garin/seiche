#!/bin/bash -l

#SBATCH --job-name seiche
#SBATCH --output=/archive2/globc/seiche/logs/seiche_%j.log
#SBATCH --nodes=1 --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=350G
#SBATCH --partition prod 

just run "$1"