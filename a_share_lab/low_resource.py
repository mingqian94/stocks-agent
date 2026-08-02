"""Process-level resource caps shared by optional research runners."""

from __future__ import annotations

import os


THREAD_ENVIRONMENT_VARIABLES = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def configure_low_resource_environment(cpu_threads: int = 1) -> None:
    if cpu_threads != 1:
        raise ValueError("the desktop research runtime requires exactly one CPU thread")
    for name in THREAD_ENVIRONMENT_VARIABLES:
        os.environ[name] = str(cpu_threads)
