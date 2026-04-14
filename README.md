# Wordflow

`Wordflow` 是一个基于 `Python + Textual` 的终端英语拼写训练器。

## 项目愿景

我们对这个项目的期待很明确：  
未来英语能力不只是“会说”，更是“会写”。而在今天，“写”已经越来越不是靠纸笔，而是靠键盘输入。

`Wordflow` 想做的是一个小而美、低干扰、可长期使用的键盘英语训练工具：

- 摸鱼场景可用：界面低调，远看像普通终端工作界面
- 拼写练习可持续：用真实内容反复训练，而不是一次性刷题
- 反应能力可锻炼：按单词逐字推进，强化拼写与键盘反应

它不追求功能堆砌，只追求稳定、顺手、长期可用。

## 当前功能

- **双内容模式**
  - `Article`：按句子切分后练习
  - `Memo`：按行切分后练习
- **主界面布局**
  - 左侧：内容列表（支持 `Article / Memo` 过滤）
  - 右侧：标题与正文编辑、状态提示
  - 底部：固定动作栏（`New A / New M / Save / Run / Del / Config / Cancel`）
- **练习模式**
  - 按当前单词逐字输入
  - 空格自动处理
  - 已完成单词与当前进度实时反馈
- **导入/导出思路（轻实现）**
  - 在 `Config` 中查看当前数据文件路径
  - 直接编辑该 JSON 文件即可导入或替换内容

## 为什么这样设计

`Wordflow` 优先服务的是“真实办公环境下的长期训练”：

- 打开快、干扰低，不需要复杂准备
- 数据结构直接、可控，不绑平台
- 行为可预期，宁可简化功能，也不引入复杂错误

## 安装与运行

```bash
cd /Users/lwq/workspace/spelllane
python3 -m pip install --user .
wordflow
```

本地开发可直接运行：

```bash
cd /Users/lwq/workspace/spelllane
./run-dev.sh
```

## 数据存储

默认数据路径：

```bash
~/.wordflow/articles.json
```

兼容旧路径：

```bash
~/.spelllane/articles.json
```

每条记录使用统一 JSON 结构（示例）：

```json
[
  {
    "article_id": "uuid",
    "title": "title",
    "body": "raw text",
    "mode": "article",
    "sentences": ["segment 1", "segment 2"]
  }
]
```

> `mode` 支持 `article` 和 `note`（UI 中显示为 Memo）。

## 测试

```bash
pytest -q
```

## Windows 单文件打包

Windows `.exe` 需要在 Windows 环境中构建。PowerShell 中执行：

```powershell
cd path\to\spelllane
.\scripts\build-windows.cmd
```

生成文件：

```text
dist\windows\wordflow.exe
```

把 `wordflow.exe` 放到例如 `C:\Tools\wordflow\wordflow.exe`，并把目录加入 `PATH`：

```powershell
setx PATH "$env:PATH;C:\Tools\wordflow"
```

重新打开终端后执行：

```powershell
wordflow
```
