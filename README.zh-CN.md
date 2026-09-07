# Wordflow — 在终端里练习英文打字

**用自己的文本，逐词练习英文拼写与键盘输入。**

Wordflow 是一个安静、离线的终端练习工具，适合在工作间隙花几分钟使用。粘贴一段想练习的英文，跟着高亮逐词输入，完成后随时重练。

无需账号或浏览器，没有计时排名。文章与完成记录保存在自己的电脑上。

[English](README.md) · [反馈问题](https://github.com/KaiXinChaoRen1/wordflow/issues/new?template=bug_report.md)

![拼写练习界面：高亮当前单词和已经输入的字母](docs/images/practice.svg)

## 适合怎样的练习？

如果你每天都在使用键盘，希望英文输入更熟练，可以把学习笔记、日常写作中的句子或正在阅读的段落放进来练习。

- **练自己的内容**：不局限于固定词库。
- **逐字反馈**：输入正确时推进高亮，输入错误时提示下一个字母；不区分大小写。
- **界面低干扰**：低对比度、键盘快捷键、无声音，适合短时间练习。
- **方便重复**：完成后显示 `Good`，按 `r` 立即重练；每条内容用三个圆点记录最多三次完成。
- **数据留在本地**：使用 JSON 文件，不依赖账号或云同步，应用内无遥测。

这是看着原文进行的跟打与拼写练习；目前不提供打字速度评分、发音训练或记忆复习计划。

## 安装与启动

需要 **Python 3.9+**、Git 和终端。安装依赖时需要网络，安装完成后可离线练习。

### macOS / Linux

```bash
git clone https://github.com/KaiXinChaoRen1/wordflow.git
cd wordflow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
wordflow
```

### Windows（PowerShell）

```powershell
git clone https://github.com/KaiXinChaoRen1/wordflow.git
cd wordflow
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\wordflow.exe
```

以后在仓库目录中执行 `.venv/bin/wordflow`（macOS/Linux）或 `.\.venv\Scripts\wordflow.exe`（Windows）即可启动。Windows 无需激活虚拟环境或修改 PowerShell 执行策略。

## 第一次练习

1. 点击 `+article` 或按 `Ctrl+N` 新建文章。
2. 填写标题，粘贴一小段英文；分组可选。
3. 按 `Ctrl+S` 保存，再按 `Ctrl+R` 开始。
4. 输入高亮的单词。词间空格自动处理，词内的撇号和连字符需要输入。
5. 完成后按 `r` 重练，其他任意键返回；练习中按 `Esc` 退出，不计为完成。

可以直接使用这段原创示例：

> A short break can be a chance to learn. Write one sentence at a time. Small steps make practice easier.

首次启动时列表为空。仓库还提供了[两段示例文本](examples/articles.json)，可以通过下方的数据路径设置独立试用。

## 管理内容

![文章列表：分组、完成标记和逐句预览](docs/images/library.svg)

- **article**：按句末标点和换行切分文章。切分规则较简单，缩写可能需要手动调整。
- **memo**：按非空行练习笔记。
- 上下方向键预览文章，`Enter` 开始练习；在分组标题上按 `Enter` 展开或收起分组。点击文章也会开始练习。
- 长标题可横向滚动查看；预览显示完成标记，正文按练习界面相同的分句换行。

| 快捷键 | 主界面操作 |
| --- | --- |
| `Ctrl+N` | 新建文章 |
| `Ctrl+S` | 保存编辑 |
| `Ctrl+R` | 练习选中的已保存内容 |
| 连按两次 `Ctrl+D` | 删除选中内容 |
| `Ctrl+T` | 切换 article / memo |

切换文章或开始练习前请先保存，当前没有自动保存。练习识别英文字母及词内撇号、连字符，不要求输入数字和其他标点。

## 本地数据

默认文件为 `~/.wordflow/articles.json`，`~` 表示用户主目录。点击 `config` 查看实际路径，旧安装可能沿用 `~/.spelllane/articles.json`。

在仓库目录使用独立示例文件，不替换自己的文章库：

```bash
WORDFLOW_DATA_PATH=examples/articles.json .venv/bin/wordflow
```

Windows PowerShell：

```powershell
$env:WORDFLOW_DATA_PATH = "examples/articles.json"
.\.venv\Scripts\wordflow.exe
Remove-Item Env:WORDFLOW_DATA_PATH
```

练习会更新所选文件中的完成次数，包括示例文件。手动导入或备份时，先关闭程序，再复制或编辑 `config` 显示的 JSON 文件；替换前保留原文件备份。当前没有合并导入向导。

完整字段和自定义分句见[数据格式说明](docs/data-format.md)。

## 开发与打包

```bash
python -m pip install -e ".[dev]"
pytest -q
PYTHONPATH=src python3 -m compileall -q src tests
```

macOS/Linux 可在激活虚拟环境后用 `./run-dev.sh` 从源码启动。维护者主要在 macOS 上开发；Windows/Linux 打包脚本需要在对应平台构建和验证。详见[贡献指南](CONTRIBUTING.md)与[打包说明](docs/building.md)。

## 帮助项目变得更好用

如果它适合你的日常练习，欢迎点 Star 收藏。更欢迎反馈安装障碍、终端兼容问题，以及真实使用中不顺手的地方。[Issue](https://github.com/KaiXinChaoRen1/wordflow/issues) 支持中文或英文，也欢迎小而明确的 Pull Request。

采用 [MIT 许可证](LICENSE)，基于 [Textual](https://github.com/Textualize/textual) 构建。
