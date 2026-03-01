"""Task registry for auto-discovery of Flyte tasks and workflows.

Discovers all tasks from stargazer.tasks and stargazer.workflows modules,
extracts parameter types, defaults, and return types for MCP catalog exposure.
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, get_type_hints


def _type_name(hint: Any) -> str:
    """Convert a type hint to a human-readable string."""
    origin = getattr(hint, "__origin__", None)
    args = getattr(hint, "__args__", None)

    if origin is not None:
        # Handle generic types like list[str], dict[str, str], tuple[Path, Path]
        origin_name = getattr(origin, "__name__", str(origin))
        if args:
            arg_names = ", ".join(_type_name(a) for a in args)
            return f"{origin_name}[{arg_names}]"
        return origin_name

    # Handle Union types (e.g., str | None)
    if hasattr(hint, "__args__") and hasattr(hint, "__origin__"):
        pass  # already handled above

    # types.UnionType (Python 3.10+ X | Y syntax)
    import types as _types

    if isinstance(hint, _types.UnionType):
        return " | ".join(_type_name(a) for a in hint.__args__)

    # typing.Union
    if getattr(hint, "__origin__", None) is not None:
        pass  # already handled

    # Simple class
    if hasattr(hint, "__name__"):
        return hint.__name__

    return str(hint)


@dataclass
class TaskParam:
    """Describes a single parameter of a task."""

    name: str
    type_hint: Any
    type_name: str
    required: bool
    default: Any = None


@dataclass
class TaskOutput:
    """Describes a single output of a task."""

    name: str
    type_hint: Any
    type_name: str


@dataclass
class TaskInfo:
    """Complete metadata about a registered task."""

    name: str
    category: str  # "task" or "workflow"
    description: str
    params: list[TaskParam]
    outputs: list[TaskOutput]
    task_obj: Any  # The Flyte task object


@dataclass
class TaskRegistry:
    """Discovers and provides access to all Flyte tasks and workflows."""

    _tasks: dict[str, TaskInfo] = field(default_factory=dict)

    def __post_init__(self):
        self._discover()

    def _discover(self):
        """Walk task and workflow modules to register all Flyte tasks."""
        self._discover_tasks()
        self._discover_workflows()

    def _discover_tasks(self):
        """Register all tasks from stargazer.tasks.__all__."""
        import stargazer.tasks as tasks_mod

        for name in tasks_mod.__all__:
            obj = getattr(tasks_mod, name)
            if not hasattr(obj, "func"):
                continue
            self._register(obj.short_name, obj, category="task")

    def _discover_workflows(self):
        """Register all workflows from stargazer.workflows.__all__."""
        import stargazer.workflows as workflows_mod

        for name in workflows_mod.__all__:
            obj = getattr(workflows_mod, name)
            if not hasattr(obj, "func"):
                continue
            # Skip if already registered (e.g. duplicate short_name across modules)
            if obj.short_name in self._tasks:
                continue
            self._register(obj.short_name, obj, category="workflow")

    def _register(self, name: str, task_obj: Any, category: str):
        """Register a single task by introspecting its wrapped function."""
        func = task_obj.func
        sig = inspect.signature(func)
        hints = get_type_hints(func)

        # Extract parameters
        params = []
        for pname, param in sig.parameters.items():
            hint = hints.get(pname, Any)
            has_default = param.default is not inspect.Parameter.empty
            params.append(
                TaskParam(
                    name=pname,
                    type_hint=hint,
                    type_name=_type_name(hint),
                    required=not has_default,
                    default=param.default if has_default else None,
                )
            )

        # Extract outputs from return type
        return_hint = hints.get("return", type(None))
        outputs = _parse_outputs(return_hint)

        # Extract description from docstring
        doc = func.__doc__ or ""
        description = doc.strip().split("\n")[0] if doc.strip() else ""

        self._tasks[name] = TaskInfo(
            name=name,
            category=category,
            description=description,
            params=params,
            outputs=outputs,
            task_obj=task_obj,
        )

    def get(self, name: str) -> TaskInfo | None:
        """Look up a task by name."""
        return self._tasks.get(name)

    def list_tasks(self, category: str | None = None) -> list[TaskInfo]:
        """List all registered tasks, optionally filtered by category."""
        tasks = list(self._tasks.values())
        if category:
            tasks = [t for t in tasks if t.category == category]
        return tasks

    def to_catalog(self, category: str | None = None) -> list[dict]:
        """Return a JSON-serializable catalog of all tasks."""
        catalog = []
        for info in self.list_tasks(category=category):
            catalog.append(
                {
                    "name": info.name,
                    "category": info.category,
                    "description": info.description,
                    "params": [
                        {
                            "name": p.name,
                            "type": p.type_name,
                            "required": p.required,
                            "default": _serialize_default(p.default)
                            if not p.required
                            else None,
                        }
                        for p in info.params
                    ],
                    "outputs": [
                        {"name": o.name, "type": o.type_name} for o in info.outputs
                    ],
                }
            )
        return catalog


def _parse_outputs(return_hint: Any) -> list[TaskOutput]:
    """Parse a return type hint into a list of TaskOutput."""
    origin = getattr(return_hint, "__origin__", None)
    if origin is tuple:
        # Multi-output: tuple[A, B, ...] → o0, o1, ...
        args = return_hint.__args__
        return [
            TaskOutput(name=f"o{i}", type_hint=arg, type_name=_type_name(arg))
            for i, arg in enumerate(args)
        ]
    # Single output
    return [
        TaskOutput(name="o0", type_hint=return_hint, type_name=_type_name(return_hint))
    ]


def _serialize_default(value: Any) -> Any:
    """Make default values JSON-serializable."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
