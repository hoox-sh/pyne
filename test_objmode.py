import numba
from numba import objmode

logs = []


def python_log(msg):
    logs.append(msg)


@numba.njit
def execute_with_logs(arr):
    for i in range(len(arr)):
        if arr[i] > 5:
            # We must specify the return types in objmode even if None, actually maybe not?
            # Let's try
            with objmode():
                python_log(f"Value > 5 at {i}")


import numpy as np

execute_with_logs(np.array([1, 2, 6, 3, 7]))
print(logs)
