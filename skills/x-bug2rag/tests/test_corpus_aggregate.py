import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BUG2RAG_DIR = Path(__file__).resolve().parents[1]
ROOT = BUG2RAG_DIR.parents[1]
AGGREGATE = BUG2RAG_DIR / "scripts" / "corpus_aggregate.py"
TRIAGE_STORE = BUG2RAG_DIR / "scripts" / "triage_store.py"
HOME_CORPUS = BUG2RAG_DIR / "scripts" / "home_corpus.py"


def rich_corpus(count: int) -> str:
    categories = (
        "状态机",
        "并发/时序",
        "幂等/唯一",
        "边界/默认值",
        "权限/越权",
    )
    sections = ["# 测试风险语料", ""]
    for number in range(1, count + 1):
        category = categories[(number - 1) % len(categories)]
        if number == 1:
            category = "权限/越权、边界/默认值"
        sections.extend(
            (
                f"## AR-{number:03d}",
                "",
                f"关键词：对象{number}、动作{number}、状态{number}",
                f"Risk：失败机制 {number} 会产生错误结果。",
                f"场景：触发条件 {number} 出现。",
                f"错误实现：错误做法 {number}。",
                f"正确实现：正确做法 {number}。",
                f"可观察差异：结果 {number} 可以被观察。",
                f"分类：{category}",
                "来源：test-fixture",
                "",
            )
        )
    return "\n".join(sections).rstrip() + "\n"


def overlapping_voice_corpus() -> str:
    cards = (
        (
            "VAD、有效帧、话轮、短句丢弃",
            "用过滤后的有效帧数近似墙钟发言时长时，自然短句会被错误判为过短。",
            "上游只上传 VAD 有效帧，下游按累计帧数判断话轮。",
            "把有效帧直接当作完整发言时长。",
            "区分有效语音量与墙钟时长并按真实分布校准。",
            "错误实现丢弃自然短句；正确实现接受满足交互目标的短句。",
            "边界/默认值",
        ),
        (
            "提前刷新、话轮、上行丢弃、长句截断",
            "较小帧数上限提前进入回复状态时，长句话轮的后半段会被丢弃。",
            "空闲超时和强制帧数上限共同结束流式话轮。",
            "把保护上限设成普通长句可达到的值。",
            "用空闲超时正常收口并把强制上限设为异常保护边界。",
            "错误实现在固定帧数回复；正确实现等待停顿后回复。",
            "状态机、边界/默认值",
        ),
        (
            "会话配额、话轮、回声循环、重复回复",
            "缺少每次入口对应的回复配额时，回声上行会在同一话轮内反复触发回复。",
            "下行回复会被设备再次采集为上行。",
            "每批上行都触发回复。",
            "入口只开放一个回复配额并在回复开始时消费。",
            "错误实现单次入口重复回复；正确实现单次入口最多回复一次。",
            "幂等/唯一、状态机",
        ),
    )
    sections = ["# 同关键词跨分片回归", ""]
    for number, card in enumerate(cards, start=1):
        keywords, risk, scene, wrong, correct, observable, category = card
        sections.extend(
            (
                f"## AR-{number:03d}",
                "",
                f"关键词：{keywords}",
                f"Risk：{risk}",
                f"场景：{scene}",
                f"错误实现：{wrong}",
                f"正确实现：{correct}",
                f"可观察差异：{observable}",
                f"分类：{category}",
                "来源：x-bot/reports/fix",
                "",
            )
        )
    return "\n".join(sections).rstrip() + "\n"


