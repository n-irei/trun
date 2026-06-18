# CPFX2 run_local_v2_cpfx2.py 作成 / S1: 骨格 + CSV読込 + 特徴量計算

## 背景・目的
CPFX2（4時間足）のバックテストをTradingViewデータ相当のCSVで実行するため、
CPX1のrun_local_v2.pyを参考にしたCPFX2専用スクリプトを新規作成する。
S1では骨格・CSV読込・特徴量計算（train_v2_4h.pyのロジック流用）までを実装する。

## 作業対象（新規作成）
`/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/run_local_v2_cpfx2.py`

## 参照ファイル
- `/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/train_v2_4h.py`（特徴量計算・モデルパス）
- `/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/run_local_v2.py`（骨格参照）

## 作業内容

### S1でやること
1. ファイル骨格作成（imports・定数・main関数）
2. BTCUSD240.csv読込（train_v2_4h.pyのload_data()と同一ロジック）
3. 特徴量計算（train_v2_4h.pyのbuild_features()と同一ロジック）
4. CPFX2モデルロード（btcusd_buy_3bar.joblib / btcusd_sell_3bar.joblib）
5. 構文チェックのみ（実行はS2以降）

### 定数
```python
DATA_PATH  = Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/data/BTCUSD240.csv")
MODEL_DIR  = Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/strategies/CPFX2/models_v2/")
CONFIG_PATH = Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/strategies/CPX1/btcusd/config.json")
OUTPUT_DIR = Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/output/")
HORIZON_BARS = 3   # 3バー後（12時間後）判定
PROB_THRESHOLD = 0.55  # シグナル閾値（暫定）
```

### 特徴量カラム（train_v2_4h.pyと同一）
```python
FEATURE_COLS = [
    "mom_4h_1", "mom_4h_3", "mom_4h_5", "vol_ratio_20h",
    "atr_14_4h", "rsi_14_4h", "macd_diff", "hour", "dow",
    "is_tokyo", "is_london", "is_ny", "entry_bar_offset", "pattern_body_ratio",
]
```

### 関数構成
```python
def load_data() -> pd.DataFrame:
    # train_v2_4h.pyのload_data()と同一

def resample_20h(df_4h) -> pd.DataFrame:
    # train_v2_4h.pyのresample_20h()と同一

def build_features(df_4h, df_20h, config) -> pd.DataFrame:
    # train_v2_4h.pyのbuild_features()と同一ロジック

def load_models() -> dict:
    # buy_model, sell_model をjoblibでロードして返す
    # {"buy": model, "sell": model}

def main():
    df_4h = load_data()
    df_20h = resample_20h(df_4h)
    config = json.load(open(CONFIG_PATH))
    df_feat = build_features(df_4h, df_20h, config)
    models = load_models()
    print(f"[S1完了] データ行数: {len(df_feat)}, 特徴量カラム: {len(FEATURE_COLS)}")
    print(f"[S1完了] モデルロード: buy={models['buy'].__class__.__name__}, sell={models['sell'].__class__.__name__}")
```

## SPARC
- **S（仕様）**: run_local_v2_cpfx2.pyの骨格・CSV読込・特徴量計算・モデルロードを実装し、構文・動作確認まで行う
- **P（疑似コード）**:

      入力: BTCUSD240.csv
      処理: load_data() → resample_20h() → build_features() → load_models()
      出力: print("[S1完了]...") で確認

- **A（設計）**: 新規ファイル1本のみ。既存ファイル変更なし。
- **R（セルフレビュー）**: 実装後に python3 -c "import ast; ast.parse(open('...').read())" で構文確認
- **C（完了）**: `python3 run_local_v2_cpfx2.py` → `[S1完了]` が表示されること

## 設計確認済み事項
- 責務: run_local_v2_cpfx2.pyがCSV読込・特徴量計算・モデルロードを担う
- データ書き込み先: なし（S1はprintのみ）
- ADR更新: 不要

## 🚫 除外スコープ（やらないこと）
- シグナル生成・判定ロジックはS2で行う（S1では不要）
- CSV保存はS2で行う
- run_local_v2.pyは変更しない
- train_v2_4h.pyは変更しない
- tv_server.py・cpx1_core.py等の既存ファイルは変更しない
- 新規ディレクトリ作成は output/ のみ（mkdir -p）

## 完了条件
- [ ] `python3 -c "import ast; ast.parse(open('/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/run_local_v2_cpfx2.py').read()); print('構文OK')"` → `構文OK`
- [ ] `python3 /mnt/c/Users/pcuser/Documents/MyVault/quant_lab/prod/cpfx2/run_local_v2_cpfx2.py` → `[S1完了]` が表示される
- [ ] 変更ファイル: run_local_v2_cpfx2.py のみ（新規1本）
- [ ] 除外スコープ違反なし
- [ ] 完了報告を `output/claude_cpfx2_run_local_v2_s1_out.md` に保存

## 注意事項
- python3 を使うこと（CODING_RULES.md #14）
- train_v2_4h.pyの関数をコピーして流用すること（新規ロジック作成禁止）
- PatternDetectorはimportlib.util経由でロード（train_v2_4h.pyと同一方式）
- output/ディレクトリがなければ mkdir -p で作成すること
- MVP原則: S1は骨格・読込・特徴量・モデルロードのみ。それ以外は追加禁止
