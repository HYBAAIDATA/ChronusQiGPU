from chronus.agent.search import search, SearchStatus as S


def test_search_exhaustion_not_infeasibility():
    r = search(
        "0",
        expand=lambda n: (str(int(n) + 1),),
        goal=lambda n: n == "3",
        max_nodes=2,
        max_frontier=4,
    )
    assert r.status == S.BUDGET_EXHAUSTED and r.certificate is None
    r = search("0", expand=lambda n: (), goal=lambda n: False, max_nodes=2, max_frontier=4)
    assert r.status == S.EXHAUSTED and r.certificate is None
    r = search("0", expand=lambda n: ("1",), goal=lambda n: n == "1", max_nodes=2, max_frontier=4)
    assert r.status == S.FOUND
