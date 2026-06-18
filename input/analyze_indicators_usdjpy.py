#!/usr/bin/env python3
"""
USDJPY 1h足 インジケーター条件別 統計・確率的エッジ検証

検証指標:
  1. MA240/MA80/MA20 アライメント（トレンド方向）
  2. RSI + RSI-MA9 クロス
  3. ZigZag トレンド（HH-HL / LH-LL）
  4. ダウ理論（MA240>MA80 × ZZトレンド）

各条件ごとに:
  - 5h先騰落（HORIZON_H=5）の勝率・期待値
  - 二項検定 p値（H0: 勝率=50%）
  - Kelly f*
  - サンプル数
"""
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

DATA_PATH  = Path("/mnt/c/Users/pcuser/Documents/MyVault/quant_lab/data/USDJPY60.csv")
OUTPUT_DIR = Path("/mnt/c/Users/pcuser/Documents/MyVault/AgentWorkspace/output")
HORIZON_H  = 5
ZZ_DEPTH         = 12
ZZ_DEVIATION_PTS = 0.005

# ── データロード ──────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, header=None,
                     names=["date","time","open","high","low","close","volume"])
    df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M")
    df = df.drop(columns=["date","time"]).set_index("datetime")
    df.index = df.index.tz_localize("UTC")
    return df.sort_index().astype(float)

# ── インジケーター計算 ─────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # MA
    df["ma20"]  = df["close"].rolling(20).mean()
    df["ma80"]  = df["close"].rolling(80).mean()
    df["ma240"] = df["close"].rolling(240).mean()

    # MA alignment
    def _align(row):
        if any(pd.isna([row.ma20, row.ma80, row.ma240])):
            return np.nan
        if row.ma20 > row.ma80 > row.ma240:
            return 1   # 完全上昇アライメント
        elif row.ma20 < row.ma80 < row.ma240:
            return -1  # 完全下降アライメント
        else:
            return 0   # 混在
    df["ma_alignment"] = df.apply(_align, axis=1)

    # RSI-14
    delta = df["close"].diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = (-delta).where(delta < 0, 0.0)
    ag    = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    al    = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df["rsi14"] = 100 - (100 / (1 + ag / al))

    # RSI MA9
    df["rsi_ma9"] = df["rsi14"].rolling(9).mean()

    # RSI-MA クロス方向
    df["rsi_cross"] = np.where(
        df["rsi14"] > df["rsi_ma9"],  1,   # RSIがMAを上回り（上昇モメンタム）
        np.where(df["rsi14"] < df["rsi_ma9"], -1, 0)
    )

    # 5h先終値 → ターゲット（BUY視点: 上昇=1、下落=0）
    df["future_close"] = df["close"].shift(-HORIZON_H)
    df["target_buy"]   = (df["future_close"] > df["close"]).astype(float)
    df["target_sell"]  = (df["future_close"] < df["close"]).astype(float)
    df.loc[df["future_close"].isna(), ["target_buy","target_sell"]] = np.nan

    return df


# ── ZigZag ───────────────────────────────────────────────────

def detect_zigzag(df: pd.DataFrame):
    highs = df["high"].values
    lows  = df["low"].values
    n     = len(df)
    idx   = df.index
    peak_price   = np.full(n, np.nan)
    bottom_price = np.full(n, np.nan)
    depth = ZZ_DEPTH
    deviation_pts = ZZ_DEVIATION_PTS
    for i in range(depth, n - depth):
        wh = highs[i - depth: i + depth + 1]
        wl = lows[i - depth: i + depth + 1]
        if highs[i] == np.max(wh):
            peak_price[i] = highs[i]
        if lows[i] == np.min(wl):
            bottom_price[i] = lows[i]
    peaks   = {}
    bottoms = {}
    last_peak = last_bottom = None
    for i in range(n):
        if not np.isnan(peak_price[i]):
            p = peak_price[i]
            if last_peak is None or abs(p - last_peak) >= deviation_pts:
                peaks[idx[i]] = p
                last_peak = p
        if not np.isnan(bottom_price[i]):
            b = bottom_price[i]
            if last_bottom is None or abs(b - last_bottom) >= deviation_pts:
                bottoms[idx[i]] = b
                last_bottom = b
    return peaks, bottoms


