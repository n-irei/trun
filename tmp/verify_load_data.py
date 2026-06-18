from pathlib import Path
import sys
sys.path.insert(0, "/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/bots/cpfx/1hto4h_exit3h")
from pipeline import load_data

df = load_data(Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/data/BTCUSD_m15_mt5.csv"))
print(len(df), df.index[0])
