"""Итог переноса: сколько чего перенесено и какие были проблемы."""

from dataclasses import dataclass, field


@dataclass
class Report:
    counts: dict = field(default_factory=dict)  # что -> сколько создано
    problems: list = field(default_factory=list)

    def count(self, what, value):
        self.counts[what] = self.counts.get(what, 0) + value

    def problem(self, text):
        self.problems.append(text)

    def lines(self, problems_shown=50):
        result = [f"{what}: {value}" for what, value in self.counts.items()]
        if self.problems:
            result.append(f"Проблемы ({len(self.problems)}):")
            result += [f"  {p}" for p in self.problems[:problems_shown]]
            if len(self.problems) > problems_shown:
                result.append(f"  … и ещё {len(self.problems) - problems_shown}")
        return result