def add_zz_trend(df: pd.DataFrame, peaks: dict, bottoms: dict) -> pd.DataFrame:
    """各時刻での直近ZZトレンド方向を付与（ベクトル化・O(n)）"""
    df = df.copy()
    sorted_peaks   = sorted(peaks.items())   # (ts, price)
    sorted_bottoms = sorted(bottoms.items())

    n = len(df)
    zz_trend  = np.full(n, np.nan)
    dow_trend = np.full(n, np.nan)

    # ピーク・ボトムの最新2つをスライド更新
    pp_idx = pb_idx = 0
    prev_p = curr_p = prev_b = curr_b = None
    ts_index = df.index

    for i in range(n):
        if i % 100000 == 0:
            print(f"  ZZ/Dow progress: {i}/{n}")
        t = ts_index[i]
        # 現在時刻までのピーク/ボトムを進める
        while pp_idx < len(sorted_peaks) and sorted_peaks[pp_idx][0] < t:
            prev_p = curr_p
            curr_p = sorted_peaks[pp_idx][1]
            pp_idx += 1
        while pb_idx < len(sorted_bottoms) and sorted_bottoms[pb_idx][0] < t:
            prev_b = curr_b
            curr_b = sorted_bottoms[pb_idx][1]
            pb_idx += 1

        if prev_p is None or prev_b is None:
            continue

        # ZZトレンド
        if curr_p > prev_p and curr_b > prev_b:
            zz_trend[i] = 1
        elif curr_p < prev_p and curr_b < prev_b:
            zz_trend[i] = -1
        else:
            zz_trend[i] = 0

        # ダウ理論: MA240/MA80 確認
        ma240 = df["ma240"].iat[i]
        ma80  = df["ma80"].iat[i]
        if pd.isna(ma240) or pd.isna(ma80):
            continue
        if ma240 > ma80 and curr_p > prev_p:
            dow_trend[i] = 1
        elif ma240 < ma80 and curr_b < prev_b:
            dow_trend[i] = -1
        else:
            dow_trend[i] = 0

    df["zz_trend"]  = zz_trend
    df["dow_trend"] = dow_trend
    return df


# ── 統計検定 ─────────────────────────────────────────────────

def binom_test(wins: int, n: int) -> float:
    """二項検定 p値（両側, H0: p=0.5）"""
    result = stats.binomtest(wins, n, p=0.5, alternative='two-sided')
    return result.pvalue


def kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return np.nan
    b = avg_win / avg_loss
    return win_rate - (1 - win_rate) / b


def analyze_condition(df_sub: pd.DataFrame, direction: str, label: str) -> dict:
    """条件を満たす行のターゲット統計を返す"""
    target_col = f"target_{direction}"
    s = df_sub[target_col].dropna()
    n = len(s)
    if n < 20:
        return {"label": label, "direction": direction, "n": n,
                "win_rate": np.nan, "p_value": np.nan, "kelly": np.nan, "note": "サンプル不足"}
    wins    = int(s.sum())
    wr      = wins / n
    p_val   = binom_test(wins, n)
    # pips代替: close変化（×100でpips近似）
    if direction == "buy":
        pips = (df_sub["future_close"] - df_sub["close"]).dropna() * 100
    else:
        pips = (df_sub["close"] - df_sub["future_close"]).dropna() * 100
    avg_w = pips[pips > 0].mean() if (pips > 0).any() else 0
    avg_l = abs(pips[pips < 0].mean()) if (pips < 0).any() else 0
    k = kelly(wr, avg_w, avg_l)
    return {
        "label":     label,
        "direction": direction,
        "n":         n,
        "win_rate":  wr,
        "p_value":   p_val,
        "kelly":     k,
        "avg_win":   avg_w,
        "avg_loss":  avg_l,
        "note":      "✅ p<0.05" if p_val < 0.05 else ("⚠️ p<0.10" if p_val < 0.10 else "❌ p≥0.10"),
    }


# ── メイン ───────────────────────────────────────────────────

