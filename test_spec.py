
import os
from pathlib import Path
print('__file__ value:', repr(__file__))
_p = Path(__file__).resolve()
print('Resolved:', _p)
