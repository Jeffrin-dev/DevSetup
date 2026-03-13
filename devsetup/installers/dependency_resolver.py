"""
devsetup.installers.dependency_resolver
-----------------------------------------
Dependency resolution for the v1.4 install engine.

Responsibilities (strictly read-only — no installation, no OS logic):
  - Build a dependency graph from a tool list and their installer classes
  - Validate all dependency references exist in the registry and tool list
  - Detect circular dependencies and report the cycle path
  - Produce a deterministic topological install order

Public API
----------
  resolve(tools, registry) -> List[str]
      Single entry point. Returns tools in dependency-correct install order.
      Raises DependencyError on cycle, missing registry entry, or missing
      tool reference.

  get_blocked(tool, graph, failed_or_blocked) -> Optional[str]
      Return the first failing dependency ID, or None if the tool is unblocked.

Complexity (Phase 14)
---------------------
  build_graph      : O(n + e)      where n = tools, e = total dependency edges
  topological_sort : O((n+e) log n) Kahn's algorithm with min-heap
  cycle detection  : O(n + e)      DFS coloring, runs only when Kahn detects cycle
"""

from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Set, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from devsetup.installers.base import BaseInstaller


# ── Exception ─────────────────────────────────────────────────────────────────

class DependencyError(ValueError):
    """
    Raised when dependency resolution cannot produce a valid install order.

    Covers three cases:
      - A dependency ID is not present in the installer registry
      - A dependency ID is not present in the environment tool list
      - A circular dependency is detected

    Attributes
    ----------
    cycle_path : List[str] | None
        The nodes forming the cycle, e.g. ['git', 'node', 'git'],
        or None for non-cycle errors.
    """

    def __init__(self, message: str, cycle_path: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.cycle_path = cycle_path


# ── Public entry point ────────────────────────────────────────────────────────

def resolve(
    tools: List[str],
    registry: Dict[str, Type],
) -> List[str]:
    """
    Return tools in dependency-correct install order.

    The input tool list may be in any order — the resolved order
    guarantees every dependency installs before its dependents.
    Tools with no dependencies among themselves retain a stable,
    alphabetically-consistent relative order (deterministic — Phase 5).

    Parameters
    ----------
    tools : List[str]
        Tool IDs as they appear in the environment config.
    registry : Dict[str, Type[BaseInstaller]]
        The live installer registry from manager.py.

    Returns
    -------
    List[str]
        Tools ordered so that every dependency precedes its dependent.

    Raises
    ------
    DependencyError
        If a dependency is not registered, not in the tool list, or a
        cycle is detected.
    """
    ordered, _ = resolve_with_graph(tools, registry)
    return ordered


def resolve_with_graph(
    tools: List[str],
    registry: Dict[str, Type],
) -> tuple:
    """
    Return (ordered_tools, graph) in a single call.

    Eliminates the double graph-build that occurs when callers first call
    build_graph() for logging, then resolve() for ordering. manager.py
    uses this entry point so the adjacency map is constructed exactly once.

    Returns
    -------
    tuple[List[str], Dict[str, List[str]]]
        (ordered_tools, graph)

    Raises
    ------
    DependencyError
        If a dependency is not registered, not in the tool list, or a
        cycle is detected.
    """
    if not tools:
        return [], {}

    graph = build_graph(tools, registry)
    _validate(tools, graph, registry)
    return _topological_sort(tools, graph), graph


def get_blocked(
    tool: str,
    graph: Dict[str, List[str]],
    failed_or_blocked: Set[str],
) -> Optional[str]:
    """
    Return the first failing dependency of tool, or None if unblocked.

    Parameters
    ----------
    tool : str
        The tool to check.
    graph : Dict[str, List[str]]
        Dependency graph: tool -> list of its direct dependencies.
    failed_or_blocked : Set[str]
        Tools that have already failed or been blocked this run.

    Returns
    -------
    str | None
        The dependency that caused the block, or None if tool can run.
    """
    for dep in graph.get(tool, []):
        if dep in failed_or_blocked:
            return dep
    return None



# ── Internal implementation ───────────────────────────────────────────────────

def build_graph(
    tools: List[str],
    registry: Dict[str, Type],
) -> Dict[str, List[str]]:
    """
    Build the dependency adjacency map for the given tool list.

    Only dependencies that appear in ``tools`` are included — dependencies
    on tools outside the environment are caught by _validate() and raise
    DependencyError there.

    Called internally by resolve() and exposed as public API so tests and
    callers can inspect the graph directly without running the full resolver.

    Complexity: O(n + e)
    """
    tool_set = set(tools)
    graph: Dict[str, List[str]] = {}

    for tool_id in tools:
        cls = registry.get(tool_id)
        if cls is None:
            graph[tool_id] = []
            continue
        # BaseInstaller subclasses declare dependencies as a class attribute
        raw_deps: List[str] = getattr(cls, "dependencies", [])
        # Only keep deps that are in the install set; unknown refs caught later
        graph[tool_id] = [d for d in raw_deps if d in tool_set]

    return graph


def _validate(
    tools: List[str],
    graph: Dict[str, List[str]],
    registry: Dict[str, Type],
) -> None:
    """
    Validate all declared dependencies (Phase 7).

    Raises DependencyError when:
      - A dependency ID is not registered in the installer registry
      - A dependency ID is not present in the environment tool list

    Complexity: O(n + e)
    """
    tool_set = set(tools)

    for tool_id in tools:
        cls = registry.get(tool_id)
        if cls is None:
            continue
        raw_deps: List[str] = getattr(cls, "dependencies", [])

        for dep in raw_deps:
            if dep not in registry:
                raise DependencyError(
                    f"CONFIG ERROR: installer '{tool_id}' declares dependency "
                    f"'{dep}' which is not in the installer registry. "
                    f"Register '{dep}' or remove it from {tool_id}.dependencies."
                )
            if dep not in tool_set:
                raise DependencyError(
                    f"CONFIG ERROR: installer '{tool_id}' depends on '{dep}' "
                    f"but '{dep}' is not in this environment's tool list. "
                    f"Add '{dep}' to the environment config or remove the dependency."
                )


def _topological_sort(
    tools: List[str],
    graph: Dict[str, List[str]],
) -> List[str]:
    """
    Kahn's algorithm with a min-heap priority queue — O((n + e) log n).

    Produces a deterministic order: among tools with equal in-degree at
    any step, alphabetical ordering is applied so the result is stable
    across Python versions and runtime state.

    The heap provides O(log n) push and pop, replacing the previous
    list.pop(0) + list.sort() approach which was O(n² log n).

    Raises DependencyError with cycle path when a cycle is detected.
    """
    # Build reverse map: dep -> list of tools that depend on it
    dependents: Dict[str, List[str]] = {t: [] for t in tools}
    for tool in tools:
        for dep in graph[tool]:
            dependents[dep].append(tool)

    # Initial in-degree = number of dependencies each tool has
    in_degree: Dict[str, int] = {t: len(graph[t]) for t in tools}

    # Min-heap of tool names with no remaining dependencies.
    # Python strings compare lexicographically, so heapq gives alphabetical
    # ordering for free — determinism without an explicit sort() call.
    heap: List[str] = [t for t in tools if in_degree[t] == 0]
    heapq.heapify(heap)
    ordered: List[str] = []

    while heap:
        tool = heapq.heappop(heap)   # O(log n) — alphabetically smallest ready tool
        ordered.append(tool)

        for dependent in dependents[tool]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(heap, dependent)   # O(log n)

    if len(ordered) != len(tools):
        # Not all nodes processed — cycle exists
        cycle = _find_cycle(tools, graph)
        cycle_str = " → ".join(cycle) if cycle else "(unknown)"
        raise DependencyError(
            f"Dependency cycle detected: {cycle_str}\n"
            f"Installation aborted. Remove the circular dependency to proceed.",
            cycle_path=cycle,
        )

    return ordered


def _find_cycle(
    tools: List[str],
    graph: Dict[str, List[str]],
) -> Optional[List[str]]:
    """
    DFS coloring to find and return the cycle node path — O(n + e).

    Returns the cycle as a list starting and ending at the same node,
    e.g. ['git', 'node', 'git'], or None if no cycle found (shouldn't
    happen when called after Kahn detects one, but defensive).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {t: WHITE for t in tools}
    path: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        color[node] = GRAY
        path.append(node)
        for dep in sorted(graph.get(node, [])):
            if color[dep] == GRAY:
                # Cycle found — extract the cycle portion of path
                cycle_start = path.index(dep)
                return path[cycle_start:] + [dep]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for tool in sorted(tools):
        if color[tool] == WHITE:
            result = dfs(tool)
            if result:
                return result

    return None
