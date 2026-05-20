"""Project: the binding between a DomainPack and a filesystem layout.

A project is a folder with a project.json and four sub-paths (vault/,
inbox/, sources/, schema.ttl). The pack defines what gets extracted and
how; the project says where the bytes live and which approval workflow
applies.
"""
from callimachus.project.project import (
    Project,
    create_from_template,
    list_projects,
    load_project,
    projects_dir,
    repo_root,
)

__all__ = [
    "Project",
    "create_from_template",
    "list_projects",
    "load_project",
    "projects_dir",
    "repo_root",
]
