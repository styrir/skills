"""End-to-end checks using bundled synthetic DOCX/PDF fixtures and local tools."""
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures"
CONVERT = [sys.executable, str(Path(__file__).with_name("research-convert"))]


def run_check():
    with tempfile.TemporaryDirectory() as temp:
        for name, needles in [
            ("sample.docx", ["silver otter", "mc", "Alpha", "7"]),
            ("sample.pdf", ["silver otter", "copper heron"]),
            ("inline-image-math.pdf", ["0.304", "0.230"]),
        ]:
            source = ROOT / name
            before = sha256(source.read_bytes()).digest()
            output = Path(temp) / name
            result = subprocess.run([*CONVERT, str(source), "--out", str(output)],
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr[-5000:]
            markdown = Path(result.stdout.strip())
            text = markdown.read_text()
            for needle in needles:
                assert needle in text, (name, needle, text)
            images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
            if name != "inline-image-math.pdf":
                assert images, (name, "No figure reference")
            for image in images:
                assert (markdown.parent / image.strip("<>")).is_file(), image
            if name.endswith("docx"):
                assert "$$" in text and "|" in text, text
            if name == "inline-image-math.pdf":
                math = re.findall(r"\$\$.*?\$\$|(?<!\$)\$(?!\$)[^$\n]+?\$(?!\$)", text, re.S)
                normalized = re.sub(r"[\s{}]", "", " ".join(math)).replace("−", "-")
                for expected in ["-0.304", "+0.230", "h_i", "E=mc^2"]:
                    assert expected in normalized, (expected, text)
            assert sha256(source.read_bytes()).digest() == before
            saved = markdown.read_bytes()
            repeat = subprocess.run([*CONVERT, str(source), "--out", str(output)],
                                    capture_output=True, text=True)
            assert repeat.returncode != 0 and markdown.read_bytes() == saved
        output = Path(temp) / "equation-only"
        equation = subprocess.run([*CONVERT, str(ROOT / "sample.pdf"), "--pages", "2",
                                   "--out", str(output)], capture_output=True, text=True)
        assert equation.returncode == 0, equation.stderr[-5000:]
        text = Path(equation.stdout.strip()).read_text()
        assert "$$" in text and "mc" in text, text
        assert "copper heron" not in text and "silver otter" not in text, text
        invalid = subprocess.run([*CONVERT, str(ROOT / "sample.docx"), "--pages", "0"],
                                 capture_output=True, text=True)
        assert invalid.returncode != 0
    print("PASS: Word preservation; PDF text/OCR/figures/image-based inline math/subscripts/equations/page selection; source and output protection")


if __name__ == "__main__":
    run_check()
