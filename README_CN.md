# ls-cx-ss

[English](./README.md) | 中文

`ls-cx-ss` 是一个给 Codex CLI 用户用的小型本地工具。

它主要补当前 `codex resume` 的几个空缺：

- 列出当前工作目录下的 session
- 把不同 provider 的 session 放在一起看
- 展示 `Provider` 和 `SessionID`
- 提供一个轻量 TUI 选择器
- 直接执行 `codex resume <SESSION_ID>`

## 本地开发

```bash
python3 -m ls_cx_ss list
python3 -m ls_cx_ss tui
python3 -m ls_cx_ss resume <SESSION_ID>
```

包入口和 GitHub Pages 单文件入口都兼容 Python 3.6+。

## 开发结构

现在唯一的源码来源在 `ls_cx_ss/`。

- `ls_cx_ss/`: 开发时维护的包式源码模块
- `docs/ls-cx-ss.py`: 通过 GitHub Pages 发布的单文件产物

Pages 单文件产物由下面这条命令从包源码生成：

```bash
python3 scripts/build_single_file.py
```

当前生成器采用一个很小的 loader 方案：

- 读取 `ls_cx_ss/` 下每个模块源码
- 把这些模块源码作为字符串嵌进一个单文件
- 启动时把它们装进 `sys.modules`
- 最后调用 `ls_cx_ss.cli.main()`

所以如果你要改行为，先改 `ls_cx_ss/`，再重新生成 `docs/ls-cx-ss.py`。除非你是在调试生成器本身，否则不要手改 `docs/ls-cx-ss.py`。

## GitHub Pages 直接使用

项目支持通过 GitHub Pages 分发，所以也可以直接从 URL 运行：

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 -
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - list
curl -fsSL https://lxchx.github.io/ls-cx-ss/ls-cx-ss.py | python3 - tui
```

如果不带子命令，现在默认会进入 TUI。`-h` / `--help` 仍然显示帮助。
在 TUI 里：

- `s`: 切换排序列
- `r`: 切换升序 / 降序
- `i`: 把最新 Pages 版本安装到 `~/.local/bin/ls-cx-ss`
- `u`: 检查是否有更新

如果要直接从 URL 安装，使用同站点托管的安装脚本：

```bash
curl -fsSL https://lxchx.github.io/ls-cx-ss/install.py | python3 -
~/.local/bin/ls-cx-ss list
```

## 已安装命令

如果你已经装到本地，命令入口仍然是：

```bash
ls-cx-ss list
ls-cx-ss tui
ls-cx-ss resume <SESSION_ID>
```

## TUI 快捷键

- `Up/Down` 或 `j/k`: 移动
- `PageUp/PageDown`: 翻页
- `Home/End`: 跳到首尾
- `/`: 搜索
- `s`: 切换排序键
- `r`: 切换倒序
- `i`: 安装到本地 `~/.local/bin/ls-cx-ss`
- `u`: 检查 GitHub Pages 上是否有更新
- `Enter`: 恢复选中的 session
- `q` 或 `Esc`: 退出
