"""Build the offline Phase 3 task explorer from the checked-in catalogs."""
import json
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "design": ("D", "链路设计", 34),
    "repair": ("R", "故障修复", 33),
    "regression": ("C", "需求变更", 33),
}


def read_catalog(group, prefix, count):
    path = ROOT / "phase3" / group / "catalog.json"
    rows = json.loads(path.read_text())
    expected = {f"{prefix}{number}" for number in range(101, 101 + count)}
    if len(rows) != count or {row["id"] for row in rows} != expected:
        raise ValueError(f"{group} has missing or duplicate tasks")
    if len({row["prompt"] for row in rows}) != count:
        raise ValueError(f"{group} has duplicate prompts")
    for row in rows:
        if not all(row.get(k) for k in ("title", "prompt", "parent", "units", "evidence", "type")):
            raise ValueError(f'{row["id"]} is incomplete')
        if not isinstance(row["units"], dict) or len(row["units"]) < 4:
            raise ValueError(f'{row["id"]} lacks module constraints')
    return sorted(rows, key=lambda row: row["id"])


STAGES = {
    "main": "主场景", "holdout": "留出", "secondary": "留出", "regression": "回归",
    "target": "目标", "initial": "初始", "reference": "参考", "old": "旧需求", "new": "新需求",
}


def load_runs(group):
    base = ROOT / "phase3" / group
    if group == "design":
        report = json.loads((base / "evidence/matrix.json").read_text())
        return {row["id"]: [(stage, run["expected_pass"], run["passed"], run["metrics"])
                            for stage, run in row["runs"].items()] for row in report["tasks"]}
    if group == "regression":
        report = json.loads((base / "evidence.json").read_text())
        return {row["id"]: [(run["stage"], run["expected"], run["passed"], run["metrics"])
                            for run in row["runs"]] for row in report["results"]}
    by_task = {}
    for run in json.loads((base / "evidence/results.json").read_text()):
        stage = f'{run["case"]}-{run["version"]}'
        by_task.setdefault(run["id"], []).append((stage, run["expected_pass"], run["passed"], run))
    return by_task


def run_table(group, rows):
    def flag(value):
        return "通过" if value else "未通过"

    matrices = {
        "design": {"main_initial": False, "main_reference": True, "holdout_initial": False,
                   "holdout_reference": True, "regression_reference": True},
        "repair": {f"{case}-{version}": version == "reference" or case == "regression"
                   for case in ("target", "regression", "holdout") for version in ("initial", "reference")},
        "regression": {f"{case}-{version}-{demand}": (version, demand) != ("initial", "new")
                       for case in ("main", "secondary") for version in ("initial", "reference")
                       for demand in ("old", "new")},
    }
    matrix = matrices[group]
    if len(rows) != len(matrix) or {row[0]: row[1] for row in rows} != matrix:
        raise ValueError(f"Incomplete or unexpected {group} replay matrix")
    html = []
    for stage, expected, actual, metrics in rows:
        if type(actual) is not bool or type(expected) is not bool or expected != actual:
            raise ValueError(f"Unexpected replay outcome in {stage}")
        name = " · ".join(STAGES[token] for token in stage.replace("_", "-").split("-"))
        rate = metrics.get("payload_mbps")
        delay = metrics.get("p95_delay_ms")
        count = metrics.get("received_packets")
        sent = metrics.get("sent_packets")
        cells = [name, flag(expected), flag(actual),
                 "—" if count is None or sent is None else f"{count}/{sent}",
                 "—" if rate is None else f"{rate:.3f}",
                 "—" if delay is None else f"{delay:.2f}"]
        html.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    headers = ["测试条件", "预期", "实测", "收包/发包", "净吞吐（Mbps）", "p95（ms）"]
    head = "".join(f"<th scope='col'>{label}</th>" for label in headers)
    return f'<div class="scroll"><table class="runs"><thead><tr>{head}</tr></thead><tbody>{"".join(html)}</tbody></table></div>'


def task_card(row, group, runs):
    def field(key):
        return escape(str(row[key]))

    units = "".join(f"<tr><th scope='row'>{escape(key)}</th><td>{escape(str(value))}</td></tr>"
                    for key, value in row["units"].items())
    return f"""<details id="{field('id')}" data-group="{group}">
    <summary><code>{field('id')}</code><strong>{field('title')}</strong><span>{field('type')}</span></summary>
    <div class="body"><small>母题 {field('parent')}</small><h3>题干</h3><p>{field('prompt')}</p>
    <h3>逐层测试约束</h3><table><tbody>{units}</tbody></table>
    <h3>重放实测</h3><p>{field('evidence')}</p>{run_table(group, runs)}<a href="../phase3/{group}/README.md">该组复跑说明</a> · <a href="../phase3/{group}/catalog.json">原始题目数据</a></div></details>"""


def main():
    cards = []
    summary = []
    parents = Counter()
    buttons = ['<button type="button" data-group="all" aria-pressed="true">全部</button>']
    for group, (prefix, label, count) in GROUPS.items():
        rows = read_catalog(group, prefix, count)
        buttons.append(f'<button type="button" data-group="{group}" aria-pressed="false">{label} · {count}</button>')
        runs = load_runs(group)
        if set(runs) != {row["id"] for row in rows}:
            raise ValueError(f"{group} evidence and tasks disagree")
        outcomes = [run[2] for stages in runs.values() for run in stages]
        summary.append(f"<tr><th scope='row'>{label}</th><td>{len(rows)}</td><td>{len(outcomes)}</td>"
                       f"<td>{sum(outcomes)}</td><td>{outcomes.count(False)}</td></tr>")
        cards.extend(task_card(row, group, runs[row["id"]]) for row in rows)
        parents.update(str(row["parent"]) for row in rows)
    html = TEMPLATE.replace("{cards}", "\n".join(cards)).replace("{buttons}", "".join(buttons))
    html = html.replace("{summary}", "".join(summary))
    (ROOT / "reports" / "phase-3.html").write_text(html)
    print(f"{len(cards)} tasks from {len(parents)} parent labels")


