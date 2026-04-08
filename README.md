# Wordflow

`Wordflow` 是一个用 `Python + Textual` 编写的终端拼写训练器。

你可以录入英文文章，程序会自动切分句子，然后按句子逐词训练拼写。训练时会显示整句原文，你需要从左到右输入当前单词；输入正确后，当前词会变绿，随后进入下一个词。整篇文章完成后，程序会输出中文鼓励和颜文字。

## 功能

- 录入文章标题和正文
- 自动按英文标点和换行切句
- 文章列表选择和删除
- 逐句逐词拼写训练
- 词级高亮反馈
- 训练完成鼓励语

## 安装

```bash
cd /Users/lwq/workspace/spelllane
python3 -m pip install --user .
wordflow
```

如果你已经像 `hn` 一样把 `~/.local/bin` 放进了 `PATH`，安装后就可以在任何目录直接运行 `wordflow`。

如果还没有生效，可以先检查：

```bash
echo $PATH
which wordflow
```

## 开发模式

如果你希望每次改完代码，重新启动终端程序就直接看到最新效果，不要用普通安装的 `wordflow`，因为它运行的是安装到 Python 环境里的副本。

推荐两种方式：

```bash
cd /Users/lwq/workspace/spelllane
python3 -m pip install --user -e .
wordflow
```

或者直接运行仓库里的开发启动脚本，或者你本机上的短命令 `wf`：

```bash
cd /Users/lwq/workspace/spelllane
./run-dev.sh
wf
```

`./run-dev.sh` 会直接从当前仓库的 `src/` 目录启动，所以你每次改完代码后，只要重新执行一次它，就会看到最新改动。

## 使用

启动后主界面分为左右两栏：

- 左边是文章列表
- 右边可以编辑标题和正文

常见流程：

1. 输入标题和英文正文
2. 点 `Save Article`
3. 在左侧选择文章
4. 点 `Start Practice`
5. 按顺序输入当前句子最左边的单词

训练规则：

- 默认忽略大小写
- 不要求输入句中标点
- 保留 `'` 和 `-` 作为单词的一部分

数据默认保存在用户目录下的 `~/.wordflow/articles.json`。
如果检测到旧版 `~/.spelllane/articles.json`，程序会自动兼容读取。
如果当前环境不允许写入用户目录，程序会自动回退到当前工作目录下的 `.wordflow/articles.json`。
