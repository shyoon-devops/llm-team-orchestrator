"""file_extractor 다중 패턴 매칭 + 파일명 검증 테스트."""

from __future__ import annotations

import os

import pytest

from orchestrator.core.file_extractor import _is_valid_filename, extract_files_from_output


class TestIsValidFilename:
    """파일명 검증 함수 테스트."""

    def test_valid_python_file(self) -> None:
        assert _is_valid_filename("src/app.py") is True

    def test_valid_nested_path(self) -> None:
        assert _is_valid_filename("src/core/models/pipeline.py") is True

    def test_valid_typescript(self) -> None:
        assert _is_valid_filename("src/App.tsx") is True

    def test_valid_yaml(self) -> None:
        assert _is_valid_filename("config.yaml") is True

    def test_valid_json(self) -> None:
        assert _is_valid_filename("package.json") is True

    def test_valid_toml(self) -> None:
        assert _is_valid_filename("pyproject.toml") is True

    def test_valid_html(self) -> None:
        assert _is_valid_filename("index.html") is True

    def test_valid_css(self) -> None:
        assert _is_valid_filename("styles.css") is True

    def test_valid_shell(self) -> None:
        assert _is_valid_filename("setup.sh") is True

    def test_invalid_no_extension(self) -> None:
        assert _is_valid_filename("Makefile") is False

    def test_invalid_korean_word(self) -> None:
        """한글 단어는 파일명으로 거부."""
        assert _is_valid_filename("개선안") is False

    def test_invalid_korean_with_extension(self) -> None:
        """한글이 포함된 파일명은 거부."""
        assert _is_valid_filename("개선안.py") is False

    def test_invalid_special_chars(self) -> None:
        assert _is_valid_filename("file name.py") is False

    def test_invalid_unknown_extension(self) -> None:
        assert _is_valid_filename("data.xyz") is False

    def test_invalid_absolute_path(self) -> None:
        """절대경로는 _is_valid_filename에서는 패스 (extract에서 별도 처리)."""
        # 절대경로도 /가 허용되므로 True를 반환하지만, extract에서 startswith('/')로 거부
        assert _is_valid_filename("/etc/passwd.txt") is True

    def test_valid_markdown(self) -> None:
        assert _is_valid_filename("README.md") is True

    def test_valid_sql(self) -> None:
        assert _is_valid_filename("migrations/001.sql") is True


class TestExtractFilesFromOutput:
    """extract_files_from_output 다중 패턴 테스트."""

    def test_pattern_colon_syntax(self, tmp_path: str) -> None:
        """```python:src/app.py 패턴."""
        output = '```python:src/app.py\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]
        assert (tmp_path / "src" / "app.py").read_text() == 'print("hello")\n'

    def test_pattern_hash_syntax(self, tmp_path: str) -> None:
        """```python # src/app.py 패턴."""
        output = '```python # src/app.py\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]

    def test_pattern_file_label(self, tmp_path: str) -> None:
        """**파일: src/app.py** 다음에 코드블록 패턴."""
        output = '**파일: src/app.py**\n```python\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]

    def test_pattern_file_label_english(self, tmp_path: str) -> None:
        """**File: src/app.py** 패턴."""
        output = '**File: src/app.py**\n```python\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]

    def test_pattern_heading_syntax(self, tmp_path: str) -> None:
        """### src/app.py 다음에 코드블록 패턴."""
        output = '### src/app.py\n```python\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]

    def test_pattern_h2_heading(self, tmp_path: str) -> None:
        """## src/app.py 다음에 코드블록 패턴."""
        output = '## src/app.py\n```python\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]

    def test_reject_false_positive_korean(self, tmp_path: str) -> None:
        """한글 파일명은 false positive로 거부."""
        output = '```python # 개선안\nprint("hello")\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == []

    def test_reject_absolute_path(self, tmp_path: str) -> None:
        """절대 경로는 거부."""
        output = '```python:/etc/passwd.txt\nmalicious\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == []

    def test_reject_no_extension(self, tmp_path: str) -> None:
        """확장자 없는 파일명은 거부."""
        output = '```python:Makefile\nall:\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == []

    def test_multiple_files(self, tmp_path: str) -> None:
        """여러 파일 추출."""
        output = (
            '```python:src/app.py\nprint("a")\n```\n\n'
            '```typescript:src/index.ts\nconsole.log("b")\n```'
        )
        files = extract_files_from_output(output, str(tmp_path))
        assert "src/app.py" in files
        assert "src/index.ts" in files
        assert len(files) == 2

    def test_dedup_same_path(self, tmp_path: str) -> None:
        """동일 파일명은 첫 번째 매칭만 사용."""
        output = (
            '```python:src/app.py\nfirst\n```\n\n'
            '**파일: src/app.py**\n```python\nsecond\n```'
        )
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/app.py"]
        # 첫 번째 패턴의 내용이 저장됨
        assert (tmp_path / "src" / "app.py").read_text() == "first\n"

    def test_empty_output(self, tmp_path: str) -> None:
        """빈 출력."""
        files = extract_files_from_output("", str(tmp_path))
        assert files == []

    def test_no_code_blocks(self, tmp_path: str) -> None:
        """코드 블록 없는 텍스트."""
        output = "이것은 일반 텍스트입니다. 코드 블록이 없습니다."
        files = extract_files_from_output(output, str(tmp_path))
        assert files == []

    def test_mixed_patterns(self, tmp_path: str) -> None:
        """여러 패턴이 섞인 출력."""
        output = (
            '```python:src/models.py\nclass Model:\n    pass\n```\n\n'
            '**파일: src/routes.py**\n```python\ndef get():\n    pass\n```\n\n'
            '### src/config.yaml\n```yaml\nkey: value\n```'
        )
        files = extract_files_from_output(output, str(tmp_path))
        assert "src/models.py" in files
        assert "src/routes.py" in files
        assert "src/config.yaml" in files
        assert len(files) == 3

    def test_nested_directory_creation(self, tmp_path: str) -> None:
        """깊은 디렉토리 구조 생성."""
        output = '```python:src/core/models/user.py\nclass User:\n    pass\n```'
        files = extract_files_from_output(output, str(tmp_path))
        assert files == ["src/core/models/user.py"]
        assert (tmp_path / "src" / "core" / "models" / "user.py").exists()
