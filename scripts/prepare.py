"""Prepare a build tree and its pinned translation/font inputs."""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib


PROJECT = Path(__file__).resolve().parents[1]
FONT = "Noto Sans CJK SC"
ICONS = {
    "pdfcraft.svg": "assets/app-icon/pdfcraft.svg",
    "pdfcraft.ico": "assets/app-icon/pdfcraft.ico",
    "pdfcraft-128.png": "assets/app-icon/hicolor/128x128/apps/ai.storyteller.pdfcraft.png",
    "pdfcraft-256.png": "assets/app-icon/hicolor/256x256/apps/ai.storyteller.pdfcraft.png",
}


def extract_source(archive, source):
    if source.exists():
        raise ValueError(f"Build path already exists: {source}")
    with tempfile.TemporaryDirectory(prefix="pdfcraft-", dir=source.parent) as temporary:
        with tarfile.open(archive, "r:gz") as upstream:
            upstream.extractall(temporary, filter="data")
        roots = list(Path(temporary).iterdir())
        if len(roots) != 1 or not (roots[0] / "Cargo.toml").is_file():
            raise ValueError("Expected a GitHub archive containing one PdfCraft source tree")
        roots[0].rename(source)


def checkout(repo, revision, destination):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError(f"Missing or invalid revision for {repo}: {revision!r}")
    subprocess.run(["git", "init", "--quiet", str(destination)], check=True)
    subprocess.run(
        ["git", "fetch", "--no-tags", "--depth", "1", f"https://github.com/storytold/{repo}.git", revision],
        cwd=destination, check=True,
    )
    subprocess.run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=destination, check=True)


def install_icons(source):
    manifest = source / "ATTRIBUTION.toml"
    replaced = set()

    for icon, target in ICONS.items():
        if not (source / target).is_file():
            raise ValueError(f"Upstream icon path changed: {target}")
        shutil.copyfile(PROJECT / "assets" / icon, source / target)

    def replace_asset(match):
        block = match[0]
        path = re.search(r'^path = "([^"]+)"$', block, re.MULTILINE)
        if not path:
            return block
        path = path[1]
        if path.startswith("docs/brand/") and 'licence = "LicenseRef-Storyteller-Trademark"' in block:
            (source / path).unlink()
            return ""
        if path not in ICONS.values():
            return block
        replaced.add(path)
        fields = {
            "author": "NoverNobida/pdfcraft contributors",
            "source": "https://github.com/NoverNobida/pdfcraft/tree/main/assets",
            "licence_file": "LICENSE-MIT",
            "sha256": sha256((source / path).read_bytes()).hexdigest(),
        }
        for key, value in fields.items():
            block = re.sub(rf'^{key} = "[^"]*"$', f'{key} = "{value}"', block, flags=re.MULTILINE)
        return block

    changed = re.sub(r"(?ms)^\[\[asset\]\]\n.*?(?=^\[\[|\Z)", replace_asset, manifest.read_text(encoding="utf-8"))
    if replaced != set(ICONS.values()):
        raise ValueError("Upstream attribution no longer lists all the replaced icons")
    manifest.write_text(changed, encoding="utf-8", newline="\n")
    with (source / "NOTICE").open("a", encoding="utf-8") as notice:
        notice.write("\nNoverNobida/pdfcraft provides this independent build of PdfCraft.\n")
        notice.write("The modified build and new icon are distributed under MIT OR Apache-2.0.\n")


def configure_fonts(fonts, platform):
    manifest = fonts / "fonts/manifest.txt"
    rows = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
    matches = [row for row in rows if row.startswith(f"{FONT} | Regular | ")]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one bundled fallback face for {FONT}")
    row = matches[0]
    _, _, filename, scripts, licence, licence_file, checksum, _ = row.strip().split(" | ")
    if "Hans" not in scripts.split(",") or licence != "OFL-1.1" or not (fonts / licence_file).is_file():
        raise ValueError(f"Missing Simplified Chinese classification or OFL notice for {FONT}")
    if sha256((fonts / filename).read_bytes()).hexdigest() != checksum:
        raise ValueError(f"Font SHA-256 mismatch: {filename}")

    if platform == "windows":
        # The native packager expects the Simplified Chinese fallback in this separate manifest.
        (fonts / "fonts/simplified-chinese-manifest.txt").write_text(row, encoding="utf-8", newline="\n")
        manifest.write_text("".join(item for item in rows if item != row), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("platform", choices=("windows", "web"))
    parser.add_argument("version")
    args = parser.parse_args()

    source = args.source.resolve()
    extract_source(args.archive, source)
    package = tomllib.loads((source / "Cargo.toml").read_text(encoding="utf-8"))["workspace"]["package"]
    if package["version"] != args.version:
        raise ValueError(f"Cargo workspace version {package['version']} differs from release {args.version}")

    patch = PROJECT / "patches/pdfcraft.patch"
    git_env = {**os.environ, "GIT_CEILING_DIRECTORIES": source.parent.as_posix()}
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=source, env=git_env, check=True)
    subprocess.run(["git", "apply", str(patch)], cwd=source, env=git_env, check=True)
    install_icons(source)

    i18n_rev = (source / "craft-i18n.rev").read_text(encoding="utf-8").strip()
    workflow = (source / ".github/workflows/release.yml").read_text(encoding="utf-8")
    fonts_pin = re.search(r"^\s+craft-fonts-ref:\s*([a-f0-9]{40})\s*$", workflow, re.MULTILINE)
    if not fonts_pin:
        raise ValueError("Upstream release workflow no longer declares the craft-fonts commit")
    translations = source.with_name("craft-i18n")
    fonts = source.with_name("craft-fonts")
    checkout("craft-i18n", i18n_rev, translations)
    checkout("craft-fonts", fonts_pin[1], fonts)
    for file in ("common.tsv", "pdfcraft.tsv"):
        if not (translations / "locales/zh-hans" / file).is_file():
            raise ValueError(f"Simplified Chinese catalog missing: {file}")
    configure_fonts(fonts, args.platform)

    env = {
        "CRAFT_I18N_DIR": translations,
        "CRAFT_I18N_REQUIRED": "1",
        "CRAFT_FONTS_DIR": fonts,
        "CRAFT_FONTS_REQUIRED": "1",
    }
    settings = "".join(f"{key}={value}\n" for key, value in env.items())
    if "GITHUB_ENV" in os.environ:
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8", newline="\n") as file:
            file.write(settings)
    else:
        print(settings, end="")


if __name__ == "__main__":
    main()