class Bug2RagAggregateTest(unittest.TestCase):
    def run_cli(self, script: Path, *args: str):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def build_fixture(
        self,
        directory: Path,
        *,
        count: int = 5,
        shard_size: int = 2,
    ) -> Path:
        source = directory / "risk-catalog.md"
        target = directory / "risk-corpus"
        source.write_text(rich_corpus(count), encoding="utf-8")
        result = self.run_cli(
            AGGREGATE,
            "build",
            "--source",
            str(source),
            "--target",
            str(target),
            "--shard-size",
            str(shard_size),
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def test_build_creates_taxonomy_indexes_and_stable_shards(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw))
            manifest = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
            shard_names = sorted(
                path.name for path in (target / "shards").glob("risk-*.md")
            )
            all_records = [
                json.loads(line)
                for line in (target / "indexes" / "all.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

            self.assertEqual(manifest["entry_count"], 5)
            self.assertEqual(manifest["shard_size"], 2)
            self.assertEqual(
                shard_names,
                [
                    "risk-000001-000002.md",
                    "risk-000003-000004.md",
                    "risk-000005-000006.md",
                ],
            )
            self.assertEqual([record["id"] for record in all_records], [
                "AR-001",
                "AR-002",
                "AR-003",
                "AR-004",
                "AR-005",
            ])
            self.assertIn(
                "二级索引：indexes/authorization.md",
                (target / "taxonomy.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                '"id": "AR-001"',
                (target / "indexes" / "authorization.jsonl").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertIn(
                '"id": "AR-001"',
                (target / "indexes" / "boundary-default.jsonl").read_text(
                    encoding="utf-8"
                ),
            )

    def test_home_init_creates_only_user_rag_directory_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            simulated_home = Path(raw) / "new user"
            directory = simulated_home / ".x-dev-pipeline" / "rag"
            target = directory / "risk-catalog.md"

            initialized = self.run_cli(
                HOME_CORPUS,
                "init",
                "--home",
                str(simulated_home),
                "--json",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stdout + initialized.stderr,
            )
            payload = json.loads(initialized.stdout)

            self.assertTrue(payload["created"])
            self.assertEqual(payload["target"], str(target))
            self.assertTrue(directory.is_dir())
            self.assertEqual(list(directory.iterdir()), [])

            repeated = self.run_cli(
                HOME_CORPUS,
                "init",
                "--home",
                str(simulated_home),
                "--json",
            )
            self.assertEqual(repeated.returncode, 0, repeated.stdout)
            self.assertFalse(json.loads(repeated.stdout)["created"])

    def test_home_import_existing_requires_init_and_copies_exact_file(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            simulated_home = directory / "new user"
            target = (
                simulated_home
                / ".x-dev-pipeline"
                / "rag"
                / "risk-catalog.md"
            )
            source = directory / "risk-catalog.md"
            source.write_text(rich_corpus(3), encoding="utf-8")

            premature = self.run_cli(
                HOME_CORPUS,
                "import-existing",
                "--home",
                str(simulated_home),
                "--source",
                str(source),
                "--json",
            )
            self.assertEqual(premature.returncode, 1)
            self.assertIn("请先初始化", json.loads(premature.stdout)["error"])

            initialized = self.run_cli(
                HOME_CORPUS,
                "init",
                "--home",
                str(simulated_home),
                "--json",
            )
            imported = self.run_cli(
                HOME_CORPUS,
                "import-existing",
                "--home",
                str(simulated_home),
                "--source",
                str(source),
                "--json",
            )
            before_repeat = target.read_bytes()
            repeated = self.run_cli(
                HOME_CORPUS,
                "import-existing",
                "--home",
                str(simulated_home),
                "--source",
                str(source),
                "--json",
            )
            after_repeat = target.read_bytes()
            validated = self.run_cli(
                HOME_CORPUS,
                "validate",
                "--home",
                str(simulated_home),
                "--json",
            )

            self.assertEqual(initialized.returncode, 0, initialized.stdout)
            self.assertEqual(imported.returncode, 0, imported.stdout)
            self.assertTrue(json.loads(imported.stdout)["copied"])
            self.assertEqual(json.loads(imported.stdout)["entry_count"], 3)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(repeated.returncode, 0)
            self.assertFalse(json.loads(repeated.stdout)["copied"])
            self.assertEqual(after_repeat, before_repeat)
            self.assertEqual(validated.returncode, 0, validated.stdout)
            self.assertTrue(json.loads(validated.stdout)["valid"])

    def test_read_returns_only_requested_sections_across_shards(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw))
            result = self.run_cli(
                AGGREGATE,
                "read",
                "--target",
                str(target),
                "--ids",
                "AR-004",
                "AR-001",
                "AR-004",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)

            self.assertEqual(
                [match["id"] for match in payload["matches"]],
                ["AR-004", "AR-001"],
            )
            self.assertIn("## AR-004", payload["matches"][0]["text"])
            self.assertNotIn("## AR-003", payload["matches"][0]["text"])
            self.assertTrue(
                payload["matches"][0]["source"].endswith(
                    "risk-000003-000004.md"
                )
            )

    def test_triage_store_appends_to_aggregate_and_rebuilds_indexes(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw), count=2)
            result = self.run_cli(
                TRIAGE_STORE,
                "--target",
                str(target),
                "--keywords",
                "新工具、白名单、审批",
                "--risk",
                "新增能力只完成执行注册时，生产策略会提前拒绝请求。",
                "--scene",
                "系统新增受保护能力。",
                "--wrong",
                "只注册执行入口。",
                "--correct",
                "同步注册入口和能力策略。",
                "--observable",
                "生产请求能够进入审批链。",
                "--category",
                "权限/越权",
                "--source",
                "test",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["stored"], ["AR-003"])
            self.assertEqual(
                json.loads(
                    (target / "manifest.json").read_text(encoding="utf-8")
                )["entry_count"],
                3,
            )
            self.assertIn(
                '"id": "AR-003"',
                (target / "indexes" / "authorization.jsonl").read_text(
                    encoding="utf-8"
                ),
            )

    def test_validate_detects_stale_index_and_rebuild_repairs_it(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw))
            all_index = target / "indexes" / "all.jsonl"
            all_index.write_text("{}\n", encoding="utf-8")

            broken = self.run_cli(
                AGGREGATE,
                "validate",
                "--target",
                str(target),
                "--json",
            )
            self.assertEqual(broken.returncode, 1)
            self.assertIn(
                "indexes/all.jsonl",
                json.loads(broken.stdout)["issues"][0],
            )

            rebuilt = self.run_cli(
                AGGREGATE,
                "rebuild",
                "--target",
                str(target),
                "--json",
            )
            valid = self.run_cli(
                AGGREGATE,
                "validate",
                "--target",
                str(target),
                "--json",
            )
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout + rebuilt.stderr)
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertTrue(json.loads(valid.stdout)["valid"])

    def test_select_merges_routes_and_deduplicates_ids(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw))
            selected_path = Path(raw) / "selected.md"
            selected = self.run_cli(
                AGGREGATE,
                "select",
                "--target",
                str(target),
                "--routes",
                "authorization",
                "boundary-default",
                "--output",
                str(selected_path),
                "--json",
            )
            selected_text = selected_path.read_text(encoding="utf-8")

            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            self.assertEqual(selected_text.count("## AR-001"), 1)
            self.assertIn("失败机制：", selected_text)
            self.assertNotIn("错误实现：", selected_text)

    def test_search_returns_short_cards_then_read_returns_full_cards(self):
        with tempfile.TemporaryDirectory() as raw:
            target = self.build_fixture(Path(raw))
            searched = self.run_cli(
                AGGREGATE,
                "search",
                "--target",
                str(target),
                "--routes",
                "authorization",
                "boundary-default",
                "--query",
                "对象1 状态1 失败机制1 错误结果",
                "--top-n",
                "2",
                "--json",
            )
            self.assertEqual(
                searched.returncode,
                0,
                searched.stdout + searched.stderr,
            )
            search_payload = json.loads(searched.stdout)
            self.assertEqual(search_payload["matches"][0]["id"], "AR-001")
            self.assertIn("失败机制：", search_payload["matches"][0]["text"])
            self.assertNotIn("错误实现：", search_payload["matches"][0]["text"])

            read = self.run_cli(
                AGGREGATE,
                "read",
                "--target",
                str(target),
                "--ids",
                search_payload["matches"][0]["id"],
                "--json",
            )
            self.assertEqual(read.returncode, 0, read.stdout + read.stderr)
            full_text = json.loads(read.stdout)["matches"][0]["text"]
            self.assertIn("错误实现：错误做法 1。", full_text)
            self.assertIn("正确实现：正确做法 1。", full_text)

    def test_same_keywords_across_shards_are_ranked_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source = directory / "voice-risks.md"
            source.write_text(overlapping_voice_corpus(), encoding="utf-8")
            target = directory / "risk-corpus"
            built = self.run_cli(
                AGGREGATE,
                "build",
                "--source",
                str(source),
                "--target",
                str(target),
                "--shard-size",
                "1",
                "--json",
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

            searched = self.run_cli(
                AGGREGATE,
                "search",
                "--target",
                str(target),
                "--routes",
                "state-machine",
                "boundary-default",
                "idempotency",
                "--query",
                "每批上行 回声循环 同一话轮 重复回复",
                "--top-n",
                "3",
                "--json",
            )
            self.assertEqual(
                searched.returncode,
                0,
                searched.stdout + searched.stderr,
            )
            matches = json.loads(searched.stdout)["matches"]
            ids = [match["id"] for match in matches]
            self.assertEqual(ids[0], "AR-003")
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(
                matches[0]["locator"]["shard"],
                "shards/risk-000003-000003.md",
            )

    def test_flat_store_and_validation_are_self_contained(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "risk-catalog.md"
            target.write_text(rich_corpus(1), encoding="utf-8")
            stored = self.run_cli(
                TRIAGE_STORE,
                "--target",
                str(target),
                "--keywords",
                "配置、漂移、默认值",
                "--risk",
                "多个组件维护独立默认端点时，局部成功会掩盖端到端配置漂移。",
                "--scene",
                "多个运行组件连接同一服务。",
                "--wrong",
                "每个组件维护自己的默认地址。",
                "--correct",
                "共享配置源并定义覆盖优先级。",
                "--observable",
                "所有组件解析到同一端点。",
                "--category",
                "持久化一致性、边界/默认值",
                "--json",
            )
            self.assertEqual(stored.returncode, 0, stored.stdout + stored.stderr)
            self.assertEqual(json.loads(stored.stdout)["stored"][0]["id"], "AR-002")

            validated = self.run_cli(
                AGGREGATE,
                "validate-flat",
                "--target",
                str(target),
                "--json",
            )
            self.assertEqual(
                validated.returncode,
                0,
                validated.stdout + validated.stderr,
            )
            self.assertTrue(json.loads(validated.stdout)["valid"])

    def test_flat_store_requires_category_and_preserves_file_on_refusal(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "risk-catalog.md"
            target.write_text(rich_corpus(1), encoding="utf-8")
            before = target.read_text(encoding="utf-8")
            refused = self.run_cli(
                TRIAGE_STORE,
                "--target",
                str(target),
                "--keywords",
                "配置、漂移",
                "--risk",
                "缺少分类的经验无法进入一级路由。",
                "--scene",
                "写入聚合前置单文件。",
                "--wrong",
                "省略分类。",
                "--correct",
                "填写有效分类。",
                "--observable",
                "条目能被路由。",
                "--json",
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("分类", json.loads(refused.stdout)["errors"][0])
            self.assertEqual(target.read_text(encoding="utf-8"), before)

    def test_ids_grow_beyond_three_digits(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            source = directory / "risk-catalog.md"
            source.write_text(
                rich_corpus(1).replace("AR-001", "AR-999"),
                encoding="utf-8",
            )
            target = directory / "risk-corpus"
            built = self.run_cli(
                AGGREGATE,
                "build",
                "--source",
                str(source),
                "--target",
                str(target),
                "--json",
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = self.run_cli(
                TRIAGE_STORE,
                "--target",
                str(target),
                "--keywords",
                "编号、扩展",
                "--risk",
                "条目超过三位数后，固定三位解析会拒绝合法新记录。",
                "--scene",
                "风险库已经拥有 999 条编号空间。",
                "--wrong",
                "解析器只接受三个数字。",
                "--correct",
                "编号使用至少三位并允许自然增长。",
                "--observable",
                "第 1000 条经验能够写入并被索引。",
                "--category",
                "边界/默认值",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["stored"], ["AR-1000"])


if __name__ == "__main__":
    unittest.main()
