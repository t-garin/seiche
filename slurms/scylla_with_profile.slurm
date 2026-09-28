#!/bin/bash -l

#SBATCH --job-name seiche-profile
#SBATCH --output=/archive2/globc/seiche/logs/seiche_profile_%j.log
#SBATCH --nodes=1 --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=350G
#SBATCH --partition prod

just run-with-profile "$1"