def main():
    print("=== Loading data ===")
    df = load_data()
    print(f"  {len(df)} rows  {df.index.min()} ~ {df.index.max()}")

    print("=== Adding indicators ===")
    df = add_indicators(df)

    print("=== Computing ZigZag ===")
    peaks, bottoms = detect_zigzag(df)
    print(f"  peaks={len(peaks)}  bottoms={len(bottoms)}")

    print("=== Adding ZZ/Dow trend ===")
    df = add_zz_trend(df, peaks, bottoms)

    results = []

    # ── 1. MA Alignment ──────────────────────────────────────
    for align_val, align_name in [(1, "MA上昇アライメント(20>80>240)"), (-1, "MA下降アライメント(20<80<240)")]:
        sub = df[df["ma_alignment"] == align_val]
        direction = "buy" if align_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, f"MA: {align_name}"))
        # 逆張りも検証
        opp = "sell" if align_val == 1 else "buy"
        results.append(analyze_condition(sub, opp, f"MA逆張り: {align_name}→{opp.upper()}"))

    # ── 2. RSI-MAクロス ───────────────────────────────────────
    for cross_val, cross_name in [(1, "RSI>MA9(上昇モメンタム)"), (-1, "RSI<MA9(下降モメンタム)")]:
        sub = df[df["rsi_cross"] == cross_val]
        direction = "buy" if cross_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, f"RSI-MAクロス: {cross_name}"))

    # ── 3. MA Alignment × RSI クロス（複合） ──────────────────
    for align_val, cross_val, label in [
        (1,  1, "MA上昇+RSI上昇モメンタム → BUY"),
        (-1, -1, "MA下降+RSI下降モメンタム → SELL"),
        (1, -1, "MA上昇+RSIクロス下 → BUY逆張り"),
    ]:
        sub = df[(df["ma_alignment"] == align_val) & (df["rsi_cross"] == cross_val)]
        direction = "buy" if align_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, label))

    # ── 4. ZigZag トレンド ────────────────────────────────────
    for zz_val, zz_name in [(1, "ZZトレンド上昇(HH-HL)"), (-1, "ZZトレンド下降(LH-LL)")]:
        sub = df[df["zz_trend"] == zz_val]
        direction = "buy" if zz_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, f"ZZ: {zz_name}"))

    # ── 5. ダウ理論 ───────────────────────────────────────────
    for dow_val, dow_name in [(1, "ダウ上昇(MA240>MA80+ZZピーク更新)"), (-1, "ダウ下降(MA240<MA80+ZZボトム更新)")]:
        sub = df[df["dow_trend"] == dow_val]
        direction = "buy" if dow_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, f"ダウ理論: {dow_name}"))

    # ── 6. ダウ理論 × MA Alignment（完全一致） ────────────────
    for dow_val, align_val, label in [
        (1,  1, "ダウ上昇+MA上昇アライメント → BUY"),
        (-1, -1, "ダウ下降+MA下降アライメント → SELL"),
    ]:
        sub = df[(df["dow_trend"] == dow_val) & (df["ma_alignment"] == align_val)]
        direction = "buy" if dow_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, label))

    # ── 7. ダウ理論 × RSI × ZZ（トリプル複合） ───────────────
    for dow_val, cross_val, zz_val, label in [
        (1,  1,  1, "ダウ上昇+RSI上昇+ZZ上昇 → BUY"),
        (-1, -1, -1, "ダウ下降+RSI下降+ZZ下降 → SELL"),
    ]:
        sub = df[(df["dow_trend"] == dow_val) & (df["rsi_cross"] == cross_val) & (df["zz_trend"] == zz_val)]
        direction = "buy" if dow_val == 1 else "sell"
        results.append(analyze_condition(sub, direction, label))

    # ── レポート出力 ──────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# USDJPY 1h足 インジケーター条件別 統計検証\n",
        f"データ: {DATA_PATH.name}  全{len(df)}本\n",
        f"HORIZON_H={HORIZON_H}h先終値騰落 / 二項検定H0:勝率=50%（両側）\n\n",
        "| 条件 | 方向 | N | 勝率 | p値 | Kelly f* | 判定 |\n",
        "|---|---|---:|---:|---:|---:|---|\n",
    ]
    for r in results:
        if r["n"] < 20:
            lines.append(f"| {r['label']} | {r['direction'].upper()} | {r['n']} | - | - | - | サンプル不足 |\n")
            continue
        lines.append(
            f"| {r['label']} | {r['direction'].upper()} | {r['n']} "
            f"| {r['win_rate']:.1%} | {r['p_value']:.4f} | {r['kelly']:.3f} | {r['note']} |\n"
        )

    # p<0.05の条件を強調
    sig = [r for r in results if r.get("p_value", 1) is not np.nan and not np.isnan(r.get("p_value", 1)) and r.get("p_value", 1) < 0.05]
    lines.append("\n## 統計的有意条件（p<0.05）\n")
    if sig:
        for r in sig:
            lines.append(f"- **{r['label']}** {r['direction'].upper()} N={r['n']} 勝率={r['win_rate']:.1%} p={r['p_value']:.4f} Kelly={r['kelly']:.3f}\n")
    else:
        lines.append("- なし（全条件 p≥0.05）\n")

    lines.append("\n## 考察\n")
    lines.append("- 有意条件があれば: train_1h.pyの特徴量として追加してモデル再訓練\n")
    lines.append("- 全条件p≥0.05の場合: 1h足単体では統計的エッジなし → CPX1(5m+ML)アプローチが優位\n")

    out_path = OUTPUT_DIR / "stat_indicators_usdjpy_out.md"
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"\n=== 出力完了: {out_path} ===")
    print("\n" + "".join(lines[:30]))


if __name__ == "__main__":
    main()
