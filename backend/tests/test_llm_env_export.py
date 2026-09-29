"""独立运行目录只接收编号项，不覆盖数据库或邮箱凭据。"""
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/export-llm-env.py'


def test_export_only_numbered_fields_and_replace_stale_groups(tmp_path):
    source, output = tmp_path/'source.env', tmp_path/'output.env'
    source.write_text("MYSQL_PASSWORD=internal\nSMTP_PASSWORD=mail\nLLM1_NAME=one\nLLM1_API_KEY='secret$part#quote\"'\n")
    result = subprocess.run([sys.executable,str(SCRIPT),str(source),str(output)],capture_output=True,text=True)
    assert result.returncode == 0
    text = output.read_text()
    assert 'MYSQL_PASSWORD' not in text and 'SMTP_PASSWORD' not in text
    assert 'secret$$part' in text
    assert 'secret' not in result.stdout + result.stderr
    assert output.stat().st_mode & 0o777 == 0o600
    source.write_text('LLM3_NAME=three\n')
    assert subprocess.run([sys.executable,str(SCRIPT),str(source),str(output)],capture_output=True).returncode == 0
    assert 'LLM1' not in output.read_text()


def test_invalid_source_and_same_file_never_overwrite(tmp_path):
    source, output = tmp_path/'source.env', tmp_path/'output.env'
    source.write_text('LLM1_API_KEY=one\nLLM1_API_KEY=two\n'); output.write_text('original')
    assert subprocess.run([sys.executable,str(SCRIPT),str(source),str(output)],capture_output=True).returncode == 2
    assert output.read_text() == 'original'
    original=source.read_text()
    assert subprocess.run([sys.executable,str(SCRIPT),str(source),str(source)],capture_output=True).returncode == 2
    assert source.read_text() == original
