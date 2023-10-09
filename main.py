# main.py
from internal.cli import CLI
from jsonargparse import lazy_instance

from internal.gaussian_splatting import GaussianSplatting
from internal.dataset import DataModule
from internal.callbacks import SaveGaussianToPly
import lightning.pytorch.loggers


def cli_main():
    cli = CLI(
        GaussianSplatting,
        DataModule,
        seed_everything_default=42,
        auto_configure_optimizers=False,
        trainer_defaults={
            "accelerator": "gpu",
            "strategy": "auto",
            "devices": 1,
            # "logger": "TensorBoardLogger",
            "num_sanity_val_steps": 1,
            # "max_epochs": -1,
            "max_steps": 30_000,
            "use_distributed_sampler": False,  # use custom ddp sampler
            "callbacks": [
                lazy_instance(SaveGaussianToPly),
            ],
        },
        save_config_kwargs={"overwrite": True},
    )
    # note: don't call fit!!


if __name__ == "__main__":
    cli_main()
    # note: it is good practice to implement the CLI in a function and call it in the main if block
