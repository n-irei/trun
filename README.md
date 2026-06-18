# trun — Task Runner for AI Agents

inotifywait + `claude -p` によるタスク自動実行エンジン。
タスクファイルを `input/` に置くだけで、AIエージェントが自動実行する。

## 特徴

- **ゼロコピペ**: ファイル配置→自動検知→実行→結果保存。手作業なし
- **YAMLフロントマター**: `model` / `effort` をタスクごとに指定
- **ライフサイクル管理**: input/ → running/ → done/ | failed/
- **ログ**: task_runner.log に全実行記録

## セットアップ

```bash
# 前提: Claude Code CLI がインストール済みであること
# https://docs.anthropic.com/en/docs/claude-code

# inotify-tools
sudo apt install -y inotify-tools

# alias登録
echo 'alias trun="bash /home/$USER/trun/task_runner.sh"' >> ~/.bashrc
source ~/.bashrc
```

## 使い方

```bash
# 監視起動（別ターミナル）
trun

# タスクファイルを配置 → 自動実行される
cp _template.md input/my_task.md
# my_task.md を編集してinput/に保存
```

## タスクファイル形式

```markdown
---
model: sonnet
effort: high
---
# タスク名

## 目的
やりたいこと

## 作業
- 手順1
- 手順2

## 完了条件
- [ ] 検証方法
```

### フロントマター（オプション）

| キー | デフォルト | 値の例 |
|---|---|---|
| model | sonnet | haiku, sonnet, opus |
| effort | high | low, medium, high |

## ディレクトリ構造

```
trun/
├── task_runner.sh    # メインスクリプト
├── input/            # タスク投入先
│   ├── _template.md  # テンプレート
│   ├── running/      # 実行中
│   ├── done/         # 完了
│   └── failed/       # 失敗
├── output/           # 実行結果
└── task_runner.log   # ログ
```

## 関連

- [Compact — AIエージェント協働OS](https://github.com/n-irei/agent_config) : ルール・知識・状態管理フレームワーク。trunはCompactのタスク実行エンジンとして機能する。

## License

MIT
