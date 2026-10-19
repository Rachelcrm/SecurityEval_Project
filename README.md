# SecurityEval_Project

AI information security course project — Ruimeng Chen, Shuqi Zhong, Jiayi Li.

我们先比较 **Bandit → 加入自定义 AST 规则 → 加入功能/安全动态测试** 的检测效果，
之后在检测流程可靠的前提下研究 LLM 修复。第一周不实现自动修复。

## 当前状态

- 已实现：Python 3.11 框架、3 个可追溯的 SecurityEval 改编样例、统一 JSON Schema、
  Member 1 的 OpenAI Responses API 生成与留档、离线测试和三位成员的接入入口。
- 尚未运行：真实 LLM 生成（模型和 API Key 尚未配置）。
- 尚未实现：Bandit/AST 检测、Docker 执行器及样例功能/安全测试。适配器返回 `not_run`。
- `pytest` 默认仅验证框架，**不代表生成代码通过功能或安全测试**。
  `generated` 仅代表收到完整响应、Python 语法可解析且含预期入口，不代表代码正确或安全。

## 快速开始（从仓库根目录执行）

需要 Python **3.11.x**。不要使用 Mac 自带的 Python 3.9。已为当前电脑创建的 `.venv` 可直接激活；
其他成员先安装 Python 3.11，再运行：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m pytest -q
security-eval samples
```

`requirements.txt` 固定本次已验证的依赖版本；`pyproject.toml` 定义包、Python 版本和扩展依赖。
不要提交 `.venv`、API Key、原始下载缓存或未审核的实验产物。

Mac 上 `code .` 不可用时，可直接执行：

```bash
"/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" .
```

要让 `code .` 长期可用，在 VS Code 命令面板中运行
`Shell Command: Install 'code' command in PATH`，然后重新打开终端。

## 三个样例与固定接口

| sample_id | 上游真实 ID | 改编后入口 | 主要改动 |
|---|---|---|---|
| `sql_delete_user` | `CWE-089_author_1.py` | `remove_user(conn, username) -> int` | MySQL → 内存 SQLite；连接由调用者提供 |
| `command_allowlist` | `CWE-078_author_1.py` | `execute_command(command) -> str` | input → 参数；限定 pwd/echo 命令与错误行为 |
| `path_read_file` | `CWE-022_codeql_1.py` | `read_file(base_dir, filename) -> bytes` | Flask → 函数；明确目录边界和异常 |

`data/samples.jsonl` 保存原始 prompt、改编 prompt、逐项修改、选择理由、功能/安全要求、
上游 commit 与 SHA-256。原始 prompt 从真实文件提取，没有编造 ID 或把自写代码标成上游数据。
**这些 prompt 加入了明确安全要求，属于改编实验，不能直接报告为原始 SecurityEval benchmark 分数。**
CWE 是上游样例类别，不代表某次生成一定有该漏洞。

来源：[s2e-lab/SecurityEval](https://github.com/s2e-lab/SecurityEval)，固定版本
`6f4fb70f782c6d47b02ea24341e8ef8c1eb04a6a`。
复核原始 prompt（联网下载一次，随后可离线验证）：

```bash
python scripts/verify_source.py --download
python scripts/verify_source.py
```

该版本未找到独立 LICENSE 文件；保留上游引用，不为上游数据擅自添加许可证。
论文：Mohammed Latif Siddiq and Joanna C. S. Santos, *SecurityEval Dataset: Mining Vulnerability
Examples to Evaluate Machine Learning-Based Code Generation Techniques*, MSR4P&S 2022.
[DOI](https://doi.org/10.1145/3549035.3561184)。

## Member 1：生成与记录

先进行不联网、不收费、不会生成 `code.py` 的准备：

```bash
security-eval generate sql_delete_user \
  --model gpt-5.4-mini-2026-03-17 --reasoning-effort none \
  --dry-run --out artifacts/sql-prepared-001
```

模型只是示例，可换成账号实际可用的 Responses API 模型；代码没有偷偷指定默认模型。
建议第一轮三份代码固定同一模型版本、prompt 和预算。先保存初始结果，再检查，不反复挑选最理想输出。

真实调用需要本地 `OPENAI_API_KEY`。在终端中隐藏输入（不会写入命令历史中的明文）：

```bash
read -s "OPENAI_API_KEY?OpenAI API key: "
export OPENAI_API_KEY
printf '\n'
security-eval generate sql_delete_user \
  --model gpt-5.4-mini-2026-03-17 --reasoning-effort none \
  --max-output-tokens 4096 --out artifacts/sql-live-001
unset OPENAI_API_KEY
```

上述隐藏输入语法用于 Mac 默认 zsh；bash 可用 `read -s -p 'OpenAI API key: ' OPENAI_API_KEY`。
`.env.example` 仅用于说明变量，程序不会自动加载 `.env`。
另外两个样例替换 sample_id 并使用不同的输出目录。可通过 `OPENAI_MODEL` 代替 `--model`。
`--temperature` 默认不发送，避免对不支持该参数的模型作错误假设；只有确认支持时才设置。
默认超时 90 秒、无自动重试，避免隐藏的额外调用。

每次调用保存：`sample.json`、`request.json`、`generation.json`；收到响应后保存
`response.json` 和 `completion.txt`，可提取时保存 `code.py`。
记录包含请求/代码哈希、请求与返回模型、时间、response ID、usage 和失败状态。
现有目录拒绝覆盖。输出截断、拒绝、空输出、语法错误均不会标为成功。
代码只做语法解析，**不会被导入或执行**。真实实验产物默认被 Git 忽略；审核后再按需归档。

API 依据：[Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)。

## 接入检测

```bash
security-eval evaluate artifacts/sql-live-001 --out artifacts/sql-analysis-001
security-eval validate analysis artifacts/sql-analysis-001/bandit.json
```

当前三个适配器都输出 `not_run`，因此 `evaluate` 返回非零退出码。
它验证候选代码哈希，防止三种检测使用不同版本；不会执行候选代码。
实现后的分析结果须通过 [统一接口说明](docs/INTERFACES.md) 的 Schema 校验。
没有 findings 不自动等于安全；工具未运行、执行失败和已执行无告警必须区分。

## 三人分工与避免合并冲突

| 成员 | 主要负责路径 | 交付 |
|---|---|---|
| Member 1 / Shuqi | `data/`、`generation.py`、`scripts/verify_source.py` | 3 份真实生成代码与请求/响应记录 |
| Member 2 | `analyzers/static.py`、新增规则模块和规则单测 | Bandit + 1–2 条 AST 规则，真实 JSON 结果 |
| Member 3 | `analyzers/dynamic.py`、`tests/candidates/`、`docker/` | 隔离执行、正常/恶意输入测试与证据 |

完整交接：[docs/INTERFACES.md](docs/INTERFACES.md)。先跑通 `sql_delete_user`，然后扩展其他两个样例。
共享 Schema 和函数签名变更先在小组确认，避免各自重建框架。

两位同学在框架推送后，从同一个 `main` 拉取并各开一个分支：

```bash
git switch main
git pull --ff-only origin main
git switch -c member2-static  # Member 3 改为 member3-dynamic
```

提交前运行框架测试和自己模块的真实测试；分别提交 PR 到 main。
不要提交 API Key、把本地 `.venv` 推到仓库，或用占位通过结果制作汇报结论。
周五演示只报告已实际完成且有证据的步骤。
