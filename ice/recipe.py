import asyncio
import sys

from abc import abstractmethod
from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction
from pathlib import Path
from traceback import print_exc
from typing import final
from typing import Generic
from typing import no_type_check
from typing import TypeGuard
from typing import TypeVar

import defopt

from merge_args import merge_args
from pydantic import BaseSettings
from structlog.stdlib import get_logger

from ice.agent import Agent
from ice.agent import agent_policy
from ice.environment import env
from ice.evaluation.evaluate_recipe_result import EvaluatedRecipeResult
from ice.evaluation.evaluate_recipe_result import RecipeResult
from ice.evaluation.evaluation_report import EvaluationReport
from ice.mode import Mode
from ice.paper import Paper
from ice.trace import enable_trace
from ice.trace import trace
from ice.trace import TracedABC
from ice.utils import map_async

RecipeSettings = TypeVar("RecipeSettings", bound=BaseSettings)

log = get_logger()


def is_list_of_recipe_result(value: object) -> TypeGuard[list[RecipeResult]]:
    return isinstance(value, list) and all(
        isinstance(item, RecipeResult) for item in value
    )


class Recipe(TracedABC, Generic[RecipeSettings]):
    defaults: Callable[["Recipe"], RecipeSettings] = lambda self: BaseSettings()  # type: ignore[assignment, return-value]

    def __init__(self, mode: Mode = "machine", settings: RecipeSettings | None = None):
        self.mode = mode
        self.s = settings or self.defaults()
        self.results: list[RecipeResult] = []

    @classmethod
    def slug(cls) -> str:
        """A unique identifier for this recipe, which does not change when the recipe is updated."""
        return cls.__name__.lower()

    @no_type_check
    @abstractmethod
    async def run(self, **kwargs):
        raise NotImplementedError

    @final
    def maybe_add_to_results(self, results: list[RecipeResult] | object):
        if is_list_of_recipe_result(results):
            self.results.extend(results)

    def to_json(self, results: list[RecipeResult] | object) -> list[dict]:
        """Convert results to objects that can be serialized to JSON."""
        if is_list_of_recipe_result(results):
            return [result.dict() for result in results]
        raise NotImplementedError

    async def evaluation_report(self) -> EvaluationReport:
        return EvaluationReport(
            technique_name=str(self),
            results=await map_async(
                self.results, EvaluatedRecipeResult.from_recipe_result
            ),
        )

    def agent(self, agent_name: str | None = None) -> Agent:
        return agent_policy(mode=self.mode, agent_name=agent_name)

    def max_concurrency(self) -> int:
        return 10 if self.mode == "machine" else 1

    def __str__(self) -> str:
        return self.__class__.__name__


class RecipeHelper:
    def __init__(self):
        self._mode: Mode | None = "machine"

    def main(self, main):
        if not iscoroutinefunction(main):
            raise TypeError("recipe.main must be given an async function")

        # Trace all globals defined in main's module.
        g = main.__globals__
        for name, value in g.items():
            if getattr(value, "__module__", None) == main.__module__:
                g[name] = trace(value)

        if main.__module__ != "__main__":
            return

        # The frontend shows everything under the first traced root.
        # TODO: Once main.py is gone, change the frontend and get rid of this wrapper.
        @trace
        @wraps(main)
        async def hidden_wrapper(*args, **kwargs):
            try:
                result = await trace(main)(*args, **kwargs)
            except NameError:
                print_exc()
                print(
                    "\nReminder: recipe.main should be at the bottom of the file",
                    file=sys.stderr,
                )
                sys.exit(1)

            env().print(result, format_markdown=False)
            return result

        # A traced function cannot be called until the event loop is running.
        @wraps(main)
        async def untraced_wrapper(*args, **kwargs):
            return await hidden_wrapper(*args, **kwargs)

        @merge_args(main)
        def cli(
            *args,
            mode: Mode = "machine",
            trace: bool = True,
            **kwargs,
        ):
            self._mode = mode
            if trace:
                enable_trace()
            asyncio.run(untraced_wrapper(*args, **kwargs))

        defopt.run(
            cli,
            cli_options="all",
            short={},
            parsers={Paper: lambda path: Paper.load(Path(path))},
        )

    def agent(self, agent_name: str | None = None) -> Agent:
        assert self._mode
        return agent_policy(self._mode, agent_name)


recipe = RecipeHelper()