TEMPLATE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ChiStarlink · 100 道全链路仿真任务</title>
<style>
*{box-sizing:border-box} html{scroll-behavior:smooth}body{margin:0;color:#192e35;background:#f4f6f2;font:16px/1.7 'PingFang SC','Microsoft YaHei',sans-serif}
header{background:#113a42;color:#eff9f4;border-bottom:5px solid #98c897}main,header>div{max-width:1080px;margin:auto;padding:32px 24px}
header>div{padding-top:40px;padding-bottom:36px}header small{color:#a9dad0;letter-spacing:.1em}h1{font-size:clamp(30px,5vw,50px);line-height:1.2;margin:12px 0}header p{max-width:800px;margin-bottom:0}
h2{font-size:24px;margin:22px 0 10px}h3{font-size:16px;color:#244d50;margin:20px 0 4px}p{margin:4px 0 10px}a{color:#13656a}button,input{font:inherit}button{cursor:pointer;border:1px solid #a5bab6;border-radius:20px;background:#fff;padding:4px 14px}button[aria-pressed=true]{background:#1c5255;color:white;border-color:#1c5255}
.filters{display:flex;align-items:center;gap:7px;flex-wrap:wrap}input{padding:6px 12px;border:1px solid #a5bab6;border-radius:7px;max-width:100%}.count,small{color:#50686b}
details{background:white;border:1px solid #ccd8d1;border-radius:9px;margin:8px 0;scroll-margin-top:12px}summary{cursor:pointer;padding:12px 16px}summary code{color:#256664;margin-right:12px}summary span{font-size:13px;color:#526768;margin-left:12px}.body{padding:0 20px 18px}th,td{padding:8px 10px;text-align:left;vertical-align:top;border-bottom:1px solid #dbe3df}th{min-width:6em}table{border-collapse:collapse;width:100%}details[hidden]{display:none}.scroll{overflow:auto;margin-bottom:12px}.runs{font-size:14px;white-space:nowrap}.runs th{background:#eaf1ec;min-width:0}
.flow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:0;list-style:none}.flow li{background:#e1eee6;padding:5px 10px;border-radius:4px}.flow li+li:before{content:'→ ';color:#53736c}footer{margin:30px 0}
</style><header><div><small>ChiStarlink / 第三阶段</small><h1>100 道全链路仿真任务</h1>
<p>从 10 道已重放母题派生新的工程场景。展开每道题，可查看工程目标、逐层测试约束和实测结果。</p></div></header><main>
<h2>从母题到入库</h2><ol class="flow"><li>选取已验证母题</li><li>生成场景与逐层约束</li><li>运行初始与参考工程</li><li>判定异常时诊断并重放</li><li>按完整矩阵筛选</li></ol>
<p>初始工程在目标条件下触发预期失败，也是验收的一部分。物理层复用第二阶段 OAI 的 AWGN 标定表，业务层以 ns-3 逐包重放。仿真采用合成轨道与设备参数。</p><p>论文统计可同时报告母题数与派生题数。划分训练集和测试集时，同一母题及其变体应归入同一侧，以避免共享工程或故障机制泄漏。</p>
<h2>验收结果</h2><div class="scroll"><table class="runs"><thead><tr><th>类型</th><th>入库题目</th><th>重放次数</th><th>实际通过</th><th>预期失败且已复现</th></tr></thead><tbody>{summary}</tbody></table></div>
<p>修复组的首轮候选有一题在留出场景未触发业务故障。替换候选后重新执行完整修复矩阵。表中只计最终入库版本。<a href="../phase3/repair/evidence/rejected.json">查看筛除记录</a></p>
<h2>任务目录</h2><div class="filters">{buttons}<input type="search" id="query" aria-label="搜索任务" placeholder="搜索编号、题干或约束"></div>
<p class="count" aria-live="polite" id="count">显示 100 道题</p>{cards}
<footer><a href="phase-2.html">查看第二阶段 10 道母题</a></footer></main>
<script>
const tasks=[...document.querySelectorAll('details')], buttons=[...document.querySelectorAll('button')], query=document.getElementById('query');
let group='all';
function filter(){const term=query.value.trim().toLowerCase();let count=0;for(const t of tasks){t.hidden=(group!=='all'&&group!==t.dataset.group)||!t.textContent.toLowerCase().includes(term);if(!t.hidden)count++}document.getElementById('count').textContent='显示 '+count+' 道题'}
for(const b of buttons)b.onclick=()=>{group=b.dataset.group;buttons.forEach(a=>a.setAttribute('aria-pressed',String(a===b)));filter()};query.oninput=filter;
function visit(){const t=document.getElementById(location.hash.slice(1));if(t?.tagName==='DETAILS'){buttons[0].click();query.value='';filter();t.open=true;t.scrollIntoView()}}window.addEventListener('hashchange',visit);visit();
</script></html>"""


if __name__ == "__main__":
    main()
