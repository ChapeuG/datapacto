"""Arquivos de repositório comuns aos projetos gerados (modelo do projeto de referência).

Gera o .gitignore e o catalog-info.yaml (Backstage), e inicializa o repositório git. Os dois itens que dependem
da infraestrutura de cada empresa são opcionais e só saem quando informados:

- organização GitHub (--github-org): remote origin e anotação github.com/project-slug;
- repositório CodeCommit (--codecommit-transformation): .github/workflows/pipeline.yml, que espelha o GitHub
  no CodeCommit a cada push em dev, qa ou prd.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

DEFAULT_GITHUB_ORG = ""  # sem organização: o projeto é criado sem remote
TEMPLATES_DIR = Path(__file__).parent / "templates" / "repo"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def repo_files(project_name: str, codecommit_repo: str = "", github_org: str = DEFAULT_GITHUB_ORG,
               language: str = "pyspark") -> dict[str, str]:
    """Arquivos de repositório do projeto, com caminho relativo ao diretório pai."""
    env = _env()
    files = {
        f"{project_name}/catalog-info.yaml": env.get_template("catalog-info.yaml.j2").render(
            project_name=project_name, github_org=github_org),
        f"{project_name}/.gitignore": env.get_template(f"gitignore-{language}.j2").render(),
    }
    if codecommit_repo:
        # Pipeline é texto puro (usa ${{ }} do GitHub Actions) — só troca o repositório CodeCommit
        pipeline = (TEMPLATES_DIR / "pipeline.yml.tpl").read_text(encoding="utf-8")
        files[f"{project_name}/.github/workflows/pipeline.yml"] = pipeline.replace("__CODECOMMIT_REPO__", codecommit_repo)
    return files


def github_remote(project_name: str, github_org: str = DEFAULT_GITHUB_ORG) -> str:
    """URL do remote origin, ou vazio quando não há organização GitHub."""
    return f"https://github.com/{github_org}/{project_name}.git" if github_org else ""


def init_git_repo(project_dir: Path, remote_url: str) -> str:
    """git init -b main + remote origin (se houver). Não faz commit nem push. Retorna o que foi feito."""
    if (project_dir / ".git").exists():
        return "repositório git já existia (mantido)"
    try:
        inside = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=project_dir, capture_output=True,
                                text=True)
        if inside.returncode == 0:
            # Projeto gerado dentro de outro repositório (ex: examples/ do datapacto): não cria repositório aninhado
            return f"dentro do repositório {inside.stdout.strip()}: git init não executado"
        subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True, capture_output=True, text=True)
        if not remote_url:
            return "git init (main), sem remote (informe --github-org para criar o origin)"
        subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=project_dir, check=True,
                       capture_output=True, text=True)
        return f"git init (main) + origin {remote_url}"
    except FileNotFoundError:
        return "git não encontrado no PATH — repositório não inicializado"
    except subprocess.CalledProcessError as e:
        return f"falha no git: {(e.stderr or e.stdout).strip()}"
