from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Callable

from . import dispatch_analysis, dispatch_control, dispatch_data, dispatch_delivery


CommandHandler = Callable[[argparse.Namespace, argparse.ArgumentParser], dict[str, Any]]


@dataclass(frozen=True)
class CommandGroup:
    name: str
    commands: frozenset[str]
    handler: CommandHandler


class CommandRegistry:
    def __init__(self, groups: tuple[CommandGroup, ...]) -> None:
        self._groups = groups
        self._handlers: dict[str, CommandGroup] = {}
        for group in groups:
            for command in group.commands:
                previous = self._handlers.get(command)
                if previous is not None:
                    raise RuntimeError(f"CLI command {command!r} is registered by both {previous.name!r} and {group.name!r}")
                self._handlers[command] = group

    @property
    def commands(self) -> frozenset[str]:
        return frozenset(self._handlers)

    @property
    def groups(self) -> tuple[CommandGroup, ...]:
        return self._groups

    def validate_parser(self, parser: argparse.ArgumentParser) -> None:
        parser_commands: set[str] = set()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                parser_commands.update(action.choices)
        missing_handlers = sorted(parser_commands - self.commands)
        missing_parsers = sorted(self.commands - parser_commands)
        if missing_handlers or missing_parsers:
            raise RuntimeError(
                "CLI parser and command registry differ: "
                f"missing handlers={missing_handlers}, missing parsers={missing_parsers}"
            )

    def dispatch(self, args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
        command = str(getattr(args, "command", ""))
        group = self._handlers.get(command)
        if group is None:
            raise ValueError(f"Unknown command: {command}")
        return group.handler(args, parser)


def build_command_registry() -> CommandRegistry:
    return CommandRegistry((
        CommandGroup("control", dispatch_control.COMMANDS, dispatch_control.dispatch),
        CommandGroup("analysis", dispatch_analysis.COMMANDS, dispatch_analysis.dispatch),
        CommandGroup("data", dispatch_data.COMMANDS, dispatch_data.dispatch),
        CommandGroup("delivery", dispatch_delivery.COMMANDS, dispatch_delivery.dispatch),
    ))
