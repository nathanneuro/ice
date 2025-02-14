from ice.trace import TracedABC


class Agent(TracedABC):
    label: str | None = None

    async def relevance(
        self,
        *,
        context: str,
        question: str,
        verbose: bool = False,
        default: float | None = None,
    ) -> float:
        raise NotImplementedError

    async def answer(
        self,
        *,
        prompt: str,
        multiline: bool = True,
        verbose: bool = False,
        default: str = "",
        max_tokens: int = 256,
    ) -> str:
        raise NotImplementedError

    async def predict(
        self, *, context: str, default: str = "", verbose: bool = False
    ) -> dict[str, float]:
        raise NotImplementedError

    async def classify(
        self,
        *,
        prompt: str,
        choices: tuple[str, ...],
        default: str | None = None,
        verbose: bool = False,
    ) -> tuple[dict[str, float], str | None]:
        raise NotImplementedError
