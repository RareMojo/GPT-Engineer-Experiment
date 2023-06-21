
import json
import os
from pathlib import Path
import shutil
from gpt_engineer.db import DBs


# Handle identity creation and files

def initialize_identity(dbs: DBs, project_name: str, template_name: str):
    '''Initialize an identity for a project.'''
    template_path = dbs.agent.path / template_name
    identity_path = dbs.agent.path / project_name
    prompt_path = dbs.input.path / "prompt.json"

    if template_path.exists():
        if identity_path.exists() and identity_path != template_path:
            print(f"Updating identity for project: {project_name}")
        else:
            print(f"Building identity for project: {project_name}")
        
        build_identity(template_path, identity_path, prompt_path)
    else:
        print(f"Template '{template_name}' not found in {dbs.agent.path}")


def build_identity(template_path: Path, identity_path: Path, prompt_path: Path):
    '''Build an identity from a template.'''
    task = 'building'
    if identity_path.exists() and identity_path != template_path:
        shutil.rmtree(identity_path)
        task = 'updating'

    shutil.copytree(template_path, identity_path)

    with open(prompt_path, "r") as main_prompt_file:
        main_prompt = json.load(main_prompt_file)

    main_prompt = {f"<{key}>": value for key, value in main_prompt.items()}
    replace_tags(identity_path, main_prompt)

    print(f"Finished {task} identity: {identity_path.name}")


def clean_identity(agents_path: Path):
    '''Clean identity directory.'''
    templates = ["generic", "coder"]
    for agent in agents_path.iterdir():
        if agent.is_dir() and agent.name not in templates:
            shutil.rmtree(agent)
            print(f"Removed identity: {agent.name}")


def replace_tags(dest_path: Path, main_prompt: dict):
    '''Replace tags in files.'''
    for root, dirs, files in os.walk(dest_path):
        for file in files:
            file_path = os.path.join(root, file)

            with open(file_path, 'r+') as f:
                content = f.read()

                for placeholder, value in main_prompt.items():
                    content = content.replace(placeholder, str(value))

                f.seek(0)  
                f.write(content)
                f.truncate()
