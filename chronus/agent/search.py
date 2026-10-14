"""Bounded graph search; failure within budget is not an infeasibility proof."""

from dataclasses import dataclass
from enum import Enum
from ._contracts import ContractError, integer, text


class SearchStatus(Enum):
    FOUND = "found"
    BUDGET_EXHAUSTED = "no_solution_within_budget"
    EXHAUSTED = "reachable_space_exhausted"
    METHOD_INADEQUATE = "current_method_inadequate"


@dataclass(frozen=True)
class SearchResult:
    status: SearchStatus
    best: str | None
    explored: tuple[str, ...]
    frontier: tuple[str, ...]
    certificate: str | None = None


def search(start, *, expand, goal, max_nodes, max_frontier):
    text(start)
    integer(max_nodes, minimum=1, maximum=100000)
    integer(max_frontier, minimum=1, maximum=100000)
    frontier, queued, explored = [start], {start}, []
    while frontier and len(explored) < max_nodes:
        node = frontier.pop(0)
        explored.append(node)
        if goal(node):
            return SearchResult(SearchStatus.FOUND, node, tuple(explored), tuple(frontier))
        children = expand(node)
        if type(children) is not tuple or len(children) > max_frontier:
            raise ContractError("expansion must return a bounded tuple")
        for child in children:
            text(child)
            if child not in queued:
                if len(frontier) >= max_frontier:
                    return SearchResult(
                        SearchStatus.BUDGET_EXHAUSTED, None, tuple(explored), tuple(frontier)
                    )
                frontier.append(child)
                queued.add(child)
    status = SearchStatus.BUDGET_EXHAUSTED if frontier else SearchStatus.EXHAUSTED
    return SearchResult(status, None, tuple(explored), tuple(frontier))
