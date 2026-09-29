"""Command line entry point."""
import argparse
import sys

from .core import RoleFormatError, classify, decompose, estimate, json_output, markdown, parse, propose, report
from .fixtures import generate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Conservative diagnostic for fictional synthetic roles; heuristic ranges, never promises.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("parse", "classify", "estimate", "propose", "report"):
        command = commands.add_parser(name)
        command.add_argument("file")
        if name == "parse":
            command.add_argument("--decompose", action="store_true")
        if name == "report":
            command.add_argument("--format", choices=("md", "json"), default="md")
    fixtures = commands.add_parser("fixtures")
    fixtures.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fixtures":
            output = {"fixtures": generate(args.out), "synthetic": True}
        else:
            role = parse(args.file)
            if args.command == "parse":
                output = {**role, "tasks": decompose(role)} if args.decompose else role
            elif args.command == "classify":
                output = classify(decompose(role))
            elif args.command == "estimate":
                output = estimate(role, classify(decompose(role)))
            elif args.command == "propose":
                output = propose(estimate(role, classify(decompose(role)))["tasks"])
            else:
                output = report(role)
                if args.format == "md":
                    sys.stdout.write(markdown(output))
                    return 0
        sys.stdout.write(json_output(output))
        return 0
    except (RoleFormatError, OSError) as error:
        sys.stderr.write(f"{type(error).__name__}: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
