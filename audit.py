"""
audit.py —— 门控判定的 append-only 审计记录。

只用标准库（json/pathlib/datetime），不引入新依赖——和 gate.py/engine.py
的"核心零重依赖"是同一个原则。存储选 JSONL 而不是 SQLite：
这个仓库已经在用 JSONL 记录 gate_record.jsonl，同一种格式，不多引入一种
存储机制；轻量、可 grep、可被任何语言读。

和 engine.py 已有的 gate_record.jsonl 是两回事，不是同一个文件的修复：
gate_record.jsonl 是"最近一次 run 的快照"（tests/test_engine.py 依赖它
每次 run 都恰好是本次这批 commit 的结果，所以那个文件继续保持覆盖写）；
这里的审计日志才是真正的历史留痕，append-only，从不覆盖、从不原地改写。

诚实的失败语义：append_gate_decision() 从不抛异常——审计写入
失败时返回 AuditWriteResult(ok=False, ...)，调用方要把"这个动作本身的
判定结果"和"这次判定有没有被成功记下来"当成两件事分别报告，不能因为
审计写失败就回滚已经生效的判定，也不能假装审计成功了。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_AUDIT_LOG = Path(__file__).parent / "gate_audit_log.jsonl"


@dataclass
class AuditWriteResult:
    ok: bool
    error: Optional[str] = None


def build_audit_record(*, action_id: str, gate_state: str, reason_code: str,
                        cq_scores: dict, schema_version: str,
                        thresholds: Optional[dict] = None,
                        case: str = "") -> dict:
    """审计记录字段：时间戳、动作标识、输入的 cq_scores、
    命中的阈值、输出的 gate_state、reason_code、schema_version。故意不收
    human_readable/notes 这类自由文本字段（敏感物纪律）——最强的
    脱敏就是压根不存来路不明的自由文本，比"存了再脱敏"更彻底。需要人看的
    说明走 GateResult/GateRecord.to_contract() 的 human_readable，那条路径
    经过 gate.py::redact_secrets() 脱敏。"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_id": action_id,
        "case": case,
        "cq_scores": dict(cq_scores),
        "thresholds": dict(thresholds) if thresholds else {},
        "gate_state": gate_state,
        "reason_code": reason_code,
        "schema_version": schema_version,
    }


def append_gate_decision(record: dict, path: Path = DEFAULT_AUDIT_LOG) -> AuditWriteResult:
    """只以追加模式打开文件——这个模块里没有任何地方会截断/覆盖这个文件。
    捕获 OSError（磁盘满、权限问题等），不让审计层的故障波及调用方已经
    做出的判定。"""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return AuditWriteResult(ok=True)
    except OSError as exc:
        return AuditWriteResult(ok=False, error=f"{type(exc).__name__}: {exc}")


def query_gate_decisions(path: Path = DEFAULT_AUDIT_LOG, *,
                          action_id: Optional[str] = None,
                          gate_state: Optional[str] = None,
                          since: Optional[str] = None,
                          until: Optional[str] = None) -> "list[dict]":
    """只读查询——这个函数从不打开文件写模式，也不删除/改写任何一行。
    日志文件还不存在时返回空列表，查一个还没产生过判定的审计记录不是
    错误。since/until 按 ISO-8601 时间戳字符串比较（datetime.isoformat()
    产出的格式本身是可字典序比较的）。"""
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if action_id is not None and rec.get("action_id") != action_id:
                continue
            if gate_state is not None and rec.get("gate_state") != gate_state:
                continue
            if since is not None and rec.get("timestamp", "") < since:
                continue
            if until is not None and rec.get("timestamp", "") > until:
                continue
            out.append(rec)
    return out
