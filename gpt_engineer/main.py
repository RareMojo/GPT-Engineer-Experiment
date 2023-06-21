import json
import logging

from pathlib import Path
import os
import shutil


import typer

from gpt_engineer import steps
from gpt_engineer.ai import AI
from gpt_engineer.db import DB, DBs
from gpt_engineer.steps import STEPS
from gpt_engineer.builder import initialize_identity, clean_identity

app = typer.Typer()


@app.command()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    project_path: str = typer.Argument("example", help="path"),
    delete_existing: bool = typer.Option(False, "-d", help="delete existing files"),
    agent: str = typer.Option("coder", help="agent type"),
    model: str = typer.Option("gpt-4", help="model name"),
    max_tokens: int = typer.Option(4097, help="max tokens"),
    temperature: float = typer.Option(0.1, help="temperature"),
    steps_config: steps.Config = typer.Option(
        steps.Config.DEFAULT, "--steps", "-s", help="decide which steps to run"
    ),
    run_prefix: str = typer.Option(
        "",
        help=(
            "run prefix, if you want to run multiple variants of the same project and "
            "later compare them"
        ),
    ),
):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    
    # Name identity after project folder
    identity_name = Path(project_path).name
    
    # Set up paths
    root_path = Path(os.path.curdir).absolute()
    engineer_path = root_path / "gpt_engineer"
    agent_path = engineer_path / "agent"
    identity_path = agent_path / identity_name
    input_path = Path(project_path).absolute()
    memory_path = input_path / f"{run_prefix}memory"
    workspace_path = input_path / f"{run_prefix}workspace"

    if delete_existing:
        # Delete files and subdirectories in paths
        shutil.rmtree(memory_path, ignore_errors=True)
        shutil.rmtree(workspace_path, ignore_errors=True)

    ai = AI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    dbs = DBs(
        input=DB(input_path),
        workspace=DB(workspace_path),
        memory=DB(memory_path),
        logs=DB(memory_path / "logs"),
        agent=DB(engineer_path / "agent"),
        identity=DB(identity_path),
    )

    initialize_identity(dbs, identity_name, agent) # Creates an identity named after the project from a chosen template, by default it uses the coder template
    
    for step in STEPS[steps_config]:
        messages = step(ai, dbs)
        dbs.logs[step.__name__] = json.dumps(messages)

    clean_identity(agent_path) # Optional: deletes the created identity, without this, the indentity will be updated with each run and persist between runs

if __name__ == "__main__":
    app()
