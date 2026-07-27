#!/usr/bin/env python3
"""从指定本地文本路径执行语义 TopN 召回。

脚本功能：
1. 读取调用方指定的 Markdown 文件、纯文本文件或目录。
2. 按 Markdown 二级及更深标题或纯文本段落切分可召回内容。
3. 使用本地 Embedding 模型实时计算查询向量和文档向量。
4. 按向量相似度排序，输出 TopN 的 ``id``、``source`` 和完整 ``text``。

关键函数：
- ``load_chunks``：读取指定路径并切分为可召回文本块。
- ``retrieve``：计算查询与文本块的向量相似度并选择 TopN。
- ``main``：解析 CLI 参数、加载本地模型、执行召回并输出结果。

向量仅存在于当前进程内存；Markdown 和纯文本文件持续作为知识事实源。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, Sequence


MODEL_REPO_ID = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_MODEL = MODEL_REPO_ID
SUPPORTED_SUFFIXES = {".md", ".txt"}
MARKDOWN_SECTION = re.compile(
    r"(?m)^(#{2,6})[ \t]+(.+?)[ \t]*$"
)


@dataclass(frozen=True)
class TextChunk:
    """一条可参与向量召回的文本单元。"""

    id: str
    source: str
    text: str


class CliArgumentError(ValueError):
    """表示 CLI 参数解析失败，并允许主流程统一输出错误。"""


class RagArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


class EmbeddingBackend(Protocol):
    def encode_query(self, text: str) -> Sequence[float]:
        """返回一个已归一化的查询向量。"""

    def encode_documents(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        """为每段文档返回一个已归一化的向量。"""


class SentenceTransformerBackend:
    """从本地文件加载 Sentence Transformers Embedding 模型。"""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers 未安装；请先准备本地依赖"
            ) from exc

        try:
            self._model = SentenceTransformer(
                model_name,
                local_files_only=True,
            )
        except Exception as exc:
            raise RuntimeError(
                f"本地模型加载失败：{model_name}"
            ) from exc

    def encode_query(self, text: str) -> Sequence[float]:
        try:
            vectors = self._model.encode(
                [text],
                prompt_name="query",
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise RuntimeError("查询 Embedding 计算失败") from exc
        values = vectors.tolist()
        if len(values) != 1:
            raise RuntimeError("查询 Embedding 返回的向量数量不为 1")
        return values[0]

    def encode_documents(
        self,
        texts: Sequence[str],
    ) -> Sequence[Sequence[float]]:
        try:
            vectors = self._model.encode(
                list(texts),
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise RuntimeError("文档 Embedding 计算失败") from exc
        return vectors.tolist()


def _clean_heading(raw: str) -> str:
    """清理 Markdown 标题末尾的井号和空白。"""

    return re.sub(r"[ \t]+#+[ \t]*$", "", raw).strip()


def _markdown_chunks(path: Path, text: str) -> list[TextChunk]:
    """按二级及更深 Markdown 标题切分文本。"""

    matches = list(MARKDOWN_SECTION.finditer(text))
    source = str(path.resolve())
    chunks: list[TextChunk] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():end].strip()
        if body:
            chunks.append(
                TextChunk(
                    id=_clean_heading(match.group(2)),
                    source=source,
                    text=body,
                )
            )
    if chunks:
        return chunks

    body = text.strip()
    if not body:
        return []
    return [TextChunk(id=path.stem, source=source, text=body)]


def _plain_text_chunks(path: Path, text: str) -> list[TextChunk]:
    """按空行分隔的段落切分纯文本。"""

    source = str(path.resolve())
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n[ \t]*\n+", text)
        if paragraph.strip()
    ]
    return [
        TextChunk(
            id=f"{path.stem}#{index:03d}",
            source=source,
            text=paragraph,
        )
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def _source_files(source: Path) -> list[Path]:
    """解析 source，返回顺序稳定的 Markdown 和纯文本文件列表。"""

    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("source 文件类型仅支持 .md 和 .txt")
        return [source]
    if source.is_dir():
        return sorted(
            path
            for path in source.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        )
    raise OSError("source 路径不存在或不可读")


def load_chunks(source: Path) -> list[TextChunk]:
    """读取指定文件或目录，返回全部可召回文本块。"""

    chunks: list[TextChunk] = []
    for path in _source_files(source):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise OSError(f"{path}: {exc}") from exc
        if path.suffix.lower() == ".md":
            chunks.extend(_markdown_chunks(path, text))
        else:
            chunks.extend(_plain_text_chunks(path, text))
    if not chunks:
        raise ValueError("source 中没有可召回的文本")
    return chunks


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    """计算两个已归一化向量的点积相似度。"""

    if len(left) != len(right) or not left:
        raise ValueError("Embedding 向量维度不一致或为空")
    value = sum(float(a) * float(b) for a, b in zip(left, right))
    if not math.isfinite(value):
        raise ValueError("Embedding 相似度不是有限数值")
    return value


def retrieve(
    chunks: Sequence[TextChunk],
    query: str,
    top_n: int,
    embedder: EmbeddingBackend,
) -> list[TextChunk]:
    """计算相似度并返回 TopN 文本块，相似度分数只用于内部排序。"""

    if not query.strip():
        raise ValueError("query 不能为空")
    if top_n < 1:
        raise ValueError("top-n 必须大于等于 1")
    if not chunks:
        raise ValueError("source 中没有可召回的文本")

    query_vector = embedder.encode_query(query.strip())
    document_vectors = list(
        embedder.encode_documents([chunk.text for chunk in chunks])
    )
    if len(document_vectors) != len(chunks):
        raise ValueError("Embedding 返回的向量数量与文本数量不一致")

    ranked = [
        (_dot(query_vector, vector), chunk)
        for chunk, vector in zip(chunks, document_vectors)
    ]
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].source,
            item[1].id,
        )
    )
    return [chunk for _, chunk in ranked[: min(top_n, len(ranked))]]


def _emit_error(error: str, message: str, as_json: bool) -> None:
    """按纯文本或 JSON 格式输出统一错误。"""

    if as_json:
        print(json.dumps({"error": error, "message": message}, ensure_ascii=False))
    else:
        print(f"{error}: {message}")


def _emit_matches(chunks: Sequence[TextChunk], as_json: bool) -> None:
    """按纯文本或 JSON 格式输出召回结果。"""

    matches = [
        {
            "id": chunk.id,
            "source": chunk.source,
            "text": chunk.text,
        }
        for chunk in chunks
    ]
    if as_json:
        print(json.dumps({"matches": matches}, ensure_ascii=False))
        return
    for match in matches:
        print(f"{match['id']}\n{match['source']}\n{match['text']}")


def build_parser() -> argparse.ArgumentParser:
    """创建 CLI 参数解析器。"""

    parser = RagArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-n", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(
    argv: Sequence[str] | None = None,
    embedder_factory: Callable[[str], EmbeddingBackend] | None = None,
) -> int:
    """执行参数校验、语料读取、模型加载、向量召回和结果输出。"""

    argument_list = list(argv) if argv is not None else sys.argv[1:]
    as_json = "--json" in argument_list
    try:
        args = build_parser().parse_args(argument_list)
    except CliArgumentError as exc:
        _emit_error("INVALID_ARGUMENT", str(exc), as_json)
        return 2

    if not args.query.strip() or args.top_n < 1:
        message = (
            "query 不能为空"
            if not args.query.strip()
            else "top-n 必须大于等于 1"
        )
        _emit_error("INVALID_ARGUMENT", message, args.as_json)
        return 2

    try:
        chunks = load_chunks(Path(args.source))
    except OSError as exc:
        _emit_error("IO_ERROR", str(exc), args.as_json)
        return 2
    except ValueError as exc:
        _emit_error("INVALID_SOURCE", str(exc), args.as_json)
        return 1

    factory = embedder_factory or SentenceTransformerBackend
    try:
        embedder = factory(args.model)
    except Exception as exc:
        _emit_error("MODEL_ERROR", str(exc), args.as_json)
        return 2

    try:
        matches = retrieve(
            chunks=chunks,
            query=args.query,
            top_n=args.top_n,
            embedder=embedder,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        _emit_error("EMBEDDING_ERROR", str(exc), args.as_json)
        return 2

    _emit_matches(matches, args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
