from enum import Enum
import json
import re
import subprocess

from gpt_engineer.ai import AI
from gpt_engineer.chat_to_files import to_files
from gpt_engineer.db import DBs


def setup_sys_prompt(dbs: DBs):
    return dbs.identity["create"] + "\nUseful to know:\n" + dbs.identity["philosophy"]


def gen_simple(ai: AI, dbs: DBs):
    """Run the AI on the main prompt and save the results"""
    messages = ai.start(
        setup_sys_prompt(dbs),
        dbs.identity["main_prompt"],
    )
    to_files(messages[-1]["content"], dbs.workspace)
    return messages


def clarify(ai: AI, dbs: DBs):
    """
    Ask the user if they want to clarify anything and save the results to the workspace
    """
    messages = [ai.fsystem(dbs.identity["qa"])]
    user = dbs.identity["main_prompt"]
    while True:
        messages = ai.next(messages, user)

        if messages[-1]["content"].strip().lower().startswith("no"):
            break

        print()
        user = input('(answer in text, or "q" to move on)\n')
        print()

        if not user or user == "q":
            break

        user += (
            "\n\n"
            "Is anything else unclear? If yes, only answer in the form:\n"
            "{remaining unclear areas} remaining questions.\n"
            "{Next question}\n"
            'If everything is sufficiently clear, only answer "no".'
        )
    print()
    return messages


def gen_spec(ai: AI, dbs: DBs):
    """
    Generate a spec from the main prompt + clarifications and save the results to
    the workspace
    """
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fsystem(f"Instructions: {dbs.identity['main_prompt']}"),
    ]
    messages = ai.next(messages, dbs.identity["spec"])
    dbs.memory["specification"] = messages[-1]["content"]
    return messages


def respec(ai: AI, dbs: DBs):
    messages = json.loads(dbs.logs[gen_spec.__name__])
    messages += [ai.fsystem(dbs.identity["respec"])]

    messages = ai.next(messages)
    messages = ai.next(messages, dbs.identity["check"])

    dbs.memory["specification"] = messages[-1]["content"]
    return messages


def gen_unit_tests(ai: AI, dbs: DBs):
    """
    Generate unit tests based on the specification, that should work.
    """
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.identity['main_prompt']}"),
        ai.fuser(f"Outline:\n\n{dbs.memory['specification']}"),
    ]

    messages = ai.next(messages, dbs.identity["tests"])

    dbs.memory["tests"] = messages[-1]["content"]
    to_files(dbs.memory["tests"], dbs.workspace)
    return messages


def gen_clarified_code(ai: AI, dbs: DBs):
    
    messages = json.loads(dbs.logs[clarify.__name__])

    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
    ] + messages[1:]
    
    messages = ai.next(messages, dbs.identity["create"])
    
    to_files(messages[-1]["content"], dbs.workspace)
    return messages


def gen_code(ai: AI, dbs: DBs):
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.identity['main_prompt']}"),
        ai.fuser(f"Outline:\n\n{dbs.memory['specification']}"),
        ai.fuser(f"Tests:\n\n{dbs.memory['tests']}"),
    ]
    
    messages = ai.next(messages, dbs.identity["create"])
    to_files(messages[-1]["content"], dbs.workspace)
    return messages


def execute_entrypoint(ai: AI, dbs: DBs):
    command = dbs.workspace["run.sh"]
    print("Do you want to execute this code?")
    print()
    print(command)
    print()
    print('If yes, press enter. Otherwise, type "no"')
    print()
    if input() != "yes": # was missing?
        print("Ok, not executing the code.")
        return []
    print("Executing the code...")
    print()
    subprocess.run("run.sh", shell=True, cwd=dbs.workspace.path)
    return []


def gen_entrypoint(ai: AI, dbs: DBs):
    messages = ai.start(
        system=(dbs.identity["install"]),
        user="Information about the codebase:\n\n" + dbs.workspace["all_output.txt"],
    )
    print()
    regex = r"```\S*\n(.+?)```"
    matches = re.finditer(regex, messages[-1]["content"], re.DOTALL)
    dbs.workspace["run.sh"] = "\n".join(match.group(1) for match in matches)
    return messages


def gen_summary(ai: AI, dbs: DBs):
    messages = ai.start(
        system=(dbs.identity["summary"]),
        user="Information about the project:\n\n" + dbs.workspace["all_output.txt"],
    )
    print()
    return messages


def use_feedback(ai: AI, dbs: DBs):
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Project to Improve: {dbs.workspace['all_output.txt']}"),
        ai.fuser(f"Feedback: {dbs.input['feedback']}")
    ]

    messages = ai.next(messages, dbs.identity["use_feedback"])
    messages = ai.next(messages, dbs.identity["improve"])
    
    to_files(messages[-1]["content"], dbs.workspace)
    return messages



def fix_code(ai: AI, dbs: DBs):
    code_ouput = json.loads(dbs.logs[gen_code.__name__])[-1]["content"]
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.identity['main_prompt']}"),
        ai.fuser(code_ouput),
        ai.fsystem(dbs.identity["improve"]),
    ]
    
    messages = ai.next(messages, "Please fix any errors in the code above.")
    
    to_files(messages[-1]["content"], dbs.workspace)
    return messages


def improve(ai: AI, dbs: DBs):
    simple_output = json.loads(dbs.logs[gen_simple.__name__])[-1]["content"]
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.identity['main_prompt']}"),
        ai.fuser(simple_output),
        ai.fsystem(dbs.identity["improve"]),
    ]
    
    messages = ai.next(messages, "Please improve the project above.")
    
    to_files(messages[-1]["content"], dbs.workspace)
    return messages

class Config(str, Enum):
    DEFAULT = "default"
    BENCHMARK = "benchmark"
    SIMPLE = "simple"
    TDD = "tdd"
    TDD_PLUS = "tdd+"
    CLARIFY = "clarify"
    RESPEC = "respec"
    EXECUTE_ONLY = "execute_only"
    USE_FEEDBACK = "use_feedback"


# Different configs of what steps to run
STEPS = {
    Config.DEFAULT: [
        clarify,
        gen_clarified_code,
        gen_entrypoint,
        execute_entrypoint,
    ],
    Config.BENCHMARK: [gen_simple, gen_entrypoint],
    Config.SIMPLE: [gen_simple, gen_entrypoint, execute_entrypoint],
    Config.TDD: [
        gen_spec,
        gen_unit_tests,
        gen_code,
        gen_entrypoint,
        execute_entrypoint,
    ],
    Config.TDD_PLUS: [
        gen_spec,
        gen_unit_tests,
        gen_code,
        fix_code,
        gen_entrypoint,
        execute_entrypoint,
    ],
    Config.CLARIFY: [
        clarify,
        gen_clarified_code,
        gen_entrypoint,
        execute_entrypoint,
    ],
    Config.RESPEC: [
        gen_spec,
        respec,
        gen_unit_tests,
        gen_code,
        gen_entrypoint,
        execute_entrypoint,
    ],
    Config.USE_FEEDBACK: [use_feedback, gen_entrypoint, execute_entrypoint],
    Config.EXECUTE_ONLY: [gen_entrypoint, execute_entrypoint],
}

# Future steps that can be added:
# run_tests_and_fix_files
# execute_entrypoint_and_fix_files_if_needed