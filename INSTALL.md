# 安装与协作手册

> 面向第一次接触本仓库的同事：从零装好环境、把 GateFix 接到自己的 agent 环境、以及怎么提交新项目的尽调证据。
> 判定机制（4D-CQ 打分、四态路由、落地等级 L0–L3）见 [README.md](README.md)。

## 一、环境要求

- Python 3.10+
- 依赖见 `requirements.txt`：核心只有 `pyyaml`；跑 MCP server 才需要 `mcp==1.23.1`；`pytest` 用于跑测试。

## 二、从零安装

```bash
git clone <仓库地址> gatefix-ai-investment
cd gatefix-ai-investment
pip install -r requirements.txt
```

验证装好：

```bash
python engine.py run --case=ai_investment   # 应打印两道闸门的判定结果
pytest -v                                   # 回归测试全绿
```

## 三、三种调用方式

### 方式一：命令行（最简单，零集成）

```bash
python engine.py run --case=ai_investment
python engine.py run --case=ai_investment --verbose
```

### 方式二：作为 MCP server 接入任意 MCP client

```bash
python mcp_server/server.py    # stdio 传输
```

任何 MCP client（Claude Desktop 等）配一个 stdio server：`command` 指向本机 `python3`，`args` 为 `mcp_server/server.py`，工作目录设为本仓库根目录。暴露三个工具：`list_precondition_functions` / `authorize` / `gate_history_get`。

### 方式三：接入 DeepSeek Harness（团队推荐）

编辑 `~/.dsh/profiles/web/cordis.patch.yml`，加一段（把 `cwd` 换成你 clone 的目录）：

```yaml
- insert:
    - id: mcp-gatefix
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: gatefix
        transport: stdio
        command: python3
        args: [mcp_server/server.py]
        cwd: '/你的路径/gatefix-ai-investment'
```

重启 `dsh web` 后，模型会看到三个原生工具：`mcp__gatefix__list_precondition_functions`、`mcp__gatefix__authorize`、`mcp__gatefix__gate_history_get`。

> 提示：若工具没注册（子进程 spawn 失败），把 `command` 换成本机 python3 的绝对路径（`which python3` 查），最稳。

## 四、新增一个项目怎么用

判断一个新项目，引擎按 `--case` 动态加载，核心代码零改动：

1. 复制 `evidence/TEMPLATE_evidence.yaml` 为 `evidence/<项目名>_evidence.yaml`，按尽调情况填字段；
2. 默认复用 `ai_investment` 的闸门定义（`commits/` 与 `preconditions/` 不用动）；
3. 只有判断标准确实不同时，才需要新增 `preconditions/<项目名>.py`（可选 `commits/<项目名>_commits.yaml`）。

字段清单见 `evidence/TEMPLATE_evidence.yaml` 的注释（治理 6 项 + 落地 5 项，各有一条红线）。

## 五、证据提交与协作

- **结构化提交**：把填好的 `evidence/<项目名>_evidence.yaml` 提交进仓库——git 历史即审计轨迹。
- **非结构化材料**：尽调 PDF/文档放共享目录，在 agent 会话里让它读材料、填字段、跑判定。
- **判定记录**：`authorize` 每次调用会追加一条记录到 `gate_audit_log.jsonl`（已 gitignore，不入库），可用 `gate_history_get` 复盘"当初为什么放行/拦截"。

## 六、核心契约（务必遵守）

`authorize` 返回的 `route`/`gate_state != "PASS"` 时，绝不能把对应的投资动作当作已授权去执行。闸门只判"证据够不够格"，不判"证据真伪"——证据真实性归取证层（人工尽调、第三方核查）。

## 七、常见问题

- **MCP 工具没出现**：先确认 `python mcp_server/server.py` 能独立跑起来；再检查 `command` 路径（绝对路径最稳）。
- **`route=ESCALATE` 是不是"项目不行"**：不是。ESCALATE 表示证据缺口不能自动闭合、转人工终审；补齐证据后重跑即可。
- **想换判断标准**：见第四节，新增 `preconditions/<项目名>.py`。
