import os
import subprocess
import tempfile
from pathlib import Path


def make_repo(subjects, bodies=None, author="Dev One <dev@example.com>", branches=()):
    """Create a throwaway git repo whose history has the given subjects (oldest first)."""
    d = Path(tempfile.mkdtemp(prefix="wir-repo-"))
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev One", GIT_AUTHOR_EMAIL="dev@example.com",
               GIT_COMMITTER_NAME="Dev One", GIT_COMMITTER_EMAIL="dev@example.com")
    subprocess.run(["git", "init", "-q", "-b", "main", str(d)], check=True, env=env)
    subprocess.run(["git", "-C", str(d), "config", "user.name", "Dev One"], check=True)
    subprocess.run(["git", "-C", str(d), "config", "user.email", "dev@example.com"], check=True)
    bodies = bodies or [""] * len(subjects)
    for i, (s, b) in enumerate(zip(subjects, bodies)):
        (d / f"f{i}.txt").write_text(f"{i}\n")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True, env=env)
        msg = s + ("\n\n" + b if b else "")
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", msg], check=True, env=env)
    for br in branches:
        subprocess.run(["git", "-C", str(d), "branch", br], check=True, env=env)
    return d
