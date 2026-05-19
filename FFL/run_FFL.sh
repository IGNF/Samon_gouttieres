#!/bin/bash
#SBATCH --nodes=1           # total number of nodes (N to be defined)
#SBATCH --ntasks-per-node=1  # number of tasks per node //!!\\ for pytorch_lightning, ntasks-per-node = nb gpus. For pytorch, ntask-per-node = 1 (number of torchrun) 
#SBATCH --cpus-per-task=12   # Cores: 16 per GPU, 48 total
#SBATCH --gres=gpu:1        # number of GPUs reserved per node (here 3, or all the GPUs)
#SBATCH --hint=nomultithread # SLURM multithreading =/= server multithreading
#SBATCH --mem=15G           # 0 = unlimited memory, Max 450G. Unlimited memory = you request the whole node
#SBATCH --partition=jean-zellou


#SBATCH -e /.../example_script_2n-%j.err
#SBATCH -o /.../example_script_2n-%j.out

export SRUN_CPUS_PER_TASK=12

eval "$(conda shell.bash hook)"
conda activate ffl-michael

#srun -vv python custom_inf.py --run_name v12.uresnet101_scale_pretrain.p4_750 --in_filepath /path_to_images/*.jp2 --out_dirpath /outdir



## Modèle réentraîné sur données IGN
srun -vv python custom_inf.py --run_name b8_512px_dataset135_ep00_lr3E-6 --in_filepath /path_to_images/*.jp2 --out_dirpath /outdir


echo "Job complete"
